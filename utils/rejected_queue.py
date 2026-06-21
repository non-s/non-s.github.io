"""Persistent quarantine for rejected queue candidates."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REJECTED_QUEUE = Path("_data/rejected_queue.jsonl")
LEGACY_REJECTED_QUEUE = Path("_data/rejected_queue.json")


def _read_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                items.append(item)
        except Exception:
            continue
    return items


def _read_legacy(path: Path | None = None) -> list[dict]:
    path = path or LEGACY_REJECTED_QUEUE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return list(data.get("items") or [])
    except Exception:
        pass
    return []


def _read(path: Path | None = None) -> list[dict]:
    path = path or REJECTED_QUEUE
    if path.suffix == ".jsonl":
        items = _read_jsonl(path)
        if items:
            return items
        return _read_legacy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return list(data.get("items") or [])
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def _script_key(script: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(script or "").lower()).strip()


def _story_angle_key(story: dict) -> str:
    try:
        from utils.packaging import extract_action, extract_animal, extract_cue  # noqa: PLC0415

        return "|".join(
            (
                extract_animal(story).lower(),
                extract_action(story).lower(),
                extract_cue(story).lower(),
                str(story.get("category") or "").lower(),
            )
        )
    except Exception:
        return ""


def record_rejection(
    story: dict, reasons: list[str], *, path: Path | None = None, stage: str = "queue_quality"
) -> None:
    if not reasons:
        return
    path = path or REJECTED_QUEUE
    items = _read(path)
    story_id = str(story.get("id") or story.get("_queue_id") or story.get("title") or "")
    items = [item for item in items if not (item.get("story_id") == story_id and item.get("stage") == stage)]
    quality_repair = story.get("_queue_quality_repair") if isinstance(story.get("_queue_quality_repair"), dict) else {}
    queue_repair = story.get("queue_repair") if isinstance(story.get("queue_repair"), dict) else {}
    local_rewrite = story.get("local_rewrite") if isinstance(story.get("local_rewrite"), dict) else {}
    rewrite_attempted = bool(
        quality_repair.get("attempted") or queue_repair.get("attempted") or local_rewrite.get("applied")
    )
    rewrite_applied = bool(quality_repair.get("applied") or queue_repair.get("applied") or local_rewrite.get("applied"))
    script_key = _script_key(story.get("script"))
    angle_key = _story_angle_key(story)
    items.append(
        {
            "story_id": story_id,
            "stage": stage,
            "reasons": list(dict.fromkeys(str(r) for r in reasons)),
            "title": story.get("seo_title") or story.get("title") or "",
            "category": story.get("category") or "",
            "script_key": script_key,
            "angle_key": angle_key,
            "source_url": story.get("url") or story.get("source_url") or "",
            "pexels_video_id": story.get("pexels_video_id") or "",
            "source_clip_id": story.get("source_clip_id") or "",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "rewrite_attempted": rewrite_attempted,
            "rewrite_applied": rewrite_applied,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".jsonl":
        lines = [json.dumps(item, ensure_ascii=False) for item in items[-1000:]]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    else:
        payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "items": items[-500:]}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_rejections(path: Path | None = None) -> list[dict]:
    return _read(path)
