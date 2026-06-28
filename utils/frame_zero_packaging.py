"""Frame-zero packaging helpers for Shorts safe areas."""

from __future__ import annotations

import re

from utils.curiosity_angles import build_curiosity_package, is_generic_movement_copy

GENERIC_FRAME_ZERO_RE = re.compile(
    r"\b(?:detect changes with (?:their|its)|show why the [a-z ]+ matters|"
    r"read the moment from one|one visible signal|before the payoff|hidden cue|final move)\b",
    re.I,
)


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


def _story_text(story: dict) -> str:
    parts = [
        str(story.get(key) or "")
        for key in (
            "seo_title",
            "title",
            "hook",
            "script",
            "lead",
            "thumbnail_text",
            "category",
            "topic_hashtag",
            "source_title",
            "raw_title",
        )
    ]
    tags = story.get("yt_tags") or story.get("tags") or []
    if isinstance(tags, list):
        parts.extend(str(tag or "") for tag in tags)
    else:
        parts.append(str(tags or ""))
    return " ".join(parts)


def needs_frame_zero_repair(story: dict) -> bool:
    """Return True when the visible opening copy is too generic for Shorts."""
    source = str(story.get("source") or "").strip().lower()
    production_mode = str(story.get("production_mode") or "").strip().lower()
    if source in {"remake factory", "youtube comment idea"} or production_mode == "remake_factory":
        return False
    text = _story_text(story)
    local_method = str((story.get("local_rewrite") or {}).get("method") or "").strip().lower()
    deterministic_source = (
        production_mode == "deterministic_subject_fallback" or local_method == "deterministic_subject_fallback"
    )
    return bool(GENERIC_FRAME_ZERO_RE.search(text) or (deterministic_source and is_generic_movement_copy(text)))


def apply_frame_zero_repair(story: dict) -> dict:
    """Replace generic openings with a concrete subject + visual cue + payoff package."""
    out = dict(story)
    if not needs_frame_zero_repair(out):
        out["frame_zero_packaging"] = score_frame_zero(out)
        return out

    package = build_curiosity_package(out, context=_story_text(out), force=True)
    if not package:
        out["frame_zero_packaging"] = score_frame_zero(out)
        return out

    original_title = str(out.get("seo_title") or out.get("title") or "")
    out.update(
        {
            "seo_title": package["seo_title"],
            "title": package["title"],
            "hook": package["hook"],
            "script": package["script"],
            "lead": package["lead"],
            "thumbnail_text": package["thumbnail_text"],
            "story_format": package["story_format"],
            "yt_tags": package["yt_tags"],
        }
    )
    out["curiosity_angle"] = {
        "key": package["angle_key"],
        "cue": package["cue"],
        "source": "frame_zero_repair",
    }
    out["frame_zero_repair"] = {
        "method": "curiosity_angle_frame_zero_repair",
        "reason": "generic_opening_copy",
        "original_title": original_title,
        "angle_key": package["angle_key"],
        "cue": package["cue"],
    }
    out["frame_zero_packaging"] = score_frame_zero(out)
    return out
