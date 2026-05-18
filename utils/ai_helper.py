"""
utils/ai_helper.py — AI text generation and content analysis.

Primary: Mistral La Plateforme (free tier, 500k tokens/mo, ~1 RPS).
Fallback: Cerebras (OpenAI-compatible, 1M tokens/DAY free at 30 RPM)
— kicks in transparently when Mistral 429s through its retries. Set
CEREBRAS_API_KEY to enable; without it the fallback is skipped and
behaviour matches the pre-fallback world.
"""
import logging
import os
import re
import threading
import time
from time import sleep

import requests

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({"User-Agent": "GlobalBR-News-Bot/4.0 (+https://youtube.com/@globalbrnews)"})

_MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
_MISTRAL_MODEL   = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")

# Cerebras has a 1M token/day free tier and uses an OpenAI-compatible
# API at api.cerebras.ai/v1. We call it ONLY after Mistral exhausts its
# 3 retries on 429 — it's the "we ran out of free tier on the primary,
# don't drop the story" parachute.
_CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
_CEREBRAS_MODEL   = os.environ.get("CEREBRAS_MODEL", "llama-3.3-70b")

# Mistral free tier is nominally 1 request/second but sustained traffic
# hits 429 well before that. 8s gives a comfortable 8x margin over the
# documented limit — costs ~7 min per 50-post run but eliminates the
# retry-and-drop loop entirely. Override via MISTRAL_MIN_INTERVAL env.
_MIN_INTERVAL    = float(os.environ.get("MISTRAL_MIN_INTERVAL", "8.0"))
_call_lock       = threading.Lock()
_last_call_ts    = 0.0

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


def _throttle() -> None:
    """Block until at least _MIN_INTERVAL seconds have passed since last call."""
    global _last_call_ts
    with _call_lock:
        elapsed = time.time() - _last_call_ts
        if 0 < elapsed < _MIN_INTERVAL:
            sleep(_MIN_INTERVAL - elapsed)
        _last_call_ts = time.time()


def _call_mistral(sys_msg: str, prompt: str, timeout: int, key: str, json_mode: bool = False) -> str:
    _throttle()
    payload: dict = {
        "model": _MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 3000,
    }
    if json_mode:
        # Forces Mistral to emit syntactically valid JSON. Eliminates the
        # "Expecting ',' delimiter" / unescaped-quote / trailing-comma
        # class of parse errors that were sinking entire posts at the
        # quality gate. Requires a 'json' word somewhere in the messages
        # (we already say "JSON" in the user prompt for these calls).
        payload["response_format"] = {"type": "json_object"}
    r = _session.post(
        _MISTRAL_API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_cerebras(sys_msg: str, prompt: str, timeout: int, key: str, json_mode: bool = False) -> str:
    """
    Drop-in OpenAI-compatible call to Cerebras as a Mistral fallback.
    Same payload shape, same response shape — `choices[0].message.content`.

    Note: Cerebras free tier is 30 req/min, but it does NOT enforce the
    8-second throttle Mistral does. We still call _throttle() to share
    the rate budget — both providers benefit from the spacing if we're
    failing-over often.
    """
    _throttle()
    payload: dict = {
        "model": _CEREBRAS_MODEL,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 3000,
    }
    if json_mode:
        # Cerebras supports the same OpenAI-style response_format flag.
        payload["response_format"] = {"type": "json_object"}
    r = _session.post(
        _CEREBRAS_API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def ai_text(prompt: str, system: str = "", seed: int = 0, timeout: int = 30, json_mode: bool = False) -> str:
    """
    Generate text via Mistral La Plateforme (free tier).
    Up to 3 attempts with backoff on rate limit / transient errors.
    `seed` is accepted for backward compatibility but ignored — Mistral
    doesn't expose seed control via the standard chat API.
    Returns empty string on persistent failure.
    """
    sys_msg = system or (
        "You are a senior news writer who explains the world the way a "
        "knowledgeable friend would — clearly, with specifics, in plain "
        "modern English. Use contractions naturally ('it's', 'don't', "
        "'they're'). Prefer short concrete sentences over long abstract "
        "ones. Lead with the most important fact. "
        "NEVER use these AI-tell phrases or words: 'crucial', 'vital', "
        "'pivotal', 'delve', 'landscape', 'game-changer', 'revolutionary', "
        "'groundbreaking', 'underscores the importance', 'sheds light on', "
        "'highlights the critical role', 'in this article', 'in this report', "
        "'it is worth noting', 'it is important to', 'navigate the complexities', "
        "'could reshape', 'paradigm shift', 'unprecedented', 'paves the way', "
        "'in the realm of', 'in today's fast-paced', 'a testament to', "
        "'tapestry', 'embark on', 'ushering in', 'reshape the future'. "
        "Be accurate, specific, and human."
    )

    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        log.error("MISTRAL_API_KEY not set — cannot generate AI text")
        return ""

    mistral_failed_with = None  # tracked so we know whether to try Cerebras
    for attempt in range(3):
        try:
            return _call_mistral(sys_msg, prompt, timeout, key, json_mode=json_mode)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            mistral_failed_with = status
            if status == 429:
                # Respect Retry-After header when present, otherwise back off
                # exponentially. Mistral's free tier sometimes serves bursts
                # of 429s, so the wait needs a real ceiling.
                hdr = (e.response.headers.get("Retry-After") if e.response is not None else None) or "0"
                try:
                    retry_after = int(float(hdr))
                except (TypeError, ValueError):
                    retry_after = 0
                wait = max(retry_after, 5 * (attempt + 1))
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
            mistral_failed_with = "exception"
            log.warning(f"Mistral error (attempt {attempt+1}/3): {exc}")
            if attempt < 2:
                time.sleep(3)

    # ── Fallback: Cerebras (1M tokens/day free, OpenAI-compatible) ──
    # Only worth trying when Mistral failed for a reason Cerebras might
    # not share — 429 (quota) or 5xx (provider outage). For other
    # statuses (e.g. 400 = bad prompt) Cerebras would also reject, so
    # we don't waste the call.
    cerebras_key = os.environ.get("CEREBRAS_API_KEY", "")
    transient_failure = (
        mistral_failed_with == 429
        or mistral_failed_with in (500, 502, 503, 504)
        or mistral_failed_with == "exception"
    )
    if cerebras_key and transient_failure:
        for attempt in range(2):
            try:
                log.info(f"Falling back to Cerebras after Mistral {mistral_failed_with}")
                return _call_cerebras(sys_msg, prompt, timeout, cerebras_key, json_mode=json_mode)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 429 and attempt < 1:
                    log.warning(f"Cerebras 429 — retry in 5s (attempt {attempt+1}/2)")
                    sleep(5)
                    continue
                log.warning(f"Cerebras HTTP {status} — giving up on this story")
                break
            except Exception as exc:
                log.warning(f"Cerebras error (attempt {attempt+1}/2): {exc}")
                if attempt < 1:
                    sleep(3)
    elif transient_failure:
        log.info("CEREBRAS_API_KEY not set — no fallback path. Set it to add a 1M tok/day cushion.")

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
