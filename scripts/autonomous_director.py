#!/usr/bin/env python3
"""Write the autonomous operating plan for the channel."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.autonomous_director import build_director

OUT = ROOT / "_data" / "autonomous_director.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    payload = build_director(
        latest=_safe(ROOT / "_data" / "analytics" / "latest.json"),
        youtube_intelligence=_safe(ROOT / "_data" / "youtube_intelligence.json"),
        health=_safe(ROOT / "_data" / "automation_health.json"),
        ops=_safe(ROOT / "_data" / "ops_guardian.json"),
        fact_ledger=_safe(ROOT / "_data" / "fact_ledger.json"),
    )
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"autonomous director: {payload['state']} ({payload['autonomy_score']}/100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
