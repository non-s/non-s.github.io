"""Durable handoff queue for linking Shorts to a relevant long-form session.

The YouTube API does not expose every Studio related-video surface.  Rather
than silently losing the intent, every upload is recorded here for the
operator/Studio step that attaches the appropriate long video to each Short.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from utils.paths import data_dir
from utils.state_lock import state_lock

_MAX_ENTRIES = 300


def _queue_file() -> Path:
    return data_dir() / "content_funnel_queue.json"


def record_funnel_candidate(video_id: str, meta: dict) -> None:
    """Record an uploaded asset for a deliberate Short-to-long-form link."""
    if not video_id:
        return
    kind = str(meta.get("kind", "")).lower()
    entry = {
        "video_id": video_id,
        "title": str(meta.get("title", ""))[:100],
        "scene": str(meta.get("scene", "")),
        "mood": str(meta.get("mood", "")),
        "uploaded_at": datetime.now(UTC).isoformat(),
        "status": "needs_related_long" if kind == "short" else "available_long_form",
    }
    queue_file = _queue_file()
    with state_lock(queue_file):
        try:
            data = json.loads(queue_file.read_text(encoding="utf-8")) if queue_file.exists() else {}
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        bucket = "shorts_needing_link" if kind == "short" else "long_form_targets"
        entries = [item for item in data.get(bucket, []) if item.get("video_id") != video_id]
        entries.insert(0, entry)
        data[bucket] = entries[:_MAX_ENTRIES]
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def recommended_long_form_id(meta: dict) -> str | None:
    """Choose the newest compatible long-form target, if one is available."""
    try:
        data = json.loads(_queue_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    targets = data.get("long_form_targets", []) if isinstance(data, dict) else []
    if not isinstance(targets, list):
        return None
    mood = str(meta.get("mood", "")).lower()
    scene = str(meta.get("scene", "")).lower()
    for target in targets:
        if not isinstance(target, dict):
            continue
        target_mood = str(target.get("mood", "")).lower()
        target_scene = str(target.get("scene", "")).lower()
        if mood and mood == target_mood or scene and scene == target_scene:
            video_id = target.get("video_id")
            return str(video_id) if video_id else None
    for target in targets:
        if isinstance(target, dict) and target.get("video_id"):
            return str(target["video_id"])
    return None


def append_related_video_cta(description: str, meta: dict) -> tuple[str, str | None]:
    """Append one clear Short-to-long CTA when a verified target exists."""
    if str(meta.get("kind", "")).lower() != "short":
        return description, None
    target_id = recommended_long_form_id(meta)
    if not target_id:
        return description, None
    url = f"https://www.youtube.com/watch?v={target_id}"
    if url in description:
        return description, target_id
    cta = f"Watch the matching full Liquid Wire session: {url}"
    return f"{description.rstrip()}\n\n{cta}", target_id
