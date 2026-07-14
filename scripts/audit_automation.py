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


def _without_generated_at(payload: dict) -> dict:
    stable = dict(payload)
    stable.pop("generated_at", None)
    return stable


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_health(ROOT)
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    if _without_generated_at(previous) == _without_generated_at(payload):
        payload["generated_at"] = previous.get("generated_at", payload["generated_at"])
    else:
        OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"automation health: {payload['state']} ({payload['score']}/100)")
    if payload.get("issues"):
        print("issues:", ", ".join(payload["issues"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
