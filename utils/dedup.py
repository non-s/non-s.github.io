"""
utils/dedup.py — Title deduplication utilities for GlobalBR News.
Pure functions, no global state, no external deps.
"""
from __future__ import annotations

import re

# Precompiled — used in every title_similarity call
_NON_WORD_RE = re.compile(r'[^\w\s]')
_STOP_WORDS = frozenset({
    'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
    'but', 'is', 'was', 'are', 'were', 'be', 'been', 'by', 'from', 'with',
    'this', 'that', 'it',
})


def levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def titles_too_similar(t1: str, t2: str) -> bool:
    """Return True if two titles are too similar (Jaccard or Levenshtein)."""
    t1, t2 = t1.lower().strip(), t2.lower().strip()
    w1, w2 = set(t1.split()), set(t2.split())
    if w1 and w2 and len(w1 & w2) / len(w1 | w2) > 0.65:
        return True
    if max(len(t1), len(t2)) < 80:
        distance = levenshtein(t1[:60], t2[:60])
        similarity = 1 - distance / max(len(t1[:60]), len(t2[:60]), 1)
        if similarity > 0.75:
            return True
    return False


def title_similarity(t1: str, t2: str) -> float:
    """Returns 0.0-1.0 Jaccard similarity ignoring stopwords."""
    w1 = set(_NON_WORD_RE.sub('', t1.lower()).split()) - _STOP_WORDS
    w2 = set(_NON_WORD_RE.sub('', t2.lower()).split()) - _STOP_WORDS
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)
