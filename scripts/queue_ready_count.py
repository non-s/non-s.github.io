#!/usr/bin/env python3
"""Count Shorts that can survive the real publishing gate right now."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.growth_strategy import load_strategy
from utils.queue_pruner import prune_queue
from utils.rejected_queue import record_rejection

QUEUE = ROOT / "_data" / "stories_queue.json"
PRUNE_REPORT = ROOT / "_data" / "queue_prune_report.json"
REPAIR_OUT = ROOT / "_data" / "repair_queue.jsonl"


def _read_queue(path: Path = QUEUE) -> dict:
    if not path.exists():
        return {"stories": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _is_publish_ready(story: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    queue_prune = story.get("queue_prune") or {}
    publish = story.get("publish_score") or {}
    editorial = story.get("editorial") or {}

    if story.get("consumed"):
        reasons.append("consumed")
    if queue_prune.get("state") != "publish_ready":
        reasons.append(f"queue_prune:{queue_prune.get('state') or 'missing'}")
    if publish.get("approved") is not True or publish.get("state") != "publish_ready":
        reasons.append(f"publish_score:{publish.get('state') or 'missing'}")
    if editorial.get("approved") is not True:
        reasons.append(f"editor_in_chief:{editorial.get('state') or 'missing'}")
    return not reasons, reasons


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


def build_payload(queue: dict) -> dict:
    pending = [story for story in queue.get("stories") or [] if isinstance(story, dict) and not story.get("consumed")]
    ready: list[dict] = []
    held = Counter()
    for story in pending:
        ok, reasons = _is_publish_ready(story)
        if ok:
            ready.append(story)
        else:
            for reason in reasons:
                held[reason] += 1
    return {
        "pending": len(pending),
        "publish_ready": len(ready),
        "publish_ready_ids": [str(story.get("id") or "") for story in ready[:20]],
        "held_reasons": dict(held.most_common()),
    }


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
    payload = build_payload(queue)
    if args.field:
        print(int(payload.get(args.field, 0) or 0))
    elif args.json:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        print(f"queue_ready_count: {payload['publish_ready']} publish-ready / {payload['pending']} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
