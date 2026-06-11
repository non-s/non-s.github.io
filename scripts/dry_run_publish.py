#!/usr/bin/env python3
"""Dry-run publish scoring without rendering/uploading."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.queue_pruner import prune_queue

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
    pruned, rejected, prune_summary = prune_queue(data)
    for story in pruned.get("stories") or []:
        if story.get("consumed"):
            continue
        rights = story.get("rights_audit") or {}
        if not rights:
            from utils.rights_audit import audit_rights
            rights = audit_rights(story)
        queue_prune = story.get("queue_prune") or {}
        publish = story.get("publish_score") or {}
        if (
            queue_prune.get("state") == "publish_ready"
            and rights.get("approved") is True
            and publish.get("approved") is True
            and publish.get("state") == "publish_ready"
        ):
            autonomy = story.get("autonomy") or {}
            items.append({
                "id": story.get("id", ""),
                "title": story.get("seo_title") or story.get("title") or "",
                "category": story.get("category", ""),
                "queue_score": queue_prune.get("score", 0),
                "autonomy_priority": _autonomy_priority(story, queue_prune.get("score", 0)),
                "autonomy_lane": autonomy.get("lane", ""),
                "hypothesis_id": autonomy.get("hypothesis_id", ""),
                "packaging_lab": autonomy.get("packaging_lab") or {},
                "publish_score": publish,
                "youtube_brain": story.get("youtube_brain") or {},
                "packaging": story.get("packaging") or {},
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
        "prune_summary": prune_summary,
        "rejected_preview": [
            {
                "id": item["story"].get("id", ""),
                "title": item["story"].get("seo_title") or item["story"].get("title") or "",
                "reasons": item["reasons"],
            }
            for item in rejected[:20]
        ],
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
