#!/usr/bin/env python3
"""Dry-run publish scoring without rendering/uploading."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.queue_pruner import enriched_score

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/dry_run_publish.json")


def _autonomy_priority(story: dict, queue_score: float) -> float:
    autonomy = story.get("autonomy") or {}
    try:
        priority = float(autonomy.get("priority", 0) or 0)
    except Exception:
        priority = 0.0
    return priority if priority > 0 else float(queue_score or 0)


def build_dry_run(data: dict) -> dict:
    items = []
    for story in data.get("stories") or []:
        if story.get("consumed"):
            continue
        enriched = enriched_score(story)
        rights = enriched["rights_audit"]
        if enriched["state"] == "publish_ready" and rights["approved"]:
            autonomy = story.get("autonomy") or {}
            items.append({
                "id": story.get("id", ""),
                "title": enriched["story"].get("seo_title") or enriched["story"].get("title") or "",
                "category": enriched["story"].get("category", ""),
                "queue_score": enriched["score"],
                "autonomy_priority": _autonomy_priority(story, enriched["score"]),
                "autonomy_lane": autonomy.get("lane", ""),
                "hypothesis_id": autonomy.get("hypothesis_id", ""),
                "packaging_lab": autonomy.get("packaging_lab") or {},
                "publish_score": enriched["publish_score"],
                "youtube_brain": enriched["youtube_brain"],
                "packaging": enriched["packaging"],
                "rights_audit": rights,
            })
    items = sorted(
        items,
        key=lambda item: (float(item.get("autonomy_priority", 0) or 0), float(item.get("queue_score", 0) or 0)),
        reverse=True,
    )
    return {
        "would_publish": items[:10],
        "eligible_count": len(items),
        "selection_rule": "autonomy_priority first, queue_score as tie-breaker",
    }


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    payload = build_dry_run(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"dry_run_publish: {payload['eligible_count']} eligible candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
