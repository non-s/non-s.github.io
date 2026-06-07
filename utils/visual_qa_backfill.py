"""Infer legacy visual QA coverage from uploaded marker metadata."""
from __future__ import annotations

from datetime import datetime, timezone


def infer_marker_visual_qa(marker: dict) -> dict:
    """Return a conservative inferred QA record for legacy markers."""
    qa = marker.get("visual_qa") or {}
    local = marker.get("local_visual_qa") or {}
    if qa.get("checked") or local.get("checked"):
        return {"needs_backfill": False, "inferred": False}
    has_motion = bool(marker.get("has_broll") or marker.get("source_clip_id") or marker.get("pexels_video_id"))
    has_captions = bool(marker.get("has_captions"))
    has_subject = bool(marker.get("category") and marker.get("title"))
    approved = has_motion and has_captions and has_subject
    score = 7 if approved else 4
    missing = []
    if not has_motion:
        missing.append("motion_source")
    if not has_captions:
        missing.append("captions")
    if not has_subject:
        missing.append("subject_metadata")
    return {
        "needs_backfill": True,
        "inferred": True,
        "checked": True,
        "approved": approved,
        "score": score,
        "reason": "legacy_metadata_inference" if approved else "legacy_missing_" + "_".join(missing),
        "missing": missing,
    }


def build_backfill_report(markers: list[dict]) -> dict:
    items = []
    approved = rejected = 0
    for marker in markers:
        inferred = infer_marker_visual_qa(marker)
        if not inferred.get("needs_backfill"):
            continue
        if inferred.get("approved"):
            approved += 1
        else:
            rejected += 1
        items.append({
            "video_id": marker.get("video_id", ""),
            "title": marker.get("title", ""),
            "category": marker.get("category", ""),
            "inferred": inferred,
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "legacy_unchecked": len(items),
        "inferred_approved": approved,
        "inferred_rejected": rejected,
        "items": items[:100],
    }
