#!/usr/bin/env python3
"""Normalize operator-dropped YouTube Reporting API CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analytics_schema import build_video_metric_row, write_jsonl_row  # noqa: E402


def _row_metrics(row: dict) -> dict:
    return {
        "views": row.get("views") or row.get("Views") or 0,
        "engaged_views": row.get("engaged_views") or row.get("Engaged views") or row.get("views") or 0,
        "estimated_minutes_watched": row.get("estimated_minutes_watched") or row.get("Estimated minutes watched") or 0,
        "average_view_duration": row.get("average_view_duration") or row.get("Average view duration") or 0,
        "average_view_percentage": row.get("average_view_percentage") or row.get("Average percentage viewed") or 0,
        "likes": row.get("likes") or row.get("Likes") or 0,
        "comments": row.get("comments") or row.get("Comments") or 0,
        "shares": row.get("shares") or row.get("Shares") or 0,
        "subscribers_gained": row.get("subscribers_gained") or row.get("Subscribers gained") or 0,
    }


def pull(root: Path = Path("."), source: str | None = None) -> dict:
    incoming = Path(source) if source else root / "_data" / "reporting_import"
    if not incoming.is_absolute():
        incoming = root / incoming
    files = [incoming] if incoming.is_file() else sorted(incoming.glob("*.csv")) if incoming.exists() else []
    out = root / "_data" / "analytics" / "reporting_video_metrics.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("", encoding="utf-8")
    rows = 0
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                video_id = row.get("video_id") or row.get("Video ID") or row.get("External video ID")
                if not video_id:
                    continue
                write_jsonl_row(
                    out,
                    build_video_metric_row(
                        video_id=str(video_id),
                        title=str(row.get("title") or row.get("Video title") or ""),
                        metrics=_row_metrics(row),
                        context={
                            "pulled_at": row.get("date") or row.get("Date") or datetime.now(timezone.utc).isoformat()
                        },
                    ),
                )
                rows += 1
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": [str(path) for path in files],
        "rows": rows,
        "output": str(out.relative_to(root)),
    }
    (root / "_data" / "analytics" / "reporting_pull.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--source")
    args = parser.parse_args()
    report = pull(Path(args.root).resolve(), args.source)
    print(f"reporting pull: {report['rows']} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
