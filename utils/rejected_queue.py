"""Persistent quarantine for rejected queue candidates."""

from __future__ import annotations

import json
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


def _read_legacy(path: Path = LEGACY_REJECTED_QUEUE) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return list(data.get("items") or [])
    except Exception:
        pass
    return []


def _read(path: Path = REJECTED_QUEUE) -> list[dict]:
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


def record_rejection(
    story: dict, reasons: list[str], *, path: Path = REJECTED_QUEUE, stage: str = "queue_quality"
) -> None:
    if not reasons:
        return
    items = _read(path)
    story_id = str(story.get("id") or story.get("_queue_id") or story.get("title") or "")
    items = [item for item in items if not (item.get("story_id") == story_id and item.get("stage") == stage)]
    items.append(
        {
            "story_id": story_id,
            "stage": stage,
            "reasons": list(dict.fromkeys(str(r) for r in reasons)),
            "title": story.get("seo_title") or story.get("title") or "",
            "category": story.get("category") or "",
            "source_url": story.get("url") or story.get("source_url") or "",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "rewrite_attempted": False,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".jsonl":
        lines = [json.dumps(item, ensure_ascii=False) for item in items[-1000:]]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    else:
        payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "items": items[-500:]}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_rejections(path: Path = REJECTED_QUEUE) -> list[dict]:
    return _read(path)
