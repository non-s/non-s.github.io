#!/usr/bin/env python3
"""Append sequel candidates from top-performing Shorts."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.autonomous_director import append_sequels, sequel_candidates

QUEUE = ROOT / "_data" / "stories_queue.json"
LATEST = ROOT / "_data" / "analytics" / "latest.json"
OUT = ROOT / "_data" / "winner_sequel_factory.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    queue = _safe(QUEUE) or {"stories": []}
    candidates = sequel_candidates(_safe(LATEST))
    updated, created = append_sequels(queue, candidates)
    if updated != queue:
        QUEUE.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "created": len(created),
        "created_ids": [item["id"] for item in created],
        "candidates": candidates,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"winner sequel factory: {len(created)} created from {len(candidates)} candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
