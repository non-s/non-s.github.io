#!/usr/bin/env python3
"""Count Shorts that can survive the real publishing gate right now."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.growth_strategy import load_strategy  # noqa: E402
from utils.queue_readiness import build_readiness_payload  # noqa: E402
from utils.queue_pruner import prune_queue  # noqa: E402
from utils.rejected_queue import record_rejection  # noqa: E402

QUEUE = ROOT / "_data" / "stories_queue.json"
PRUNE_REPORT = ROOT / "_data" / "queue_prune_report.json"
REPAIR_OUT = ROOT / "_data" / "repair_queue.jsonl"
AGENCY_GATE = ROOT / "_data" / "agency_gate.json"
CATEGORY_RECOVERY = ROOT / "_data" / "category_recovery.json"
CHANNEL_SUCCESS = ROOT / "_data" / "channel_success.json"
REWRITE_QUEUE = ROOT / "_data" / "retention_rewrite_queue.json"


def _read_queue(path: Path = QUEUE) -> dict:
    if not path.exists():
        return {"stories": []}
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_queue(path: Path = QUEUE) -> dict:
    """Prune and persist queue metadata before counting ready supply."""
    queue = _read_queue(path)
    pruned, rejected, summary = prune_queue(queue, analytics_strategy=load_strategy())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pruned, indent=2, ensure_ascii=False), encoding="utf-8")
    PRUNE_REPORT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    repair_items = []
    for item in rejected:
        record_rejection(item["story"], item["reasons"], stage=item.get("stage", "queue_prune"))
        if item.get("stage") == "queue_repair":
            repair_items.append(item)
    REPAIR_OUT.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in repair_items),
        encoding="utf-8",
    )
    return pruned


def build_payload(
    queue: dict,
    *,
    env: Mapping[str, str] | None = None,
    refresh_agency: bool = False,
    queue_path: Path = QUEUE,
) -> dict:
    return build_readiness_payload(
        queue,
        root=ROOT,
        env=env,
        refresh_agency=refresh_agency,
        queue_path=queue_path,
        agency_gate_path=AGENCY_GATE,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=str(QUEUE), help="Queue JSON path.")
    parser.add_argument(
        "--refresh", action="store_true", help="Refresh queue_prune/editorial metadata before counting."
    )
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    parser.add_argument("--field", choices=("pending", "publish_ready"), help="Print one numeric field only.")
    args = parser.parse_args()

    queue_path = Path(args.queue)
    queue = refresh_queue(queue_path) if args.refresh else _read_queue(queue_path)
    payload = build_payload(queue, refresh_agency=args.refresh, queue_path=queue_path)
    if args.field:
        print(int(payload.get(args.field, 0) or 0))
    elif args.json:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        print(f"queue_ready_count: {payload['publish_ready']} publish-ready / {payload['pending']} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
