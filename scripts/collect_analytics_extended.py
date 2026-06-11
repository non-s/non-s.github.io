#!/usr/bin/env python3
"""Normalize current analytics into durable JSONL growth rows."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analytics_schema import build_video_metric_row, write_jsonl_row  # noqa: E402


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _latest_rows(latest: dict) -> list[dict]:
    pulled_at = str(latest.get("pulled_at") or datetime.now(timezone.utc).isoformat())
    rows: list[dict] = []
    for item in latest.get("top_performers") or []:
        if not isinstance(item, dict) or not item.get("video_id"):
            continue
        metrics = {
            "views": item.get("views", 0),
            "engaged_views": item.get("engaged_views", item.get("views", 0)),
            "estimated_minutes_watched": item.get("estimated_minutes_watched", 0),
            "average_view_duration": item.get("average_view_duration", 0),
            "average_view_percentage": item.get("average_view_percentage") or item.get("view_pct", 0),
            "likes": item.get("likes", 0),
            "comments": item.get("comments", 0),
            "shares": item.get("shares", 0),
            "subscribers_gained": item.get("subscribers_gained", 0),
        }
        rows.append(
            build_video_metric_row(
                video_id=str(item.get("video_id")),
                title=str(item.get("title") or ""),
                metrics=metrics,
                context={
                    "pulled_at": pulled_at,
                    "category": item.get("category", ""),
                    "series": item.get("series", ""),
                    "story_format": item.get("story_format", ""),
                    "publish_slot": item.get("publish_slot", ""),
                },
                variants=item.get("experiments") or {},
                traffic_sources=item.get("traffic_sources") or {},
            )
        )
    return rows


def collect(root: Path = ROOT) -> dict:
    analytics = root / "_data" / "analytics"
    latest = _read_json(analytics / "latest.json", {})
    if not isinstance(latest, dict):
        latest = {}
    out = analytics / "video_metrics.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("", encoding="utf-8")
    rows = _latest_rows(latest)
    for row in rows:
        write_jsonl_row(out, row)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "output": str(out.relative_to(root)),
        "source": "_data/analytics/latest.json",
    }
    (analytics / "extended_collection_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    report = collect(Path(args.root).resolve())
    print(f"collect_analytics_extended: {report['rows']} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
