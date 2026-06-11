"""Semantic callback scoring between the opening and the final line."""

from __future__ import annotations

import re

STOPWORDS = {"the", "and", "for", "that", "this", "with", "from", "into", "your", "why", "how", "what"}


def _sentences(text: object) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "")) if part.strip()]


def _keywords(text: object) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9][a-z0-9'-]*", str(text or "").lower())
        if word not in STOPWORDS and len(word) > 3
    }


def score_loop_semantics(script: str, hook: str = "") -> dict:
    sentences = _sentences(script)
    opening = hook or (sentences[0] if sentences else "")
    ending = sentences[-1] if sentences else ""
    opening_terms = _keywords(opening)
    ending_terms = _keywords(ending)
    overlap = sorted(opening_terms & ending_terms)
    all_terms = opening_terms | ending_terms
    callback_keyword_overlap = round(len(overlap) / max(len(all_terms), 1), 4)
    mentions = 0
    for sentence in sentences:
        if _keywords(sentence) & opening_terms:
            mentions += 1
    loop_density = round(mentions / max(len(sentences), 1), 4)
    score = 45 + callback_keyword_overlap * 120 + min(22, loop_density * 35)
    if ending and ending.endswith("?"):
        score += 8
    state = "live_loop" if score >= 70 else ("thin_loop" if score >= 55 else "dead_ending")
    return {
        "score": round(max(0, min(100, score)), 2),
        "state": state,
        "opening_terms": sorted(opening_terms),
        "ending_terms": sorted(ending_terms),
        "callback_keywords": overlap,
        "callback_keyword_overlap": callback_keyword_overlap,
        "loop_density": loop_density,
        "opening_line": opening,
        "final_line": ending,
    }
