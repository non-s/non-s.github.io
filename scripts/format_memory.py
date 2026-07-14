#!/usr/bin/env python3
"""Build learned format memory from uploaded Wild Brief markers."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.growth_engine import MEMORY_PATH, build_format_memory
from utils.real_metrics import data_coverage, enrich_markers_with_latest, safe_json

VIDEOS_DIR = ROOT / "_videos"
LATEST_PATH = ROOT / "_data" / "analytics" / "latest.json"
YOUTUBE_INTELLIGENCE_PATH = ROOT / "_data" / "youtube_intelligence.json"


def _load_markers() -> list[dict]:
    markers: list[dict] = []
    for path in sorted(VIDEOS_DIR.glob("*.done")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            markers.append(data)
    return markers


def main() -> int:
    markers = enrich_markers_with_latest(
        _load_markers(),
        safe_json(LATEST_PATH),
        safe_json(YOUTUBE_INTELLIGENCE_PATH),
    )
    payload = build_format_memory(markers)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["data_coverage"] = data_coverage(markers)
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"format-memory: wrote {MEMORY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
