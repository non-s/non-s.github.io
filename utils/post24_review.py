"""Classify Shorts after the first 24 hours."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ANALYTICS_FILE = Path("_data/analytics/latest.json")
POST24_FILE = Path("_data/post24_review.json")
RETENTION_SCALE_FLOOR = 62.0
RETENTION_REWRITE_FLOOR = 62.0


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def classify_video(item: dict) -> str:
    views = int(item.get("views") or 0)
    retention = float(item.get("view_pct") or item.get("average_view_percentage") or 0)
    growth = float(item.get("growth_score") or 0)
    if retention >= RETENTION_SCALE_FLOOR and growth >= 180:
        return "scale"
    if views >= 900 and retention < RETENTION_REWRITE_FLOOR:
        return "rewrite_hook"
    if views < 500 and retention < 50:
        return "pause_topic"
    return "watch"


def build_review(analytics: dict | None = None) -> dict:
    analytics = analytics or _safe_json(ANALYTICS_FILE)
    rows = []
    for item in analytics.get("top_performers") or []:
        rows.append({
            "video_id": item.get("video_id", ""),
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "views": item.get("views", 0),
            "retention": item.get("view_pct") or item.get("average_view_percentage") or 0,
            "growth_score": item.get("growth_score", 0),
            "decision": classify_video(item),
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": rows,
        "counts": {state: sum(1 for row in rows if row["decision"] == state)
                   for state in ("scale", "rewrite_hook", "pause_topic", "watch")},
        "rules": {
            "scale": f"retention >= {RETENTION_SCALE_FLOOR:g} and growth_score >= 180",
            "rewrite_hook": f"views >= 900 and retention < {RETENTION_REWRITE_FLOOR:g}",
            "pause_topic": "views < 500 and retention < 50",
        },
    }


def write_review(path: Path = POST24_FILE) -> dict:
    review = build_review()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    return review
