#!/usr/bin/env python3
"""Check whether the current hour is inside a recommended publish window."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "_data" / "ops_guardian.json"


def main() -> int:
    if not OPS.exists():
        print("publish window: no ops report; allow")
        return 0
    data = json.loads(OPS.read_text(encoding="utf-8"))
    hours = [
        int(item.get("utc_hour"))
        for item in ((data.get("scheduler") or {}).get("recommended_utc_hours") or [])
        if isinstance(item, dict) and item.get("utc_hour") is not None
    ]
    now_hour = datetime.now(timezone.utc).hour
    allow = not hours or now_hour in set(hours)
    print(f"publish window: current={now_hour:02d}:00 UTC recommended={hours or 'any'} allow={allow}")
    if allow:
        return 0
    if os.environ.get("PUBLISH_WINDOW_ENFORCE", "0") in {"1", "true", "True"}:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
