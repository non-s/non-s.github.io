#!/usr/bin/env python3
"""Reconcile Studio Reach exports and Analytics API retention-like fields."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analytics_schema import read_jsonl  # noqa: E402
from utils.retention_warehouse import reconcile_studio_api  # noqa: E402


def reconcile(root: Path = ROOT) -> dict:
    analytics = root / "_data" / "analytics"
    api_rows = {str(row.get("video_id")): row for row in read_jsonl(analytics / "video_metrics.jsonl")}
    studio_rows = {str(row.get("video_id")): row for row in read_jsonl(analytics / "studio_reach_daily.jsonl")}
    rows = []
    for video_id in sorted(set(api_rows) & set(studio_rows)):
        api_metrics = api_rows[video_id].get("metrics") or {}
        studio_metrics = studio_rows[video_id].get("metrics") or studio_rows[video_id]
        rec = reconcile_studio_api(studio_metrics, api_metrics)
        rows.append({"video_id": video_id, **rec})
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matched_videos": len(rows),
        "target_delta": 0.02,
        "out_of_tolerance": [row for row in rows if not row["within_2pct"]][:20],
    }
    out = analytics / "retention_reconciliation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = reconcile(Path(args.root).resolve())
    print(
        json.dumps(report, sort_keys=True, ensure_ascii=False)
        if args.json
        else f"retention_reconciliation: {report['matched_videos']} matched"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
