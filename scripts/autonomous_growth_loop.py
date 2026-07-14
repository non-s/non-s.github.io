#!/usr/bin/env python3
"""Run the closed-loop autonomous growth planner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.autonomous_growth_loop import write_plan


def main() -> int:
    plan = write_plan()
    queue = plan.get("queue") or {}
    print(
        "autonomous growth loop: "
        f"{plan.get('state')} score={plan.get('autonomy_score')} "
        f"mode={plan.get('operating_mode')} "
        f"pending={queue.get('pending', 0)} "
        f"annotated={plan.get('queue_annotations_written', 0)} "
        f"changed={plan.get('queue_annotations_changed', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
