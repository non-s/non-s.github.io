#!/usr/bin/env python3
"""List the strongest next Shorts without rendering."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.publish_score import score_story

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/next_shorts.json")


def _console_safe(text: str) -> str:
    return text.encode("ascii", errors="replace").decode("ascii")


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    rows = []
    for story in data.get("stories") or []:
        if story.get("consumed"):
            continue
        score = score_story(story)
        if score["state"] != "reject":
            rows.append({
                "id": story.get("id", ""),
                "title": story.get("seo_title") or story.get("title") or "",
                "category": story.get("category", ""),
                "score": score,
            })
    rows = sorted(rows, key=lambda row: row["score"]["score"], reverse=True)[:30]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"items": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    for row in rows[:10]:
        print(_console_safe(f"{row['score']['score']:5.1f} [{row['category']}] {row['title']}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
