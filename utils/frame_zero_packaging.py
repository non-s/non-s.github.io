"""Frame-zero packaging helpers for Shorts safe areas."""

from __future__ import annotations


def safe_area_4x5(width: int = 1080, height: int = 1920) -> dict:
    target_h = int(width * 5 / 4)
    top = max(0, (height - target_h) // 2)
    return {"x": 0, "y": top, "w": width, "h": min(target_h, height), "aspect": "4:5"}


def score_frame_zero(meta: dict | None = None) -> dict:
    meta = meta or {}
    text = str(meta.get("thumbnail_text") or meta.get("cover_text") or "")
    words = [word for word in text.split() if word]
    score = 62
    if 2 <= len(words) <= 4:
        score += 22
    elif len(words) > 5:
        score -= 18
    if meta.get("has_broll") or meta.get("visual_ctr"):
        score += 10
    if meta.get("opening_audit", {}).get("score", 0) >= 78:
        score += 8
    return {
        "score": max(0, min(100, score)),
        "safe_area": safe_area_4x5(),
        "first_frame_preview": str(meta.get("first_frame_preview") or "first_frame_preview.png"),
        "word_count": len(words),
        "approved": score >= 72,
    }
