"""Persistent quarantine for rejected queue candidates."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REJECTED_QUEUE = Path("_data/rejected_queue.json")


def _read(path: Path = REJECTED_QUEUE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def record_rejection(story: dict, reasons: list[str], *, path: Path = REJECTED_QUEUE,
                     stage: str = "queue_quality") -> None:
    if not reasons:
        return
    payload = _read(path)
    items = list(payload.get("items") or [])
    story_id = str(story.get("id") or story.get("_queue_id") or story.get("title") or "")
    items = [
        item for item in items
        if not (item.get("story_id") == story_id and item.get("stage") == stage)
    ]
    items.append({
        "story_id": story_id,
        "stage": stage,
        "reasons": list(dict.fromkeys(str(r) for r in reasons)),
        "title": story.get("seo_title") or story.get("title") or "",
        "category": story.get("category") or "",
        "source_url": story.get("url") or story.get("source_url") or "",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "rewrite_attempted": False,
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "items": items[-500:]}, indent=2, ensure_ascii=False), encoding="utf-8")


def load_rejections(path: Path = REJECTED_QUEUE) -> list[dict]:
    return list((_read(path).get("items") or []))
