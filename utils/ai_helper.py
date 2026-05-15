"""
utils/ai_helper.py — AI text generation and content analysis for GlobalBR News.
Uses Groq (primary) → Gemini 1.5 Flash (fallback) → Pollinations.ai (free fallback).
"""
import json
import logging
import os
import re
from time import sleep

import requests

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({"User-Agent": "GlobalBR-News-Bot/3.0 (+https://non-s.github.io)"})

_GROQ_API_URL          = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL            = "llama-3.3-70b-versatile"
_GEMINI_API_URL        = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
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


def ai_text(prompt: str, system: str = "", seed: int = 0, timeout: int = 30) -> str:
    """
    Generate text via Groq → Gemini 1.5 Flash → Pollinations.ai (all free tiers).
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
        try:
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
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 429:
                log.warning("Groq rate limited (429) — waiting 30s before Gemini fallback")
                sleep(30)
            else:
                log.warning(f"Groq HTTP error {status} — trying Gemini")
        except Exception as exc:
            log.warning(f"Groq error: {exc}")

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
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
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 429:
                log.warning("Gemini rate limited (429) — waiting 30s before Pollinations fallback")
                sleep(30)
            else:
                log.warning(f"Gemini HTTP error {status} — trying Pollinations")
        except Exception as exc:
            log.warning(f"Gemini error: {exc}")

    try:
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
        data = r.json()
        if isinstance(data, dict) and "choices" in data:
            return data["choices"][0]["message"]["content"].strip()
        return str(data).strip()
    except Exception as exc:
        log.warning(f"Pollinations error: {exc}")
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
