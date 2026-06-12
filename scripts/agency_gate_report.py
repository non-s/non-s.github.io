#!/usr/bin/env python3
"""Summarise the agency publish gate over the pending queue."""
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

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "agency_gate.json"


def main() -> int:
    queue = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {"stories": []}
    rewrite_ids = load_rewrite_ids(ROOT / "_data" / "retention_rewrite_queue.json")
    recovery = load_recovery_plans(ROOT / "_data" / "category_recovery.json")
    duplicate_ids = load_duplicate_ids(QUEUE)
    success_plan = load_success_plan(ROOT / "_data" / "channel_success.json")
    held = []
    approved = 0
    reasons = Counter()
    for story in queue.get("stories") or []:
        if story.get("consumed"):
            continue
        verdict = evaluate_story(story, rewrite_ids, recovery, duplicate_ids, success_plan)
        if verdict["approved"]:
            approved += 1
        else:
            reasons.update(verdict["reasons"])
            held.append(
                {
                    "id": story.get("id", ""),
                    "title": story.get("seo_title") or story.get("title", ""),
                    "category": story.get("category", ""),
                    "reasons": verdict["reasons"],
                }
            )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "approved": approved,
        "held": len(held),
        "reasons": dict(reasons.most_common()),
        "held_items": held[:50],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"agency gate: {approved} approved, {len(held)} held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
