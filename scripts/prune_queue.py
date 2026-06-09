#!/usr/bin/env python3
"""Prune active queue inventory and quarantine weak candidates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.growth_strategy import load_strategy
from utils.queue_pruner import prune_queue
from utils.rejected_queue import record_rejection

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "queue_prune_report.json"


def main() -> int:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    pruned, rejected, summary = prune_queue(queue, analytics_strategy=load_strategy())
    for item in rejected:
        record_rejection(item["story"], item["reasons"], stage=item.get("stage", "queue_prune"))
    QUEUE.write_text(json.dumps(pruned, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "prune_queue: "
        f"{summary['pending_before']} -> {summary['pending_after']} pending, "
        f"{summary['rejected']} quarantined"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
