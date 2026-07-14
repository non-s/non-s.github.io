#!/usr/bin/env python3
"""Mark queue stories consumed when upload evidence already exists."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

QUEUE_PATH = Path("_data/stories_queue.json")
UPLOAD_INTENTS_PATH = Path("_data/upload_intents.jsonl")
DONE_GLOBS = ("_videos/*.done", "_videos_pt-BR/*.done")


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return data if isinstance(data, type(default)) else default


def _uploaded_from_intents(path: Path) -> dict[str, dict]:
    uploaded: dict[str, dict] = {}
    if not path.exists():
        return uploaded
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict) or str(row.get("status") or "").lower() != "uploaded":
            continue
        story_id = str(row.get("story_id") or "").strip()
        if not story_id:
            continue
        uploaded[story_id] = {
            "uploaded_at": str(row.get("created_at") or ""),
            "video_id": str(row.get("video_id") or ""),
            "source": "upload_intents",
        }
    return uploaded


def _uploaded_from_done_markers(root: Path) -> dict[str, dict]:
    uploaded: dict[str, dict] = {}
    for pattern in DONE_GLOBS:
        for path in root.glob(pattern):
            marker = _read_json(path, {})
            story_id = str(marker.get("story_id") or marker.get("id") or "").strip()
            if not story_id:
                continue
            uploaded[story_id] = {
                "uploaded_at": str(
                    marker.get("uploaded_at")
                    or marker.get("published_at")
                    or marker.get("created_at")
                    or marker.get("publish_ts_utc")
                    or ""
                ),
                "video_id": str(marker.get("video_id") or ""),
                "source": path.as_posix(),
            }
    return uploaded


def uploaded_story_records(root: Path) -> dict[str, dict]:
    uploaded = _uploaded_from_done_markers(root)
    uploaded.update(_uploaded_from_intents(root / UPLOAD_INTENTS_PATH))
    return uploaded


def reconcile_queue_uploads(root: Path) -> dict:
    queue_path = root / QUEUE_PATH
    queue = _read_json(queue_path, {"stories": []})
    stories = queue.get("stories") if isinstance(queue, dict) else []
    if not isinstance(stories, list):
        stories = []
    uploaded = uploaded_story_records(root)
    now = datetime.now(timezone.utc).isoformat()
    changed = 0
    for story in stories:
        if not isinstance(story, dict):
            continue
        story_id = str(story.get("id") or story.get("story_id") or "").strip()
        if not story_id or story_id not in uploaded:
            continue
        record = uploaded[story_id]
        if story.get("consumed") and story.get("uploaded_video_id"):
            continue
        story["consumed"] = True
        story["consumed_at"] = story.get("consumed_at") or record.get("uploaded_at") or now
        story["consumed_reason"] = "uploaded_reconciliation"
        if record.get("video_id"):
            story["uploaded_video_id"] = record["video_id"]
        story["upload_reconciliation"] = {
            "source": record.get("source") or "",
            "video_id": record.get("video_id") or "",
        }
        changed += 1
    if changed:
        queue["stories"] = stories
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    pending = sum(1 for story in stories if isinstance(story, dict) and not story.get("consumed"))
    return {"changed": changed, "pending": pending, "uploaded_records": len(uploaded)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = reconcile_queue_uploads(Path(args.root).resolve())
    print(
        "reconcile_queue_uploads: "
        f"{result['changed']} consumed, {result['pending']} pending, "
        f"{result['uploaded_records']} uploaded record(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
