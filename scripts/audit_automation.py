#!/usr/bin/env python3
"""Write the local Wild Brief automation health report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.automation_health import build_health

OUT = ROOT / "_data" / "automation_health.json"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_health(ROOT)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"automation health: {payload['state']} ({payload['score']}/100)")
    if payload.get("issues"):
        print("issues:", ", ".join(payload["issues"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
