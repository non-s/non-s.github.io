"""Single source of truth for legacy platform terms banned from the repo.

The YouTube focus audit (tests/test_youtube_focus_audit.py) fails the
build when any of these terms appears in tracked text or data files.
Terms are assembled by concatenation so this module never matches its
own blocklist.
"""

from __future__ import annotations

import re

# Terms from abandoned platforms/providers that must not reappear in
# code, docs or generated data. Keep in sync with nothing — the focus
# audit imports this tuple directly.
BLOCKED_TERMS: tuple[str, ...] = (
    "tik" + "tok",
    "f" + "yp",
    "for" + "you",
    "cat" + "tok",
    "dog" + "tok",
    "bird" + "tok",
    "farm" + "tok",
    "@wildbrief" + "_x",
    "feed" + "parser",
    "feed_" + "cache",
    "feed_" + "health",
    "pol" + "linations",
    "na" + "sa",
)

# The space-agency acronym only counts as a whole word; the other terms
# are unambiguous substrings.
_WORD_BOUNDARY_TERMS = {"na" + "sa"}

# Neutral stand-ins keep scrubbed sentences readable; terms without an
# entry are simply removed.
_REPLACEMENTS = {"na" + "sa": "space agency"}

_SCRUB_RES = [
    (
        re.compile(
            (r"\b" + re.escape(term) + r"\b") if term in _WORD_BOUNDARY_TERMS else re.escape(term), re.IGNORECASE
        ),
        _REPLACEMENTS.get(term, ""),
    )
    for term in BLOCKED_TERMS
]


def matches_blocked_term(text: str, term: str) -> bool:
    """Return True when `term` occurs in `text` under audit rules."""
    if term in _WORD_BOUNDARY_TERMS:
        return re.search(r"\b" + re.escape(term) + r"\b", text) is not None
    return term in text


def scrub_legacy_terms(text: str) -> str:
    """Remove blocked terms from text that will be persisted to _data.

    Rejection logs and other generated artifacts must never carry these
    terms or the focus audit turns red long after the fact.
    """
    out = str(text or "")
    for pattern, replacement in _SCRUB_RES:
        out = pattern.sub(replacement, out)
    return re.sub(r"[ \t]{2,}", " ", out)
