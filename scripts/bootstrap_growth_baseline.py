#!/usr/bin/env python3
"""Bootstrap normalized Wild Brief growth analytics artifacts.

This script is safe to run on an empty checkout and safe to rerun. It reads the
current dashboard-oriented analytics when present, writes normalized JSONL
files, and creates a compact weekly summary for future jobs to consume.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analytics_schema import build_variant_row, build_video_metric_row, write_jsonl_row


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _done_markers(root: Path) -> Iterable[dict]:
    videos_dir = root / "_videos"
    if not videos_dir.exists():
        return []
    rows: list[dict] = []
    for path in sorted(videos_dir.glob("*.done")):
        data = _read_json(path, {})
        if isinstance(data, dict):
            rows.append(data)
    return rows


def _reset_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _metric_rows_from_latest(latest: dict) -> list[dict]:
    pulled_at = str(latest.get("pulled_at") or datetime.now(timezone.utc).isoformat())
    rows: list[dict] = []
    for item in latest.get("top_performers") or []:
        if not isinstance(item, dict) or not item.get("video_id"):
            continue
        metrics = {
            "views": item.get("views", 0),
            "engaged_views": item.get("engaged_views", 0),
            "estimated_minutes_watched": item.get("estimated_minutes_watched", 0),
            "average_view_duration": item.get("average_view_duration", 0),
            "average_view_percentage": item.get("average_view_percentage") or item.get("view_pct", 0),
            "likes": item.get("likes", 0),
            "comments": item.get("comments", 0),
            "shares": item.get("shares", 0),
            "subscribers_gained": item.get("subscribers_gained", 0),
        }
        context = {
            "pulled_at": pulled_at,
            "category": item.get("category", ""),
            "series": item.get("series", ""),
            "story_format": item.get("story_format", ""),
            "publish_slot": item.get("publish_slot", ""),
        }
        rows.append(build_video_metric_row(
            video_id=str(item.get("video_id")),
            title=str(item.get("title") or ""),
            metrics=metrics,
            context=context,
            variants=item.get("experiments") or {},
        ))
    return rows


def _variant_rows_from_markers(markers: Iterable[dict]) -> list[dict]:
    rows: list[dict] = []
    for marker in markers:
        story_id = str(marker.get("story_id") or marker.get("id") or marker.get("video_id") or marker.get("title") or "")
        if not story_id:
            continue
        context = {
            "video_id": marker.get("video_id", ""),
            "category": marker.get("category", ""),
            "series": marker.get("series", ""),
            "story_format": marker.get("story_format", ""),
        }
        for axis, variant in (marker.get("experiments") or {}).items():
            rows.append(build_variant_row(str(axis), str(variant), story_id, context=context))
    return rows


def build_baseline(root: Path) -> dict:
    """Build normalized baseline files under ``root/_data/analytics``."""
    analytics_dir = root / "_data" / "analytics"
    analytics_dir.mkdir(parents=True, exist_ok=True)
    latest = _read_json(analytics_dir / "latest.json", {})
    if not isinstance(latest, dict):
        latest = {}

    video_metrics_path = analytics_dir / "video_metrics.jsonl"
    variant_path = analytics_dir / "variant_assignments.jsonl"
    weekly_path = analytics_dir / "weekly_summary.json"
    _reset_jsonl(video_metrics_path)
    _reset_jsonl(variant_path)

    metric_rows = _metric_rows_from_latest(latest)
    markers = list(_done_markers(root))
    variant_rows = _variant_rows_from_markers(markers)
    for row in metric_rows:
        write_jsonl_row(video_metrics_path, row)
    for row in variant_rows:
        write_jsonl_row(variant_path, row)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "bootstrap_growth_baseline",
        "video_metric_rows": len(metric_rows),
        "variant_assignment_rows": len(variant_rows),
        "shorts_tracked": int(latest.get("shorts_tracked", 0) or len(metric_rows)),
        "total_views": int(latest.get("total_views", 0) or sum(row["metrics"]["views"] for row in metric_rows)),
        "avg_view_percentage": float(latest.get("avg_view_percentage", latest.get("avg_view_pct", 0)) or 0),
        "top_categories": latest.get("category_avg_growth_score") or latest.get("category_avg_view_pct") or {},
        "top_formats": latest.get("format_avg_growth_score") or {},
        "files": {
            "video_metrics": str(video_metrics_path.relative_to(root)),
            "variant_assignments": str(variant_path.relative_to(root)),
            "weekly_summary": str(weekly_path.relative_to(root)),
        },
    }
    weekly_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Wild Brief growth baseline artifacts.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args()
    summary = build_baseline(Path(args.root).resolve())
    print(
        "growth baseline: "
        f"{summary['video_metric_rows']} video rows, "
        f"{summary['variant_assignment_rows']} variant rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
