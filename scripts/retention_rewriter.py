#!/usr/bin/env python3
"""Apply local retention rewrites to held queue stories."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.agency_gate import load_rewrite_ids
from utils.retention_rewriter import rewrite_queue

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "retention_rewriter.json"


def main() -> int:
    queue = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {"stories": []}
    rewrite_ids = load_rewrite_ids(ROOT / "_data" / "retention_rewrite_queue.json")
    limit = int(os.environ.get("RETENTION_REWRITER_LIMIT", "20"))
    updated, changed = rewrite_queue(queue, rewrite_ids, limit=limit)
    if changed:
        tmp = QUEUE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(QUEUE)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rewritten": len(changed),
        "limit": limit,
        "items": changed,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"retention rewriter: {len(changed)} rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
