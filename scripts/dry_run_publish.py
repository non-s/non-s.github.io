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


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    items = []
    for story in data.get("stories") or []:
        if story.get("consumed"):
            continue
        enriched = enriched_score(story)
        rights = enriched["rights_audit"]
        if enriched["state"] == "publish_ready" and rights["approved"]:
            items.append({
                "id": story.get("id", ""),
                "title": enriched["story"].get("seo_title") or enriched["story"].get("title") or "",
                "category": enriched["story"].get("category", ""),
                "queue_score": enriched["score"],
                "publish_score": enriched["publish_score"],
                "youtube_brain": enriched["youtube_brain"],
                "packaging": enriched["packaging"],
                "rights_audit": rights,
            })
    items = sorted(items, key=lambda item: item["queue_score"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"would_publish": items[:10], "eligible_count": len(items)}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"dry_run_publish: {len(items)} eligible candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
