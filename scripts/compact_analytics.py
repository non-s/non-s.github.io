#!/usr/bin/env python3
"""Compact flat analytics JSONL files into monthly partitions."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analytics_schema import read_jsonl  # noqa: E402

DATASETS = (
    "video_metrics",
    "video_core_daily",
    "traffic_source_daily",
    "retention_curve",
    "segment_metrics",
    "studio_reach_daily",
    "reporting_video_metrics",
)


def _month(row: dict) -> str:
    value = str(
        row.get("pulled_at")
        or row.get("day")
        or row.get("observed_at")
        or row.get("imported_at")
        or row.get("assigned_at")
        or datetime.now(timezone.utc).isoformat()
    )
    if len(value) >= 7 and value[4:5] == "-":
        return value[:7]
    return datetime.now(timezone.utc).strftime("%Y-%m")


def compact(root: Path = ROOT) -> dict:
    enabled = os.environ.get("WAREHOUSE_COMPACTION_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
    analytics = root / "_data" / "analytics"
    partitions = analytics / "partitions"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enabled": enabled,
        "datasets": {},
        "partition_root": str(partitions.relative_to(root)),
    }
    if not enabled:
        (analytics / "compaction_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return report
    for dataset in DATASETS:
        source = analytics / f"{dataset}.jsonl"
        rows = read_jsonl(source)
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[_month(row)].append(row)
        files = []
        for month, items in sorted(grouped.items()):
            dest = partitions / dataset / f"{month}.jsonl"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                "".join(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in items),
                encoding="utf-8",
            )
            files.append(str(dest.relative_to(root)))
        report["datasets"][dataset] = {
            "source": str(source.relative_to(root)),
            "rows": len(rows),
            "partitions": files,
        }
    analytics.mkdir(parents=True, exist_ok=True)
    (analytics / "compaction_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    report = compact(Path(args.root).resolve())
    total = sum(int(item.get("rows", 0) or 0) for item in report.get("datasets", {}).values())
    print(f"compact_analytics: {total} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
