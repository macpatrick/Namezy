"""
Duplicate Eliminator step (brief section 4).

Uses difflib (stdlib) string similarity on a normalized form of each name --
sufficient for catching plural/hyphen/spacing variants and obvious
near-duplicates (e.g. "Pikto" vs "Picto") without needing embeddings.
"""
import difflib
import re

DEFAULT_SIMILARITY_THRESHOLD = 0.80


def normalize(name: str) -> str:
    """Lowercase, strip spacing/hyphen/punctuation, drop a trailing plural 's'."""
    s = name.lower().strip()
    s = re.sub(r"[\s\-_]+", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    if len(s) > 3 and s.endswith("s"):
        s = s[:-1]
    return s


def dedupe_candidates(
    candidates: list[dict], similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> list[dict]:
    """
    candidates: list of {"name": str, "method": str, ...}
    Returns a filtered list (original order, first occurrence wins) with
    exact and near-duplicate names removed.
    """
    seen_norms: list[str] = []
    kept: list[dict] = []

    for candidate in candidates:
        name = (candidate.get("name") or "").strip()
        if not name:
            continue
        norm = normalize(name)
        if not norm:
            continue

        is_duplicate = False
        for seen in seen_norms:
            if norm == seen:
                is_duplicate = True
                break
            ratio = difflib.SequenceMatcher(None, norm, seen).ratio()
            if ratio >= similarity_threshold:
                is_duplicate = True
                break

        if is_duplicate:
            continue

        seen_norms.append(norm)
        kept.append(candidate)

    return kept
