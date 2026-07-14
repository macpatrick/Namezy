"""
Namezy -- lean MVP.

Flask app orchestrating the core naming loop:
  description -> Brand Strategist (Claude) -> Name Generator (Claude)
  -> Duplicate Eliminator -> Validation (domain + Google web-conflict)
  -> Brandability scoring -> ranked SQLite-backed shortlist.

See README.md for full details and how to run this.
"""
import csv
import io
import json

from flask import Flask, Response, abort, jsonify, render_template, request

import database
import validation
from brand_strategist import BrandStrategistError, extract_brand_profile
from dedupe import dedupe_candidates, normalize
from name_generator import NameGeneratorError, generate_candidates
from scoring import compute_score

app = Flask(__name__)
database.init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(silent=True) or {}
    description = (payload.get("description") or "").strip()
    company_name = (payload.get("company_name") or "").strip() or None

    if not description:
        return jsonify({"error": "A description is required."}), 400

    # 1. Brand Strategist
    try:
        profile = extract_brand_profile(description)
    except BrandStrategistError as exc:
        return jsonify({"error": str(exc)}), 502

    conn = database.get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO projects (company_name, description, industry, personality_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (company_name, description, None, json.dumps(profile), database.now_iso()),
        )
        project_id = cur.lastrowid
        conn.commit()

        # 2. Name Generator
        try:
            raw_candidates = generate_candidates(profile)
        except NameGeneratorError as exc:
            return jsonify({"error": str(exc), "project_id": project_id}), 502

        # 3. Duplicate Eliminator
        deduped = dedupe_candidates(raw_candidates)
        if not deduped:
            return jsonify(
                {"error": "No usable candidate names survived deduplication.", "project_id": project_id}
            ), 502

        # 4. Validation -- domain check (bulk, threaded) for everyone
        norms = [normalize(c["name"]) for c in deduped]
        domain_results = validation.check_domains_bulk(norms)

        # Preliminary score (no domain/web bonus yet) decides which
        # candidates get a quota-limited Google Custom Search check.
        prelim = []
        for c in deduped:
            norm = normalize(c["name"])
            prelim_score = compute_score(c["name"], {}, "unchecked")
            prelim.append((prelim_score, c, norm))
        prelim.sort(key=lambda t: t[0], reverse=True)

        web_results = {}
        if validation.google_configured():
            for _, c, _norm in prelim[: validation.GOOGLE_CSE_MAX_CHECKS]:
                web_results[c["name"]] = validation.check_web_conflict(c["name"])

        # 6. Brandability scoring (final, with domain + web-conflict bonuses)
        scored_rows = []
        for _, c, norm in prelim:
            domain_status = domain_results.get(norm, {})
            web_info = web_results.get(c["name"], {"status": "not_configured", "top_result": None})
            final_score = compute_score(c["name"], domain_status, web_info["status"])
            scored_rows.append((c, norm, domain_status, web_info, final_score))

        scored_rows.sort(key=lambda r: r[4], reverse=True)

        now = database.now_iso()
        for c, norm, domain_status, web_info, final_score in scored_rows:
            cur = conn.execute(
                "INSERT INTO candidates "
                "(project_id, candidate, candidate_norm, method, score, status, favorite, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', 0, ?)",
                (project_id, c["name"], norm, c.get("method"), final_score, now),
            )
            candidate_id = cur.lastrowid
            conn.execute(
                "INSERT INTO validation "
                "(candidate_id, domain_com, domain_io, domain_app, google, google_top_result, checked_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    candidate_id,
                    domain_status.get("com"),
                    domain_status.get("io"),
                    domain_status.get("app"),
                    web_info.get("status"),
                    web_info.get("top_result"),
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return jsonify(_get_project_payload(project_id))


def _get_project_payload(project_id: int) -> dict:
    conn = database.get_connection()
    try:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            abort(404)
        rows = conn.execute(
            "SELECT c.id, c.candidate, c.method, c.score, c.favorite, "
            "v.domain_com, v.domain_io, v.domain_app, v.google, v.google_top_result "
            "FROM candidates c LEFT JOIN validation v ON v.candidate_id = c.id "
            "WHERE c.project_id = ? ORDER BY c.score DESC",
            (project_id,),
        ).fetchall()
        return {
            "project": dict(project),
            "candidates": [dict(r) for r in rows],
            "google_configured": validation.google_configured(),
        }
    finally:
        conn.close()


@app.route("/api/projects/<int:project_id>")
def api_get_project(project_id: int):
    return jsonify(_get_project_payload(project_id))


@app.route("/api/candidates/<int:candidate_id>/favorite", methods=["PATCH"])
def api_toggle_favorite(candidate_id: int):
    conn = database.get_connection()
    try:
        row = conn.execute("SELECT favorite FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            abort(404)
        new_value = 0 if row["favorite"] else 1
        conn.execute("UPDATE candidates SET favorite = ? WHERE id = ?", (new_value, candidate_id))
        conn.commit()
        return jsonify({"favorite": bool(new_value)})
    finally:
        conn.close()


@app.route("/api/projects/<int:project_id>/export.csv")
def api_export_csv(project_id: int):
    conn = database.get_connection()
    try:
        rows = conn.execute(
            "SELECT c.candidate, c.score, c.method, c.favorite, "
            "v.domain_com, v.domain_io, v.domain_app, v.google, v.google_top_result "
            "FROM candidates c LEFT JOIN validation v ON v.candidate_id = c.id "
            "WHERE c.project_id = ? ORDER BY c.score DESC",
            (project_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        abort(404)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "name",
            "score",
            "method",
            "favorite",
            "domain_com",
            "domain_io",
            "domain_app",
            "web_status",
            "web_top_result",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["candidate"],
                r["score"],
                r["method"],
                "Yes" if r["favorite"] else "No",
                r["domain_com"],
                r["domain_io"],
                r["domain_app"],
                r["google"],
                r["google_top_result"],
            ]
        )

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=namezy_project_{project_id}.csv"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
