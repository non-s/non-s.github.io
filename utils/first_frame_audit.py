"""Cheap first-second opening audit for Shorts."""

from __future__ import annotations

import os
from pathlib import Path


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _words(text: str) -> list[str]:
    return [word for word in str(text or "").replace("\n", " ").split() if word.strip()]


def score_motion_first_1s(metadata: dict | None = None, frames: list[dict] | None = None) -> dict:
    metadata = metadata or {}
    frames = frames or []
    motion_values = [
        _num(frame.get("motion_score")) for frame in frames if isinstance(frame, dict) and frame.get("time", 0) <= 1.2
    ]
    if motion_values:
        score = max(motion_values)
    elif metadata.get("has_broll") or metadata.get("motion_broll"):
        score = 74.0
    else:
        score = 45.0
    return {"score": round(max(0.0, min(100.0, score)), 2), "reason": "motion_first_1s"}


def check_cover_text_budget(text: str) -> dict:
    count = len(_words(text))
    if 2 <= count <= 4:
        score = 100
        reason = "cover_text_target"
    elif count <= 5:
        score = 78
        reason = "cover_text_hard_cap"
    else:
        score = max(0, 78 - (count - 5) * 14)
        reason = "cover_text_too_long"
    return {"score": score, "word_count": count, "reason": reason}


def check_text_safe_zone(boxes: list[dict] | None = None) -> dict:
    boxes = boxes or []
    if not boxes:
        return {"score": 82, "reason": "safe_zone_not_measured", "overlaps": 0}
    overlaps = 0
    for box in boxes:
        y = _num(box.get("y"), 0.5)
        h = _num(box.get("h"), 0.1)
        if y < 0.06 or y + h > 0.94:
            overlaps += 1
    score = max(0, 100 - overlaps * 28)
    return {"score": score, "reason": "safe_zone_checked", "overlaps": overlaps}


def check_contrast_heuristic(metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    contrast = _num(metadata.get("opening_contrast"), 0)
    if not contrast:
        contrast = 72 if metadata.get("thumbnail_text") or metadata.get("cover_text") else 62
    return {"score": round(max(0.0, min(100.0, contrast)), 2), "reason": "contrast_heuristic"}


def explain_opening_failures(audit: dict, min_score: float = 72.0) -> list[str]:
    reasons = []
    if audit.get("score", 0) < min_score:
        reasons.append("opening_score_below_threshold")
    checks = audit.get("checks") or {}
    if (checks.get("cover_text_budget") or {}).get("reason") == "cover_text_too_long":
        reasons.append("cover_text_too_long")
    if (checks.get("safe_zone") or {}).get("overlaps", 0):
        reasons.append("text_outside_safe_zone")
    if (checks.get("motion") or {}).get("score", 0) < 55:
        reasons.append("weak_motion_first_1s")
    if (checks.get("contrast") or {}).get("score", 0) < 55:
        reasons.append("low_opening_contrast")
    return reasons


def audit_opening_frames(
    metadata: dict | None = None,
    *,
    frames: list[dict] | None = None,
    text_boxes: list[dict] | None = None,
    min_score: float | None = None,
) -> dict:
    """Return an explainable opening score without requiring heavy OCR."""
    metadata = metadata or {}
    if os.environ.get("OPENING_AUDIT_ENABLED", "1").strip().lower() in {"0", "false", "no", "off"}:
        return {"enabled": False, "approved": True, "score": 100, "reasons": ["opening_audit_disabled"]}
    min_score = min_score if min_score is not None else _num(os.environ.get("OPENING_MIN_SCORE"), 72)
    cover_text = str(metadata.get("thumbnail_text") or metadata.get("cover_text") or metadata.get("title") or "")
    checks = {
        "motion": score_motion_first_1s(metadata, frames),
        "cover_text_budget": check_cover_text_budget(cover_text),
        "safe_zone": check_text_safe_zone(text_boxes or metadata.get("opening_text_boxes") or []),
        "contrast": check_contrast_heuristic(metadata),
    }
    score = round(
        checks["motion"]["score"] * 0.36
        + checks["cover_text_budget"]["score"] * 0.24
        + checks["safe_zone"]["score"] * 0.20
        + checks["contrast"]["score"] * 0.20,
        2,
    )
    audit = {"enabled": True, "score": score, "checks": checks}
    reasons = explain_opening_failures(audit, min_score)
    strict = os.environ.get("OPENING_AUDIT_STRICT", "0").strip().lower() in {"1", "true", "yes", "on"}
    audit["reasons"] = reasons
    audit["approved"] = not (strict and reasons)
    audit["strict"] = strict
    audit["min_score"] = min_score
    return audit


def audit_video_path(path: Path, metadata: dict | None = None) -> dict:
    """Lightweight path-aware wrapper; absence of a readable video is non-fatal."""
    data = dict(metadata or {})
    data["has_broll"] = bool(path and Path(path).exists()) or bool(data.get("has_broll"))
    return audit_opening_frames(data)
