#!/usr/bin/env python3
"""Write the channel success operating plan."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.channel_success import build_success_plan

OUT = ROOT / "_data" / "channel_success.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    payload = build_success_plan(
        latest=_safe(ROOT / "_data" / "analytics" / "latest.json"),
        comments=_safe(ROOT / "_data" / "analytics" / "comments.json"),
        health=_safe(ROOT / "_data" / "automation_health.json"),
        autonomous=_safe(ROOT / "_data" / "autonomous_director.json"),
        fact_ledger=_safe(ROOT / "_data" / "fact_ledger.json"),
        ops=_safe(ROOT / "_data" / "ops_guardian.json"),
    )
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"channel success: {payload['state']} ({payload['success_score']}/100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

