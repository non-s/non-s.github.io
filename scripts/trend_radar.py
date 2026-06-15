#!/usr/bin/env python3
"""Write the local public nature-science trend radar."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.trend_radar import build_trend_radar  # noqa: E402

OUT = ROOT / "_data" / "trend_radar.json"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_trend_radar(ROOT)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = payload.get("summary") or {}
    print("trend radar: " f"{summary.get('animal_topics', 0)} topic(s), " f"top={summary.get('top_animal') or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
