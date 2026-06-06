"""Tests for local automation health audit."""
from __future__ import annotations

import json
from pathlib import Path

from utils.automation_health import build_health


def test_automation_health_scores_queue_and_analytics(tmp_path: Path):
    data = tmp_path / "_data"
    (data / "analytics").mkdir(parents=True)
    (data / "stories_queue.json").write_text(json.dumps({
        "stories": [{
            "id": "a",
            "category": "cats",
            "seo_title": "Cats purr to heal their bones",
            "hook": "Cats purr to heal their bones.",
            "script": "Cats purr to heal their bones. Watch the chest and paws because vibration helps tissue recover.",
            "yt_tags": ["cats", "purring"],
            "source_url": "https://www.pexels.com/video/cat/",
        }]
    }), encoding="utf-8")
    (data / "analytics" / "latest.json").write_text(json.dumps({
        "metric_scope": "youtube_analytics_and_public_statistics",
        "avg_view_pct": 70,
        "total_views": 100,
        "shorts_tracked": 1,
    }), encoding="utf-8")
    out = build_health(tmp_path)
    assert out["queue"]["pending"] == 1
    assert out["seo"]["average_score"] >= 90
    assert out["analytics"]["metric_scope"] == "youtube_analytics_and_public_statistics"


def test_automation_health_flags_duplicate_scripts(tmp_path: Path):
    data = tmp_path / "_data"
    data.mkdir(parents=True)
    script = "Cats purr to heal their bones."
    (data / "stories_queue.json").write_text(json.dumps({
        "stories": [
            {"id": "a", "category": "cats", "seo_title": "Cats purr to heal", "script": script},
            {"id": "b", "category": "cats", "seo_title": "Cats purr to heal", "script": script},
        ]
    }), encoding="utf-8")
    out = build_health(tmp_path)
    assert out["queue"]["duplicate_scripts"] == 1
    assert "duplicate_scripts_in_queue" in out["issues"]
