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


def build_report(queue_path: Path = QUEUE, out_path: Path = OUT) -> dict:
    queue = _safe(queue_path)
    items = []
    for story in queue.get("stories") or []:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        brain = creator_premortem(story)
        queue_state = str((story.get("queue_prune") or {}).get("state") or "")
        items.append({
            "id": story.get("id", ""),
            "title": story.get("seo_title") or story.get("title") or "",
            "category": story.get("category", ""),
            "queue_state": queue_state,
            "youtube_brain": brain,
        })
    items.sort(key=lambda item: item["youtube_brain"]["score"], reverse=True)
    publish_ready = [item for item in items if item.get("queue_state") == "publish_ready"]
    watchlist = [
        item
        for item in items
        if item.get("queue_state") not in ("", "publish_ready")
        or ((item.get("youtube_brain") or {}).get("risks") or [])
    ]
    watchlist.sort(
        key=lambda item: (
            0 if item.get("queue_state") not in ("", "publish_ready") else 1,
            -float((item.get("youtube_brain") or {}).get("score", 0) or 0),
        )
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pending": len(items),
        "summary": channel_brain_summary(items),
        "publish_ready_summary": channel_brain_summary(publish_ready),
        "publish_ready_top": publish_ready[:30],
        "risk_watchlist": watchlist[:30],
        "top": items[:30],
        "operating_principle": (
            "Each Short must earn the swipe: one visible animal, one specific "
            "action, one reason to keep watching, and one payoff."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> int:
    payload = build_report()
    print(f"youtube brain report: {payload['pending']} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
