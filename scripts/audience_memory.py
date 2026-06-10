#!/usr/bin/env python3
"""Build real audience memory from .done markers plus analytics/latest.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.audience_memory import AUDIENCE_MEMORY_PATH, write_audience_memory
from utils.real_metrics import enrich_markers_with_latest, safe_json

VIDEOS_DIR = ROOT / "_videos"
LATEST_PATH = ROOT / "_data" / "analytics" / "latest.json"
YOUTUBE_INTELLIGENCE_PATH = ROOT / "_data" / "youtube_intelligence.json"


def _load_markers() -> list[dict]:
    markers: list[dict] = []
    for path in sorted(VIDEOS_DIR.glob("*.done")) if VIDEOS_DIR.exists() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                markers.append(data)
        except Exception:
            continue
    return markers


def main() -> int:
    markers = enrich_markers_with_latest(
        _load_markers(),
        safe_json(LATEST_PATH),
        safe_json(YOUTUBE_INTELLIGENCE_PATH),
    )
    payload = write_audience_memory(markers, ROOT / AUDIENCE_MEMORY_PATH)
    print(
        "audience_memory: "
        f"{payload.get('sample_count', 0)} video(s), "
        f"{payload.get('coverage', {}).get('with_retention', 0)} with retention"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
