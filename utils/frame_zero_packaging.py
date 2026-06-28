"""Frame-zero packaging helpers for Shorts safe areas."""

from __future__ import annotations

import re

from utils.curiosity_angles import build_curiosity_package, is_generic_movement_copy
from utils.opening_retention import score_retention_opening

OPENING_RETENTION_FLOOR = 82.0
DETERMINISTIC_TIGHTENING_CATEGORIES = {
    "chemistry",
    "conservation",
    "discoveries",
    "earth_from_space",
    "ecosystems",
    "forests",
    "fungi",
    "geology",
    "microscopy",
    "physics",
    "plants",
    "rivers",
    "space",
    "trees",
    "weather",
}

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
    retention_opening = score_retention_opening(meta) if any(meta.get(k) for k in ("hook", "script")) else {}
    if retention_opening:
        if retention_opening["score"] >= 82:
            score += 8
        elif retention_opening["score"] < 68:
            score -= 12
    return {
        "score": max(0, min(100, score)),
        "safe_area": safe_area_4x5(),
        "first_frame_preview": str(meta.get("first_frame_preview") or "first_frame_preview.png"),
        "word_count": len(words),
        "approved": score >= 72,
        "retention_opening": retention_opening,
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


def _deterministic_source(story: dict) -> bool:
    local_method = str((story.get("local_rewrite") or {}).get("method") or "").strip().lower()
    production_mode = str(story.get("production_mode") or "").strip().lower()
    return production_mode == "deterministic_subject_fallback" or local_method == "deterministic_subject_fallback"


def _preserve_opening_source(story: dict) -> bool:
    source = str(story.get("source") or "").strip().lower()
    production_mode = str(story.get("production_mode") or "").strip().lower()
    studio_state = str(story.get("studio_state") or "").strip().lower()
    return (
        source in {"remake factory", "youtube comment idea"}
        or production_mode == "remake_factory"
        or studio_state == "comment_idea"
    )


def needs_frame_zero_repair(story: dict) -> bool:
    """Return True when the visible opening copy is too generic for Shorts."""
    if _preserve_opening_source(story):
        return False
    text = _story_text(story)
    return bool(GENERIC_FRAME_ZERO_RE.search(text) or (_deterministic_source(story) and is_generic_movement_copy(text)))


def _first_sentence_tail(script: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", str(script or "").strip(), maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _because_tail(script: str) -> str:
    match = re.search(r"\bbecause\b\s*(.+)", str(script or ""), flags=re.I)
    if match:
        return match.group(1).strip(" .")
    return _first_sentence_tail(script).strip(" .")


def _frontload_package(package: dict) -> dict:
    """Make the generated angle repeat the visible cue in the first swipe window."""
    out = dict(package)
    subject = str(out.get("subject") or "Nature").strip() or "Nature"
    cue = str(out.get("cue") or "visible cue").strip() or "visible cue"
    lower_subject = subject.lower()
    lower_cue = cue.lower()
    if lower_cue and lower_cue in lower_subject:
        hook = f"{subject} turn one visible pattern into the clue."
    else:
        hook = f"{subject} reveal the {cue} first."
    tail = _because_tail(str(out.get("script") or ""))
    if not tail:
        tail = "that visible cue makes the payoff clear before the viewer swipes"
    script = f"{hook} Watch the {cue} first, because {tail}."
    script = re.sub(r"\s+", " ", script).strip()
    out["hook"] = hook
    out["script"] = script
    out["lead"] = script[:400]
    out["first_2s_narration"] = " ".join(script.split()[:12])
    return out


def _apply_package_fields(story: dict, package: dict) -> dict:
    out = dict(story)
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
            "first_2s_narration": package.get("first_2s_narration") or "",
        }
    )
    out["curiosity_angle"] = {
        "key": package["angle_key"],
        "cue": package["cue"],
        "source": "frame_zero_repair",
    }
    return out


def apply_frame_zero_repair(story: dict) -> dict:
    """Replace generic openings with a concrete subject + visual cue + payoff package."""
    out = dict(story)
    before_view = {key: value for key, value in out.items() if key != "first_2s_narration"}
    before_opening = (
        score_retention_opening(before_view) if any(before_view.get(k) for k in ("hook", "script", "title")) else {}
    )
    generic_repair = needs_frame_zero_repair(out)
    before_score = float(before_opening.get("score") or 100)
    deterministic_tightening_allowed = (
        _deterministic_source(out)
        and str(out.get("category") or "").strip().lower() in DETERMINISTIC_TIGHTENING_CATEGORIES
    )
    low_retention = (
        not _preserve_opening_source(out)
        and (not _deterministic_source(out) or deterministic_tightening_allowed)
        and 70 <= before_score < OPENING_RETENTION_FLOOR
    )
    if not generic_repair and not low_retention:
        out["frame_zero_packaging"] = score_frame_zero(out)
        return out

    package = build_curiosity_package(out, context=_story_text(out), force=True)
    if not package:
        out["frame_zero_packaging"] = score_frame_zero(out)
        return out

    original_title = str(out.get("seo_title") or out.get("title") or "")
    if low_retention and not generic_repair:
        package = _frontload_package(package)
    candidate = _apply_package_fields(out, package)
    after_opening = score_retention_opening(candidate)
    if not generic_repair and float(after_opening.get("score") or 0) < float(before_opening.get("score") or 0):
        out["frame_zero_packaging"] = score_frame_zero(out)
        return out
    out = candidate
    out["frame_zero_repair"] = {
        "method": (
            "curiosity_angle_frame_zero_repair" if generic_repair else "curiosity_angle_frame_zero_retention_rewrite"
        ),
        "reason": "generic_opening_copy" if generic_repair else "opening_retention_below_floor",
        "original_title": original_title,
        "angle_key": package["angle_key"],
        "cue": package["cue"],
        "floor": OPENING_RETENTION_FLOOR,
        "before": before_opening,
        "after": after_opening,
    }
    out["frame_zero_packaging"] = score_frame_zero(out)
    return out
