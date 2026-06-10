"""Automatic, safe YouTube comment replies for Wild Brief."""
from __future__ import annotations

import re

from utils.comment_intelligence import clean_comment

BLOCKED_TERMS = {
    "http", "www.", "crypto", "telegram", "whatsapp", "onlyfans",
    "subscribe to me", "sub4sub", "kill yourself",
}


def is_replyable_comment(text: str) -> bool:
    cleaned = clean_comment(text)
    lower = cleaned.lower()
    if not cleaned or len(cleaned) > 420:
        return False
    if any(term in lower for term in BLOCKED_TERMS):
        return False
    if re.search(r"[/\\]block\b|[/\\]skip\b", lower):
        return False
    return True


def _subject_from_meta(meta: dict) -> str:
    for key in ("category", "series", "story_format"):
        value = " ".join(str(meta.get(key) or "").replace("_", " ").split()).strip()
        if value:
            return value[:40]
    return "nature"


def build_reply_text(comment_text: str, video_meta: dict | None = None) -> str:
    """Return a concise first-person reply that does not overpromise."""
    text = clean_comment(comment_text)
    lower = text.lower()
    meta = video_meta or {}
    subject = _subject_from_meta(meta)

    if "?" in text or re.search(r"\b(why|how|what|can you|do one|next)\b", lower):
        reply = (
            f"Great question. I am adding this to the Wild Brief idea list. "
            f"{subject.title()} has a lot more weird science to unpack."
        )
    elif re.search(r"\b(wrong|fake|not true|source|actually)\b", lower):
        reply = (
            "Good catch. I will double-check the wording and sources before "
            "turning this into a follow-up."
        )
    elif re.search(r"\b(love|cool|wow|amazing|wild|nice|great)\b", lower):
        reply = (
            "Right? That tiny detail is exactly why I like this format. "
            "More wild nature clues are coming."
        )
    else:
        reply = (
            "Thanks for watching. I am using the comments to pick the next "
            "Wild Brief subjects."
        )
    return reply[:450]
