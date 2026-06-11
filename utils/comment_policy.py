"""Comment moderation and comment-to-Short policy helpers."""

from __future__ import annotations

import re

SPAM_TERMS = {"crypto", "giveaway", "telegram", "whatsapp", "http://", "https://", "subscribe back"}


def classify_comment(text: str) -> dict:
    clean = " ".join(str(text or "").split())
    lower = clean.lower()
    if any(term in lower for term in SPAM_TERMS):
        state = "spam"
    elif "?" in clean and len(re.findall(r"[A-Za-z0-9']+", clean)) >= 4:
        state = "short_candidate"
    else:
        state = "reply_ok"
    return {"state": state, "approved": state != "spam", "text": clean[:500]}
