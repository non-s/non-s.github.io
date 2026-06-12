#!/usr/bin/env python3
"""Write narrator performance from latest analytics."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.narrator_optimizer import narrator_report

LATEST = ROOT / "_data" / "analytics" / "latest.json"
VIDEOS = ROOT / "_videos"
OUT = ROOT / "_data" / "narrator_report.json"


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _marker_by_video_id() -> dict[str, dict]:
    markers: dict[str, dict] = {}
    for path in sorted(VIDEOS.glob("*.done")) if VIDEOS.exists() else []:
        item = _safe_json(path)
        video_id = str(item.get("video_id") or "")
        if video_id:
            markers[video_id] = item
    return markers


def _enrich_with_markers(items: list[dict]) -> list[dict]:
    markers = _marker_by_video_id()
    out = []
    for item in items:
        merged = dict(item)
        marker = markers.get(str(item.get("video_id") or ""))
        if marker:
            merged.setdefault("narrator_voice", marker.get("narrator_voice") or "")
            merged.setdefault("experiments", marker.get("experiments") or {})
            merged["legacy_marker_found"] = True
        out.append(merged)
    return out


def main() -> int:
    latest = _safe_json(LATEST)
    payload = narrator_report(_enrich_with_markers(latest.get("top_performers") or []))
    payload["legacy_marker_backfill"] = {
        "matched_top_performers": sum(
            1 for item in _enrich_with_markers(latest.get("top_performers") or []) if item.get("legacy_marker_found")
        )
    }
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"narrator report: {len(payload.get('voices') or [])} voice group(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
