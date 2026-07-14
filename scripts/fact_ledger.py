#!/usr/bin/env python3
"""Build the editorial fact/angle ledger for the pending queue."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.fact_ledger import build_fact_ledger

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "fact_ledger.json"


def main() -> int:
    queue = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {"stories": []}
    payload = build_fact_ledger(queue.get("stories") or [])
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"fact ledger: {len(payload.get('duplicate_clusters') or [])} duplicate cluster(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
