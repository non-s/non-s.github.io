"""
utils/ranking.py — Pre-AI scoring helpers.

Cheap, deterministic, network-free scorers used to rank RSS entries by
likely-quality before we spend AI quota on them. Living in utils/ so the
test suite can import without pulling in feedparser/requests.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone


_SPAM_HEADLINE_RE = re.compile(
    r"\b(you won.t believe|shocking|secret|trick|hate this|click here|"
    r"viral|here.s why|this is what)\b",
    re.IGNORECASE,
)
_BREAKING_HEADLINE_RE = re.compile(
    r"\b(breaking|urgent|just in|alert|live updates?|exclusive|"
    r"developing|confirmed)\b",
    re.IGNORECASE,
)


def entry_relevance_score(entry) -> float:
    """
    Headline-only score (no AI, no network). Higher = better.

    Components:
      * Substantive title length (sweet spot 50-100 chars).
      * Has a real description (≥120 chars).
      * Has an image attached.
      * Breaking-news verbs in the headline.
      * Penalty for clickbait/spam phrases.
      * Slight recency boost.
    """
    title = (getattr(entry, "title", "") or "").strip()
    try:
        description = (
            getattr(entry, "summary", "") or
            getattr(entry, "description", "") or ""
        )
    except Exception:
        description = ""

    score = 0.0
    n = len(title)
    if 50 <= n <= 100:
        score += 3
    elif 30 <= n < 50 or 100 < n <= 130:
        score += 2
    elif 15 <= n < 30:
        score += 1

    if len(description) >= 120:
        score += 2
    elif len(description) >= 40:
        score += 1

    if (hasattr(entry, "media_content") or
            hasattr(entry, "media_thumbnail") or
            hasattr(entry, "enclosures")):
        score += 1

    if _BREAKING_HEADLINE_RE.search(title):
        score += 2
    if _SPAM_HEADLINE_RE.search(title):
        score -= 3

    # Recency tie-breaker.
    try:
        if getattr(entry, "published_parsed", None):
            from time import mktime
            age_h = (datetime.now(timezone.utc).timestamp() -
                     mktime(entry.published_parsed)) / 3600.0
            if age_h < 6:
                score += 1.5
            elif age_h < 24:
                score += 0.5
    except Exception:
        pass

    return score
