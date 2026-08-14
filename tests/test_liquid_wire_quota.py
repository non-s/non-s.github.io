from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from utils.quota_tracker import daily_call_count, daily_total, infer_cost, record_usage


def test_video_upload_uses_granular_single_unit_cost(tmp_path: Path) -> None:
    quota = tmp_path / "quota.json"
    for _ in range(24):
        record_usage("videos", "insert", file=quota)
    assert infer_cost("insert", "videos") == 1
    assert daily_call_count("videos", "insert", file=quota) == 24
    assert daily_total(file=quota) == 24


def test_legacy_upload_costs_are_migrated_on_read(tmp_path: Path) -> None:
    quota = tmp_path / "quota.json"
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    quota.write_text(
        json.dumps(
            {
                today: {
                    "total": 3250,
                    "calls": [
                        {"resource": "videos", "method": "insert", "units": 1600},
                        {"resource": "videos", "method": "insert", "units": 1600},
                        {"resource": "playlists", "method": "insert", "units": 50},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    assert daily_total(file=quota) == 52
    assert daily_call_count("videos", "insert", file=quota) == 2
