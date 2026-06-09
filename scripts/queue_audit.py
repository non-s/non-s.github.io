#!/usr/bin/env python3
"""Audit pending queue quality and write _data/queue_audit.json."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.publish_score import score_story
from utils.queue_pruner import enriched_score, prune_queue
from utils.rights_audit import audit_rights

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/queue_audit.json")


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    rows = []
    states = Counter()
    rights = Counter()
    _, rejected, prune_summary = prune_queue(data)
    for story in data.get("stories") or []:
        if story.get("consumed"):
            continue
        enriched = enriched_score(story)
        score = score_story(story)
        right = audit_rights(story)
        states[enriched["state"]] += 1
        rights["approved" if right["approved"] else "rejected"] += 1
        rows.append({
            "id": story.get("id", ""),
            "title": story.get("seo_title") or story.get("title") or "",
            "category": story.get("category", ""),
            "publish_score": score,
            "editorial_state": enriched["state"],
            "queue_score": enriched["score"],
            "youtube_brain": enriched["youtube_brain"],
            "packaging": enriched["packaging"],
            "rights_audit": right,
        })
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pending": len(rows),
        "states": dict(states),
        "rights": dict(rights),
        "prune_summary": prune_summary,
        "rejected_preview": [
            {
                "id": item["story"].get("id", ""),
                "title": item["story"].get("seo_title") or item["story"].get("title") or "",
                "reasons": item["reasons"],
            }
            for item in rejected[:30]
        ],
        "top": sorted(rows, key=lambda r: r["queue_score"], reverse=True)[:20],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"queue_audit: {len(rows)} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
