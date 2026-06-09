#!/usr/bin/env python3
"""Audit the pending queue with senior YouTube creator heuristics."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.youtube_brain import channel_brain_summary, creator_premortem

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "youtube_brain_report.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    queue = _safe(QUEUE)
    items = []
    for story in queue.get("stories") or []:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        brain = creator_premortem(story)
        items.append({
            "id": story.get("id", ""),
            "title": story.get("seo_title") or story.get("title") or "",
            "category": story.get("category", ""),
            "youtube_brain": brain,
        })
    items.sort(key=lambda item: item["youtube_brain"]["score"], reverse=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": channel_brain_summary(items),
        "top": items[:30],
        "operating_principle": (
            "Each Short must earn the swipe: one visible animal, one specific "
            "action, one reason to keep watching, and one payoff."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"youtube brain report: {len(items)} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
