"""Automatic, safe YouTube comment replies for Wild Brief."""
from __future__ import annotations

import re
import hashlib

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


def classify_comment(text: str) -> str:
    lower = clean_comment(text).lower()
    if re.search(r"\b(wrong|fake|not true|source|actually|mistake)\b", lower):
        return "critique"
    if re.search(r"\b(do|cover|make|next|please).{0,40}\b(volcano|fungi|mushroom|shark|forest|ocean|storm|animal|plant)\b", lower):
        return "suggestion"
    if "?" in lower or re.search(r"\b(why|how|what|can you|do one|next)\b", lower):
        return "question"
    if re.search(r"\b(love|cool|wow|amazing|wild|nice|great|beautiful|awesome)\b", lower):
        return "praise"
    return "neutral"


def _pick(options: list[str], seed: str, recent: set[str]) -> str:
    ordered = list(options)
    start = int(hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:8], 16) % len(ordered)
    for idx in range(len(ordered)):
        candidate = ordered[(start + idx) % len(ordered)]
        if candidate not in recent:
            return candidate
    return ordered[start]


def _recent_stems(recent: set[str]) -> set[str]:
    return {" ".join(item.lower().split()[:3]) for item in recent if item}


def build_reply_text(comment_text: str, video_meta: dict | None = None) -> str:
    """Return a concise first-person reply that does not overpromise."""
    text = clean_comment(comment_text)
    meta = video_meta or {}
    subject = _subject_from_meta(meta)
    intent = classify_comment(text)
    recent = set(str(item) for item in (meta.get("recent_reply_texts") or []))
    stems = _recent_stems(recent)
    options = {
        "question": [
            f"Good question. I will only use that angle if I can source it cleanly.",
            f"That one is worth a follow-up if the footage can show the detail clearly.",
            f"I like that question. The visual proof has to come first, then the explanation.",
            f"Adding that to the idea list. {subject.title()} still has a lot to test.",
            "That is exactly the kind of small detail that can carry a Short.",
        ],
        "suggestion": [
            "Added to the queue. I am prioritizing suggestions that have a strong visual cue.",
            f"Noted. {subject.title()} could work well if the footage has motion.",
            "That is a strong lane for Wild Brief. I will watch for a clean source.",
            "Good pick. Short, visual, and easy for people to argue about in a useful way.",
            "Saved. Viewer ideas are helping shape the next batch.",
        ],
        "critique": [
            "Fair note. I will double-check the wording and source before using that angle again.",
            "Good catch. I would rather tighten the claim than overstate the science.",
            "Appreciate the correction. I will treat that as a source-check for a future update.",
            "That is fair. I try to keep these short without stretching the claim.",
            "Thanks for flagging it. Better to be precise than dramatic.",
        ],
        "praise": [
            "Right? That tiny detail is exactly why I like this format.",
            "Glad you caught it. The small visual clues are the fun part.",
            "Thanks for watching. More wild nature clues are coming.",
            "That detail got me too. Nature is very efficient at being strange.",
            "Appreciate it. I am trying to keep these fast but still accurate.",
        ],
        "neutral": [
            "Thanks for watching. I use the comments to pick the next Wild Brief subjects.",
            "Appreciate you being here. More fast nature science is on the way.",
            "Noted. I am tracking which details people want explained next.",
            "Thanks. The best follow-ups usually come from comment threads like this.",
            "Appreciate the signal. I am watching what people replay and ask about.",
        ],
    }
    filtered = [option for option in options[intent] if " ".join(option.lower().split()[:3]) not in stems]
    reply = _pick(filtered or options[intent], f"{text}|{subject}|{intent}", recent)
    return reply[:450]
