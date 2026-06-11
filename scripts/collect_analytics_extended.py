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

from utils.analytics_schema import (  # noqa: E402
    build_retention_row,
    build_segment_row,
    build_traffic_source_row,
    build_video_metric_row,
    read_jsonl,
    write_jsonl_row,
)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _latest_rows(latest: dict) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    pulled_at = str(latest.get("pulled_at") or datetime.now(timezone.utc).isoformat())
    rows: list[dict] = []
    traffic_rows: list[dict] = []
    retention_rows: list[dict] = []
    segment_rows: list[dict] = []
    for item in latest.get("top_performers") or []:
        if not isinstance(item, dict) or not item.get("video_id"):
            continue
        video_id = str(item.get("video_id"))
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
        context = {
            "pulled_at": pulled_at,
            "category": item.get("category", ""),
            "series": item.get("series", ""),
            "story_format": item.get("story_format", ""),
            "publish_slot": item.get("publish_slot", ""),
        }
        rows.append(
            build_video_metric_row(
                video_id=video_id,
                title=str(item.get("title") or ""),
                metrics=metrics,
                context=context,
                variants=item.get("experiments") or {},
                traffic_sources=item.get("traffic_sources") or {},
            )
        )
        for source_type, views in (item.get("traffic_sources") or {}).items():
            traffic_rows.append(
                build_traffic_source_row(video_id, str(source_type), {"views": views}, pulled_at=pulled_at)
            )
        for bucket in item.get("retention_curve") or item.get("retention_buckets") or []:
            if not isinstance(bucket, dict):
                continue
            retention_rows.append(
                build_retention_row(
                    video_id,
                    bucket.get("elapsed_video_time_ratio", bucket.get("elapsed", 0)),
                    bucket.get("audience_watch_ratio", bucket.get("watch_ratio", 0)),
                    pulled_at=pulled_at,
                )
            )
        for segment_type in ("country", "deviceType", "subscribedStatus"):
            values = (item.get("segments") or {}).get(segment_type) or {}
            if not isinstance(values, dict):
                continue
            for segment_value, segment_metrics in values.items():
                payload = segment_metrics if isinstance(segment_metrics, dict) else {"views": segment_metrics}
                segment_rows.append(
                    build_segment_row(
                        segment_type, str(segment_value), payload, pulled_at=pulled_at, context={"video_id": video_id}
                    )
                )
    return rows, traffic_rows, retention_rows, segment_rows


def _missing_analytics_reports(root: Path) -> list[dict]:
    intelligence = _read_json(root / "_data" / "youtube_intelligence.json", {})
    reports = intelligence.get("analytics_reports") if isinstance(intelligence, dict) else []
    missing = []
    for report in reports or []:
        if isinstance(report, dict) and report.get("status") != "ok":
            missing.append(
                {
                    "id": report.get("id", ""),
                    "dimensions": report.get("dimensions", ""),
                    "status": report.get("status", "missing"),
                    "error": report.get("error", ""),
                }
            )
    return missing


def collect(root: Path = ROOT) -> dict:
    analytics = root / "_data" / "analytics"
    latest = _read_json(analytics / "latest.json", {})
    if not isinstance(latest, dict):
        latest = {}
    paths = {
        "video_metrics": analytics / "video_metrics.jsonl",
        "video_core_daily": analytics / "video_core_daily.jsonl",
        "traffic_source_daily": analytics / "traffic_source_daily.jsonl",
        "retention_curve": analytics / "retention_curve.jsonl",
        "segment_metrics": analytics / "segment_metrics.jsonl",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    rows, traffic_rows, retention_rows, segment_rows = _latest_rows(latest)
    reporting_rows = read_jsonl(analytics / "reporting_video_metrics.jsonl")
    if reporting_rows:
        rows.extend(reporting_rows)
    for row in rows:
        write_jsonl_row(paths["video_metrics"], row)
        write_jsonl_row(paths["video_core_daily"], row)
    for row in traffic_rows:
        write_jsonl_row(paths["traffic_source_daily"], row)
    for row in retention_rows:
        write_jsonl_row(paths["retention_curve"], row)
    for row in segment_rows:
        write_jsonl_row(paths["segment_metrics"], row)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "reporting_rows": len(reporting_rows),
        "traffic_source_rows": len(traffic_rows),
        "retention_rows": len(retention_rows),
        "segment_rows": len(segment_rows),
        "outputs": {name: str(path.relative_to(root)) for name, path in paths.items()},
        "source": "_data/analytics/latest.json",
        "missing_analytics_reports": _missing_analytics_reports(root),
    }
    (analytics / "extended_collection_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
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
