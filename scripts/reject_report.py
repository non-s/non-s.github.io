#!/usr/bin/env python3
"""Summarise rejected candidates."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.rejected_queue import load_rejections

OUT = Path("_data/reject_report.json")


def main() -> int:
    items = load_rejections()
    reasons = Counter(reason for item in items for reason in item.get("reasons", []))
    stages = Counter(item.get("stage", "unknown") for item in items)
    payload = {
        "total": len(items),
        "reasons": dict(reasons.most_common()),
        "stages": dict(stages.most_common()),
        "latest": items[-25:],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"reject_report: {len(items)} rejected candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
