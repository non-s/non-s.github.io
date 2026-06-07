#!/usr/bin/env python3
"""Rewrite stories held by category recovery into approved-safe variants."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.agency_gate import evaluate_story, load_recovery_plans, load_rewrite_ids
from utils.category_recovery_rewriter import recover_queue

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "category_recovery_rewriter.json"


def main() -> int:
    queue = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {"stories": []}
    rewrite_ids = load_rewrite_ids(ROOT / "_data" / "retention_rewrite_queue.json")
    recovery = load_recovery_plans(ROOT / "_data" / "category_recovery.json")
    held_ids = {
        str(story.get("id") or "")
        for story in queue.get("stories") or []
        if not story.get("consumed") and not evaluate_story(story, rewrite_ids, recovery)["approved"]
    }
    updated, changed = recover_queue(queue, held_ids, recovery)
    if changed:
        QUEUE.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rewritten": len(changed),
        "items": changed,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"category recovery rewriter: {len(changed)} rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
