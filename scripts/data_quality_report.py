#!/usr/bin/env python3
"""Write a data-quality report for Wild Brief learning systems."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.data_quality import build_data_quality_report
from utils.real_metrics import enrich_markers_with_latest, safe_json

VIDEOS_DIR = ROOT / "_videos"
LATEST_PATH = ROOT / "_data" / "analytics" / "latest.json"
YOUTUBE_INTELLIGENCE_PATH = ROOT / "_data" / "youtube_intelligence.json"
OUT_PATH = ROOT / "_data" / "data_quality_report.json"


def _load_markers() -> list[dict]:
    markers: list[dict] = []
    for path in sorted(VIDEOS_DIR.glob("*.done")) if VIDEOS_DIR.exists() else []:
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
    payload = build_data_quality_report(
        markers,
        audience_memory=safe_json(ROOT / "_data" / "audience_memory.json"),
        format_memory=safe_json(ROOT / "_data" / "format_memory.json"),
        early_performance=safe_json(ROOT / "_data" / "early_performance.json"),
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "data_quality_report: "
        f"{payload.get('sample_count', 0)} marker(s), "
        f"confidence={payload.get('overall_confidence_score', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
