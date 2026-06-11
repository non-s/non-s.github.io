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
from utils.editorial_mix_optimizer import build_mix_plan, classify_lane, mix_adjustment

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/next_shorts.json")


def _console_safe(text: str) -> str:
    return text.encode("ascii", errors="replace").decode("ascii")


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    rows = []
    pending_stories = [story for story in data.get("stories") or [] if not story.get("consumed")]
    mix_plan = build_mix_plan(pending_stories)
    for story in data.get("stories") or []:
        if story.get("consumed"):
            continue
        score = score_story(story)
        if score["state"] != "reject":
            lane_adjustment = mix_adjustment(story)
            score = {**score, "score": round(float(score.get("score") or 0) + lane_adjustment, 1)}
            rows.append(
                {
                    "id": story.get("id", ""),
                    "title": story.get("seo_title") or story.get("title") or "",
                    "category": story.get("category", ""),
                    "lane": classify_lane(story),
                    "mix_adjustment": lane_adjustment,
                    "score": score,
                }
            )
    rows = sorted(rows, key=lambda row: row["score"]["score"], reverse=True)[:30]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"items": rows, "editorial_mix": mix_plan}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for row in rows[:10]:
        print(_console_safe(f"{row['score']['score']:5.1f} [{row['category']}] {row['title']}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
