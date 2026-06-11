#!/usr/bin/env python3
"""Write experiment registry and power-aware scheduling artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.experiment_registry import write_registry  # noqa: E402
from utils.experiment_scheduler import write_underpowered_tests  # noqa: E402


def run(root: Path = ROOT, engaged_views_per_day: float = 371) -> dict:
    registry = write_registry(root / "_data" / "experiment_registry.json")
    schedule = write_underpowered_tests(
        root / "_data" / "underpowered_tests.json",
        registry=registry,
        engaged_views_per_day=engaged_views_per_day,
    )
    return {
        "registry_validation": registry.get("validation", {}),
        "underpowered_tests": schedule.get("underpowered_tests", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--engaged-views-per-day", type=float, default=371)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run(Path(args.root).resolve(), args.engaged_views_per_day)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False) if args.json else "experiment_governance: ok")
    return 0 if report["registry_validation"].get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
