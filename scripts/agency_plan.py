#!/usr/bin/env python3
"""Write the seven-day Wild Brief agency plan."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.agency_plan import build_plan

OUT = ROOT / "_data" / "agency_plan.json"


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    payload = build_plan(
        latest=_safe_json(ROOT / "_data" / "analytics" / "latest.json"),
        health=_safe_json(ROOT / "_data" / "automation_health.json"),
        ops=_safe_json(ROOT / "_data" / "ops_guardian.json"),
        trend=_safe_json(ROOT / "_data" / "trend_radar.json"),
    )
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"agency plan: {payload.get('status', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
