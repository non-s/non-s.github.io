#!/usr/bin/env python3
"""Write a legacy visual-QA backfill report from existing markers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.visual_qa_backfill import build_backfill_report

VIDEOS = ROOT / "_videos"
OUT = ROOT / "_data" / "visual_qa_backfill.json"


def main() -> int:
    markers = []
    for path in sorted(VIDEOS.glob("*.done")) if VIDEOS.exists() else []:
        try:
            markers.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    payload = build_backfill_report(markers)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"visual qa backfill: {payload['legacy_unchecked']} legacy marker(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
