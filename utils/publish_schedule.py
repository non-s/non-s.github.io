"""Adaptive publish-window helper based on local analytics."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils.audience_expansion import GLOBAL_PUBLISH_WINDOWS

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
    # Until traffic-source/daypart data exists, use global UTC windows:
    # Asia/Oceania evening, Europe/Africa afternoon, Americas midday and
    # Americas evening. Cadence still adapts to retention health.
    retention = float(analytics.get("avg_view_percentage") or analytics.get("avg_view_pct") or 0)
    global_slots = [str(item["slot"]) for item in GLOBAL_PUBLISH_WINDOWS]
    slots = [global_slots[0], global_slots[1], global_slots[-1]]
    if retention < 52:
        cadence = 2
        slots = [global_slots[0], global_slots[-1]]
    elif retention >= 70:
        cadence = 4
        slots = global_slots
    else:
        cadence = 3
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "UTC",
        "recommended_slots": slots,
        "recommended_shorts_per_day": cadence,
        "target_regions": GLOBAL_PUBLISH_WINDOWS,
        "reason": "global_daypart_retention_based_until_country_analytics_available",
    }


def write_schedule(path: Path = SCHEDULE_FILE) -> dict:
    schedule = recommend_schedule()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8")
    return schedule
