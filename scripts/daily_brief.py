#!/usr/bin/env python3
"""Daily agency brief for the next production day."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "_data" / "daily_brief.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    health = _safe(ROOT / "_data" / "automation_health.json")
    ops = _safe(ROOT / "_data" / "ops_guardian.json")
    remakes = _safe(ROOT / "_data" / "remake_backlog.json")
    plan = _safe(ROOT / "_data" / "agency_plan.json")
    rewrite = _safe(ROOT / "_data" / "retention_rewrite_queue.json")
    trend = _safe(ROOT / "_data" / "trend_radar.json")
    agency_top = (health.get("agency") or {}).get("top") or []
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": plan.get("status", "steady"),
        "publish_now_inventory": (health.get("agency") or {}).get("decisions", {}).get("publish_now", 0),
        "today": (plan.get("days") or [{}])[0],
        "publish_first": agency_top[:3],
        "remake_first": (remakes.get("remakes") or [])[:3],
        "rewrite_first": (rewrite.get("items") or [])[:5],
        "avoid": [item.get("category") for item in (ops.get("paused_topics") or [])],
        "trend_watch": [
            {
                "animal": item.get("animal"),
                "category": item.get("category"),
                "posture": (item.get("trend_safety") or {}).get("posture", ""),
            }
            for item in (trend.get("topics") or [])[:5]
        ],
        "orders": [
            "Publish agency publish_now candidates before generic queue items.",
            "Use one remake candidate if the slot needs a proven topic.",
            "Do not use paused categories unless category_recovery rules pass.",
            "Rewrite low retention hooks before creating more similar videos.",
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"daily brief: {payload['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
