"""
utils/ai_helper.py — AI text generation and content analysis for GlobalBR News.
Uses Mistral La Plateforme (free tier, 1B tokens/month, 60 req/min).
"""
import json
import logging
import os
import re
import time
from time import sleep

import requests

from utils.retry import with_retry

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({"User-Agent": "GlobalBR-News-Bot/3.0 (+https://non-s.github.io)"})

_MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
_MISTRAL_MODEL   = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")

_POSITIVE_WORDS = {
    "breakthrough", "success", "discover", "innovation", "growth", "record",
    "victory", "achieve", "advance", "cure", "save", "improve", "rise",
    "hope", "peace", "agreement", "award", "celebrate", "launch", "win",
    "boom", "rally", "recover", "benefit", "progress", "surge", "historic",
}
_NEGATIVE_WORDS = {
    "war", "attack", "kill", "death", "dead", "crisis", "disaster", "collapse",
    "crash", "fall", "fail", "worst", "threat", "danger", "flood", "fire",
    "earthquake", "explosion", "shooting", "murder", "arrest", "ban", "loss",
    "decline", "drop", "recession", "conflict", "violence", "protest", "riot",
    "scandal", "corrupt", "terror", "bomb", "casualt", "injur", "evacuate",
}

_FACT_VERIFIED_PHRASES = {
    "officials confirmed", "according to", "announced", "reported by",
    "confirmed by", "published by", "data shows", "study found",
    "research shows", "percent", "million", "billion",
    "2024", "2025", "2026",
}
_FACT_DEVELOPING_PHRASES = {
    "reportedly", "sources say", "unconfirmed", "alleged", "claims",
    "rumored", "believed to", "said to be", "may have", "might have",
    "anonymous source", "sources close", "could be",
}
_FACT_OPINION_PHRASES = {
    "opinion", "analysis", "commentary", "editorial", "think",
    "perspective", "column", "op-ed", "viewpoint", "argue",
    "believe we should", "it is time to",
}
_FACT_SATIRE_PHRASES = {
    "satire", "parody", "humor", "humour", "spoof", "onion",
    "satirical", "comedic take",
}

BREAKING_KEYWORDS = [
    "breaking", "urgent", "alert", "just in", "developing",
    "just announced", "breaking news", "emergency", "exclusive",
    "war declared", "killed", "attack", "explosion", "crash",
    "earthquake", "tsunami", "coup", "assassination", "outbreak",
]

_SPAM_PATTERNS = re.compile(
    r'\bclick here\b|\byou won\'t believe\b|\bshoking\b|\bshocking\b',
    re.IGNORECASE,
)


def _call_mistral(sys_msg: str, prompt: str, timeout: int, key: str) -> str:
    r = _session.post(
        _MISTRAL_API_URL,
        json={
            "model": _MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 3000,
        },
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def ai_text(prompt: str, system: str = "", seed: int = 0, timeout: int = 30) -> str:
    """
    Generate text via Mistral La Plateforme (free tier).
    Up to 3 attempts with backoff on rate limit / transient errors.
    `seed` is accepted for backward compatibility but ignored — Mistral
    doesn't expose seed control via the standard chat API.
    Returns empty string on persistent failure.
    """
    sys_msg = system or (
        "You are a world-class AP-style journalist and SEO expert. "
        "Write in plain, direct news style. Never use: 'crucial', 'vital', 'pivotal', "
        "'delve', 'It is worth noting', 'It is important to', 'landscape', 'game-changer', "
        "'revolutionary', 'groundbreaking'. Always start with the most important fact. "
        "Be concise and factually accurate."
    )

    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        log.error("MISTRAL_API_KEY not set — cannot generate AI text")
        return ""

    for attempt in range(3):
        try:
            return _call_mistral(sys_msg, prompt, timeout, key)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 429:
                wait = 5 * (attempt + 1)
                if attempt < 2:
                    log.warning(f"Mistral rate limited (429) — retry in {wait}s (attempt {attempt+1}/3)")
                    sleep(wait)
                else:
                    log.warning("Mistral rate limited (429) — giving up after 3 attempts")
                    break
            elif status in (500, 502, 503, 504):
                wait = 3 * (attempt + 1)
                if attempt < 2:
                    log.warning(f"Mistral server error {status} — retry in {wait}s (attempt {attempt+1}/3)")
                    sleep(wait)
                else:
                    log.warning(f"Mistral server error {status} — giving up after 3 attempts")
                    break
            else:
                log.warning(f"Mistral HTTP error {status} — giving up")
                break
        except Exception as exc:
            log.warning(f"Mistral error (attempt {attempt+1}/3): {exc}")
            if attempt < 2:
                time.sleep(3)
    return ""


def sentiment_score(text: str) -> str:
    """Returns 'positive', 'negative', or 'neutral'."""
    words = re.findall(r'\b\w+\b', text.lower())
    pos = sum(1 for w in words if any(w.startswith(p) for p in _POSITIVE_WORDS))
    neg = sum(1 for w in words if any(w.startswith(p) for p in _NEGATIVE_WORDS))
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def fact_check_score(title: str, description: str) -> str | None:
    """Returns 'verified', 'developing', 'opinion', 'satire', or None."""
    combined = (title + " " + description).lower()
    for phrase in _FACT_SATIRE_PHRASES:
        if phrase in combined:
            return "satire"
    for phrase in _FACT_OPINION_PHRASES:
        if phrase in combined:
            return "opinion"
    for phrase in _FACT_DEVELOPING_PHRASES:
        if phrase in combined:
            return "developing"
    for phrase in _FACT_VERIFIED_PHRASES:
        if phrase in combined:
            return "verified"
    return None


def is_breaking_news(title: str, description: str = "") -> bool:
    """Return True if the article appears to be breaking/urgent news."""
    text = (title + " " + description).lower()
    return any(kw in text for kw in BREAKING_KEYWORDS)


def quality_check(title: str, description: str) -> tuple[bool, str]:
    """Returns (ok, reason). Posts failing quality check should be skipped."""
    if len(title) < 15:
        return False, f"title too short ({len(title)} chars)"
    if len(description) < 50:
        return False, f"description too short ({len(description)} chars)"
    if _SPAM_PATTERNS.search(title):
        return False, "spam pattern in title"
    letters = [c for c in title if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.80:
        return False, "title is ALL CAPS"
    return True, ""


# ── Numeric quality score for fine-grained gating ──────────────────
#
# Used as a publish gate after AI enrichment. We don't want a binary
# yes/no on description length anymore — we want to differentiate a
# barebones RSS dump (low score) from a full AI-enhanced post with
# body + key_points + faq (high score). The gate then skips anything
# below a configurable threshold.

_VAGUE_TITLE_RE = re.compile(
    r"^\s*(some|the|a|new|this|that|update|news|breaking)\s+(news|story|item|article)\s*$",
    re.IGNORECASE,
)


def quality_score(
    title: str,
    description: str,
    ai_payload: dict | None = None,
    body_chars: int = 0,
) -> tuple[int, list[str]]:
    """
    Score 0-10. Returns (score, reasons_below_max).

    >= 6  publish (default threshold)
    >= 8  promote to /featured (caller may use)
    <  6  drop with reason logged

    Components:
      * title length + non-vague    (max 2)
      * description length + clean  (max 2)
      * AI body present, ≥400 chars (max 2)
      * AI key_points ≥3            (max 1)
      * AI tl_dr present, sensible  (max 1)
      * AI faq ≥3                   (max 1)
      * Has image OR will get OG    (max 1) — caller injects
    """
    ai = ai_payload or {}
    score = 0
    notes: list[str] = []

    t_clean = (title or "").strip()
    if len(t_clean) >= 25 and not _VAGUE_TITLE_RE.match(t_clean):
        score += 2
    elif len(t_clean) >= 15:
        score += 1
        notes.append("title shortish")
    else:
        notes.append(f"title too short ({len(t_clean)})")
    if _SPAM_PATTERNS.search(t_clean):
        notes.append("title spammy")
        score = max(0, score - 1)

    d_clean = (description or "").strip()
    if len(d_clean) >= 120 and "." in d_clean:
        score += 2
    elif len(d_clean) >= 60:
        score += 1
        notes.append("description shortish")
    else:
        notes.append(f"description too short ({len(d_clean)})")

    body = ai.get("article_body") or ""
    if isinstance(body, str) and len(body) >= 400:
        score += 2
    elif body_chars >= 400:
        score += 1
        notes.append("body via source only, no AI body")
    else:
        notes.append("no substantial body")

    kp = ai.get("key_points") or []
    if isinstance(kp, list) and len([k for k in kp if k]) >= 3:
        score += 1
    else:
        notes.append("no key_points")

    tl = (ai.get("tl_dr") or "").strip()
    if 12 <= len(tl) <= 280:
        score += 1
    else:
        notes.append("no usable tl_dr")

    faq = ai.get("faq") or []
    if isinstance(faq, list) and len(faq) >= 3:
        score += 1
    else:
        notes.append("no FAQ")

    return min(score, 10), notes
