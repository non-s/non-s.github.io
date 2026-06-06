#!/usr/bin/env python3
"""Write the Wild Brief operations guardian report."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ops_guardian import build_ops_report, should_enforce_pause

OUT = ROOT / "_data" / "ops_guardian.json"


def _without_generated_at(payload: dict) -> dict:
    stable = dict(payload)
    stable.pop("generated_at", None)
    return stable


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = build_ops_report(ROOT)
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    if _without_generated_at(previous) == _without_generated_at(report):
        report["generated_at"] = previous.get("generated_at", report["generated_at"])
    else:
        OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    risk = report.get("risk") or {}
    print(f"ops guardian: {risk.get('level', 'unknown')} ({risk.get('score', 0)}/100)")
    paused = report.get("paused_topics") or []
    if paused:
        print("paused topics:", ", ".join(str(item.get("category")) for item in paused))
    if os.environ.get("OPS_GUARDIAN_ENFORCE", "0") in {"1", "true", "True"} and should_enforce_pause(report):
        print("ops guardian: critical risk; enforcement requested, stopping run")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
