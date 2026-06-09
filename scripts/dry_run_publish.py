#!/usr/bin/env python3
"""Dry-run publish scoring without rendering/uploading."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.publish_score import score_story
from utils.rights_audit import audit_rights

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/dry_run_publish.json")


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    items = []
    for story in data.get("stories") or []:
        if story.get("consumed"):
            continue
        score = score_story(story)
        rights = audit_rights(story)
        if score["state"] != "reject" and rights["approved"]:
            items.append({
                "id": story.get("id", ""),
                "title": story.get("seo_title") or story.get("title") or "",
                "category": story.get("category", ""),
                "publish_score": score,
                "rights_audit": rights,
            })
    items = sorted(items, key=lambda item: item["publish_score"]["score"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"would_publish": items[:10], "eligible_count": len(items)}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"dry_run_publish: {len(items)} eligible candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
