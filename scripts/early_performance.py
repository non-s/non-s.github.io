#!/usr/bin/env python3
"""Build early distribution velocity, warnings and winner-pattern memory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.early_performance import EARLY_PERFORMANCE_PATH, EARLY_WARNING_PATH, WINNER_PATTERNS_PATH, write_reports
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
    payload = write_reports(
        markers,
        ROOT / EARLY_PERFORMANCE_PATH,
        ROOT / EARLY_WARNING_PATH,
        ROOT / WINNER_PATTERNS_PATH,
    )
    early = payload["early_performance"]
    warning = payload["early_warning"]
    print(
        "early_performance: "
        f"{early.get('sample_count', 0)} video(s), "
        f"{len(warning.get('potential_accelerators') or [])} accelerator(s), "
        f"{len(warning.get('risk_of_dying_early') or [])} risk(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
