"""
Validation step (brief section 5), scoped from 6 checks down to 2 for v1:
domain availability and a Google web-conflict check. Trademark, App Store,
Play Store, and social-handle checks are explicitly out of scope for v1 --
see database.py's `validation` table, which already has nullable columns
(`apple`, `play`, `trademark`, `social`, `risk`) reserved for them.
"""
import concurrent.futures
import os
import socket

import requests

DOMAIN_TLDS = ["com", "io", "app"]
DOMAIN_LOOKUP_TIMEOUT = 3.0

GOOGLE_CSE_API_KEY = os.environ.get("GOOGLE_CSE_API_KEY")
GOOGLE_CSE_CX = os.environ.get("GOOGLE_CSE_CX")
GOOGLE_CSE_MAX_CHECKS = int(os.environ.get("GOOGLE_CSE_MAX_CHECKS", "50"))


# --------------------------------------------------------------------------
# Domain check: free DNS-based heuristic (brief explicitly allows this in
# place of a paid registrar API). If a hostname resolves, treat it as taken;
# if resolution fails (NXDOMAIN-equivalent), treat it as likely available.
# This is a heuristic, not a WHOIS/RDAP lookup: a domain can resolve to
# nothing meaningful (parked page) yet still be "taken" here, and a domain
# with no DNS record can still be registered-but-unconfigured. Good enough
# as a free, fast v1 signal; a real WHOIS/RDAP check is a clean v2 upgrade
# that only touches this function.
# --------------------------------------------------------------------------


def _domain_registered(hostname: str):
    """Returns True (resolves -> likely taken), False (NXDOMAIN -> likely
    available), or None (lookup error / timeout -> unknown)."""
    try:
        socket.setdefaulttimeout(DOMAIN_LOOKUP_TIMEOUT)
        socket.getaddrinfo(hostname, None)
        return True
    except socket.gaierror:
        return False
    except Exception:
        return None


def check_domain(name_norm: str) -> dict:
    result = {}
    for tld in DOMAIN_TLDS:
        registered = _domain_registered(f"{name_norm}.{tld}")
        if registered is True:
            result[tld] = "taken"
        elif registered is False:
            result[tld] = "available"
        else:
            result[tld] = "unknown"
    return result


def check_domains_bulk(name_norms: list[str], max_workers: int = 20) -> dict:
    """Threaded domain lookups -- DNS calls are I/O-bound and slow one at a
    time; this keeps a batch of ~200 candidates x 3 TLDs from taking minutes."""
    results: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(check_domain, n): n for n in name_norms}
        for future in concurrent.futures.as_completed(future_map):
            n = future_map[future]
            try:
                results[n] = future.result()
            except Exception:
                results[n] = {tld: "unknown" for tld in DOMAIN_TLDS}
    return results


# --------------------------------------------------------------------------
# Web conflict check: Google Custom Search API. Requires GOOGLE_CSE_API_KEY
# and GOOGLE_CSE_CX env vars (see .env.example). If unset, this gracefully
# no-ops per candidate rather than failing the whole pipeline.
#
# STATUS (2026-07-14): confirmed non-functional for any newly created Google
# Cloud project -- the Custom Search JSON API is closed to new customers, so
# a fresh API key/project gets a 403 "This project does not have the access
# to Custom Search JSON API" regardless of account, org, or billing setup.
# Verified against two separate Google accounts (one Workspace-managed, one
# personal). This is a Google policy closure, not a bug in this code -- if
# this check needs to work, swap the request in check_web_conflict() below
# to a different provider (e.g. Serper.dev, Brave Search API) rather than
# debugging a 403 here again.
#
# Judgment call: the free tier is 100 queries/day (paid: $5 per 1,000), so
# this only checks the top GOOGLE_CSE_MAX_CHECKS candidates by preliminary
# score (default 50), not the full batch. Everything else is left
# "not_configured"/unchecked rather than burning quota on low-ranked names.
# --------------------------------------------------------------------------


def google_configured() -> bool:
    return bool(GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX)


def check_web_conflict(name: str) -> dict:
    """Returns {"status": "clear"|"conflict"|"error"|"not_configured", "top_result": str|None}"""
    if not google_configured():
        return {"status": "not_configured", "top_result": None}

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_CSE_API_KEY,
                "cx": GOOGLE_CSE_CX,
                "q": f'"{name}"',
                "num": 3,
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return {"status": "clear", "top_result": None}

        # Crude heuristic: if the top hit's title or URL contains the exact
        # candidate name, treat it as an existing-brand collision.
        top = items[0]
        title = (top.get("title") or "").lower()
        link = (top.get("link") or "").lower()
        name_lower = name.lower()
        if name_lower in title or name_lower in link:
            return {"status": "conflict", "top_result": top.get("link")}
        return {"status": "clear", "top_result": top.get("link")}
    except requests.RequestException as exc:
        return {"status": "error", "top_result": None, "error": str(exc)}
