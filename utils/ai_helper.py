"""
utils/ai_helper.py — AI text generation and content analysis for GlobalBR News.
Uses Groq (primary) → Gemini 2.5 Flash (fallback) → Pollinations.ai (free fallback).
"""
import ast
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

_GROQ_API_URL          = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL            = "llama-3.3-70b-versatile"
_GEMINI_API_URL        = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
_POLLINATIONS_TEXT_URL = "https://text.pollinations.ai/"

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


def _call_groq(sys_msg: str, prompt: str, timeout: int, groq_key: str) -> str:
    r = _session.post(
        _GROQ_API_URL,
        json={
            "model": _GROQ_MODEL,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 3000,
        },
        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_gemini(sys_msg: str, prompt: str, timeout: int, gemini_key: str) -> str:
    r = _session.post(
        f"{_GEMINI_API_URL}?key={gemini_key}",
        json={
            "contents": [{"parts": [{"text": f"{sys_msg}\n\n{prompt}"}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2000},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _call_pollinations(sys_msg: str, prompt: str, timeout: int, seed: int) -> str:
    r = _session.post(
        _POLLINATIONS_TEXT_URL,
        json={
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user",   "content": prompt},
            ],
            "model":      "openai",
            "seed":       seed or abs(hash(prompt)) % 9999,
            "private":    True,
            "max_tokens": 3000,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    # Pollinations sometimes returns a Python-repr'd dict (single quotes,
    # reasoning model envelope) instead of JSON. Try JSON first, then
    # fall back to literal_eval, then to the raw text body.
    body = r.text
    data: object
    try:
        data = r.json()
    except ValueError:
        try:
            data = ast.literal_eval(body)
        except (ValueError, SyntaxError):
            return body.strip()
    if isinstance(data, dict):
        if "choices" in data:
            try:
                return data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                pass
        # Reasoning-model envelope: {'role': 'assistant', 'content': '...', 'reasoning': '...'}
        if "content" in data and isinstance(data["content"], str):
            return data["content"].strip()
    return str(data).strip()


def ai_text(prompt: str, system: str = "", seed: int = 0, timeout: int = 30) -> str:
    """
    Generate text via Groq → Gemini 1.5 Flash → Pollinations.ai (all free tiers).
    Each provider retried up to 2 times with backoff before falling back.
    Returns empty string if all providers fail.
    """
    sys_msg = system or (
        "You are a world-class AP-style journalist and SEO expert. "
        "Write in plain, direct news style. Never use: 'crucial', 'vital', 'pivotal', "
        "'delve', 'It is worth noting', 'It is important to', 'landscape', 'game-changer', "
        "'revolutionary', 'groundbreaking'. Always start with the most important fact. "
        "Be concise and factually accurate."
    )

    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        # 2 attempts max with short backoff: when Groq is rate-limited it stays
        # rate-limited for the whole run, so a long wait just bleeds the job
        # timeout. Better to fail fast to the next provider.
        for attempt in range(2):
            try:
                return _call_groq(sys_msg, prompt, timeout, groq_key)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 429:
                    if attempt == 0:
                        log.warning("Groq rate limited (429) — quick retry in 3s")
                        sleep(3)
                    else:
                        log.warning("Groq rate limited (429) — giving up, falling back to Gemini")
                        break
                elif status in (500, 502, 503, 504):
                    if attempt == 0:
                        log.warning(f"Groq server error {status} — retry in 2s")
                        sleep(2)
                    else:
                        log.warning(f"Groq server error {status} — falling back to Gemini")
                        break
                else:
                    log.warning(f"Groq HTTP error {status} — falling back to Gemini")
                    break
            except Exception as exc:
                log.warning(f"Groq error (attempt {attempt+1}/2): {exc}")
                if attempt == 0:
                    time.sleep(2)

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        for attempt in range(2):
            try:
                return _call_gemini(sys_msg, prompt, timeout, gemini_key)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 429:
                    if attempt == 0:
                        log.warning("Gemini rate limited (429) — quick retry in 3s")
                        sleep(3)
                    else:
                        log.warning("Gemini rate limited (429) — giving up, falling back to Pollinations")
                        break
                elif status in (500, 502, 503, 504):
                    if attempt == 0:
                        log.warning(f"Gemini server error {status} — retry in 2s")
                        sleep(2)
                    else:
                        log.warning(f"Gemini server error {status} — falling back to Pollinations")
                        break
                else:
                    log.warning(f"Gemini HTTP error {status} — falling back to Pollinations")
                    break
            except Exception as exc:
                log.warning(f"Gemini error (attempt {attempt+1}/2): {exc}")
                if attempt == 0:
                    time.sleep(2)

    for attempt in range(2):
        try:
            return _call_pollinations(sys_msg, prompt, timeout, seed)
        except Exception as exc:
            log.warning(f"Pollinations error (attempt {attempt+1}/2): {exc}")
            if attempt == 0:
                time.sleep(5)
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
