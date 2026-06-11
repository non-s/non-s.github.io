"""Promise-to-payoff scoring for short scripts."""

from __future__ import annotations

import re

REVEAL_TERMS = {"because", "so", "actually", "means", "works", "reason", "payoff", "reveals", "survives"}
STOPWORDS = {"the", "and", "this", "that", "with", "from", "into", "because", "actually", "about"}


def _sentences(text: object) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "")) if part.strip()]


def _words(text: object) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9'-]*", str(text or "").lower())


def _keywords(text: object) -> set[str]:
    return {word for word in _words(text) if len(word) > 3 and word not in STOPWORDS}


def score_payoff(script: str, hook: str = "", *, words_per_second: float = 2.8) -> dict:
    """Estimate when the script pays off the opening promise."""
    sentences = _sentences(script)
    promise_terms = _keywords(hook or (sentences[0] if sentences else ""))
    elapsed_words = 0
    reveal_index = None
    reveal_terms: set[str] = set()
    for idx, sentence in enumerate(sentences):
        sentence_words = _words(sentence)
        current = set(sentence_words)
        if current & REVEAL_TERMS or len(current & promise_terms) >= 2:
            reveal_index = idx
            reveal_terms = current
            break
        elapsed_words += len(sentence_words)
    if reveal_index is None:
        reveal_index = max(0, len(sentences) - 1)
        reveal_terms = _keywords(sentences[-1] if sentences else "")
        elapsed_words = sum(len(_words(sentence)) for sentence in sentences[:reveal_index])
    payoff_second = round(elapsed_words / max(words_per_second, 0.1), 2)
    overlap = len(promise_terms & reveal_terms)
    score = 50 + min(25, overlap * 7)
    if 2 <= payoff_second <= 12:
        score += 18
    elif payoff_second > 18:
        score -= 18
    if reveal_terms & REVEAL_TERMS:
        score += 9
    reasons = []
    if payoff_second > 18:
        reasons.append("payoff_too_late")
    if overlap == 0:
        reasons.append("weak_promise_reveal_overlap")
    return {
        "score": round(max(0, min(100, score)), 2),
        "payoff_second": payoff_second,
        "promise_terms": sorted(promise_terms),
        "reveal_terms": sorted((reveal_terms & (promise_terms | REVEAL_TERMS))),
        "reveal_sentence_index": reveal_index,
        "reasons": reasons,
    }
