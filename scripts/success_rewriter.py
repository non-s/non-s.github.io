#!/usr/bin/env python3
"""Repair queue stories held by the channel success gate."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.agency_gate import (
    evaluate_story,
    load_duplicate_ids,
    load_recovery_plans,
    load_rewrite_ids,
    load_success_plan,
)
from utils.success_rewriter import evaluate_pending, rewrite_queue

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "success_rewriter.json"


def _load_queue() -> dict:
    if not QUEUE.exists():
        return {"stories": []}
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"stories": []}


def _count_held(queue: dict,
                rewrite_ids: set[str],
                recovery: dict[str, dict],
                duplicate_ids: set[str],
                success_plan: dict) -> tuple[int, Counter]:
    held = 0
    reasons: Counter[str] = Counter()
    for story in queue.get("stories") or []:
        if story.get("consumed"):
            continue
        verdict = evaluate_story(story, rewrite_ids, recovery, duplicate_ids, success_plan)
        if not verdict.get("approved"):
            held += 1
            reasons.update(verdict.get("reasons") or [])
    return held, reasons


def main() -> int:
    queue = _load_queue()
    rewrite_ids = load_rewrite_ids(ROOT / "_data" / "retention_rewrite_queue.json")
    recovery = load_recovery_plans(ROOT / "_data" / "category_recovery.json")
    success_plan = load_success_plan(ROOT / "_data" / "channel_success.json")
    duplicate_ids = load_duplicate_ids(QUEUE)
    before_held, before_reasons = _count_held(queue, rewrite_ids, recovery, duplicate_ids, success_plan)
    verdicts = evaluate_pending(queue, rewrite_ids, recovery, duplicate_ids, success_plan)
    updated, changed = rewrite_queue(queue, set(verdicts), verdicts, limit=250)
    if changed:
        QUEUE.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    duplicate_after = load_duplicate_ids(QUEUE)
    final_queue = _load_queue()
    after_held, after_reasons = _count_held(final_queue, rewrite_ids, recovery, duplicate_after, success_plan)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "before_held": before_held,
        "after_held": after_held,
        "rewritten": len(changed),
        "before_reasons": dict(before_reasons.most_common()),
        "after_reasons": dict(after_reasons.most_common()),
        "items": changed[:100],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"success rewriter: {len(changed)} rewritten, held {before_held} -> {after_held}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

