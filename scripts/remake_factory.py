#!/usr/bin/env python3
"""Create queue-ready remake drafts from the remake backlog."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.remake_factory import append_remakes_to_queue

QUEUE = ROOT / "_data" / "stories_queue.json"
BACKLOG = ROOT / "_data" / "remake_backlog.json"
OUT = ROOT / "_data" / "remake_factory.json"


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    queue = _safe_json(QUEUE) or {"stories": []}
    backlog = _safe_json(BACKLOG)
    limit = int(os.environ.get("REMAKE_FACTORY_LIMIT", "5"))
    updated, created = append_remakes_to_queue(queue, backlog.get("remakes") or [], limit=limit)
    if created or updated != queue:
        tmp = QUEUE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(QUEUE)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "created": len(created),
        "created_ids": [item["id"] for item in created],
        "limit": limit,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"remake factory: {payload['created']} draft(s) created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
