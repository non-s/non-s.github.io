"""Adaptive publish-window helper based on local analytics."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ANALYTICS_FILE = Path("_data/analytics/latest.json")
SCHEDULE_FILE = Path("_data/publish_schedule.json")


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def recommend_schedule(analytics: dict | None = None) -> dict:
    analytics = analytics or _safe_json(ANALYTICS_FILE)
    # Until traffic-source/daypart data exists, keep proven UTC slots and
    # adapt cadence based on retention health.
    retention = float(analytics.get("avg_view_percentage") or analytics.get("avg_view_pct") or 0)
    slots = ["14:23", "19:23", "23:23"]
    if retention < 52:
        cadence = 2
        slots = ["14:23", "23:23"]
    elif retention >= 70:
        cadence = 4
        slots = ["11:23", "14:23", "19:23", "23:23"]
    else:
        cadence = 3
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "UTC",
        "recommended_slots": slots,
        "recommended_shorts_per_day": cadence,
        "reason": "retention_based_until_daypart_analytics_available",
    }


def write_schedule(path: Path = SCHEDULE_FILE) -> dict:
    schedule = recommend_schedule()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8")
    return schedule
