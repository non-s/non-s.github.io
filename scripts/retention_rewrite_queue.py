#!/usr/bin/env python3
"""Write a queue of pending stories that need retention rewrites."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.retention_surgeon import diagnose

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "retention_rewrite_queue.json"


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {"stories": []}
    items = []
    for story in data.get("stories") or []:
        if story.get("consumed"):
            continue
        surgery = diagnose(story)
        if surgery["verdict"] == "rewrite":
            items.append(
                {
                    "id": story.get("id", ""),
                    "title": story.get("seo_title") or story.get("title", ""),
                    "category": story.get("category", ""),
                    "score": surgery["score"],
                    "issues": surgery["issues"],
                    "fixes": surgery["fixes"],
                    "suggested_hook": surgery["suggested_hook"],
                }
            )
    items.sort(key=lambda item: item["score"])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items[:50],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"retention rewrite queue: {payload['count']} item(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
