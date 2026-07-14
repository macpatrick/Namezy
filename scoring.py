"""
Brandability scoring step (brief section 6), scoped to a simple 0-100
heuristic: length, syllable/pronunciation estimate, uniqueness (implicit --
survivors of dedupe.py), domain availability bonus, and web-conflict
adjustment. No embeddings/semantic similarity, per the v1 scope.
"""
import re

VOWEL_GROUPS = re.compile(r"[aeiouy]+", re.IGNORECASE)
HARD_CONSONANT_RUN = re.compile(r"[^aeiouy\s]{4,}", re.IGNORECASE)

# Domain availability is weighted heavily (30/18/12) relative to length/pronunciation
# (10 each): Claude is prompted to generate short, pronounceable names, so nearly every
# candidate maxes those two out, and if domain weight were comparable the length+
# pronunciation floor alone (~20) plus any available domain would saturate the 100
# clamp for almost every candidate -- collapsing the ranking. Keeping domain (and web
# conflict) as the dominant factors preserves a real spread.
DOMAIN_WEIGHTS = {"com": 30, "io": 18, "app": 12}


def estimate_syllables(name: str) -> int:
    groups = VOWEL_GROUPS.findall(name)
    return max(1, len(groups))


def length_score(name: str) -> int:
    n = len(name)
    if 4 <= n <= 9:
        return 10
    if n in (3, 10, 11):
        return 6
    if n in (2, 12, 13):
        return 3
    return 0


def pronunciation_score(name: str) -> int:
    syllables = estimate_syllables(name)
    score = 10
    if syllables > 4:
        score -= (syllables - 4) * 2
    if HARD_CONSONANT_RUN.search(name):
        score -= 4
    return max(0, min(10, score))


def domain_bonus(domain_status: dict) -> int:
    best = 0
    for tld, weight in DOMAIN_WEIGHTS.items():
        if domain_status.get(tld) == "available":
            best = max(best, weight)
    return best


def web_conflict_adjustment(web_status: str) -> int:
    if web_status == "conflict":
        return -30
    if web_status == "clear":
        return 20
    return 0  # not_configured / error / unchecked


def compute_score(name: str, domain_status: dict, web_status: str) -> int:
    score = 40
    score += length_score(name)
    score += pronunciation_score(name)
    score += domain_bonus(domain_status or {})
    score += web_conflict_adjustment(web_status)
    return max(0, min(100, score))
