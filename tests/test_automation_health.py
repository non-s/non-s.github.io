"""Tests for local automation health audit."""

from __future__ import annotations

import json
from pathlib import Path

from utils.automation_health import build_health


def test_automation_health_scores_queue_and_analytics(tmp_path: Path):
    data = tmp_path / "_data"
    (data / "analytics").mkdir(parents=True)
    (data / "stories_queue.json").write_text(
        json.dumps(
            {
                "stories": [
                    {
                        "id": "a",
                        "category": "cats",
                        "seo_title": "Cats purr to heal their bones",
                        "hook": "Cats purr to heal their bones.",
                        "script": "Cats purr to heal their bones. Watch the chest and paws because vibration helps tissue recover.",
                        "yt_tags": ["cats", "purring"],
                        "source_url": "https://www.pexels.com/video/cat/",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (data / "analytics" / "latest.json").write_text(
        json.dumps(
            {
                "metric_scope": "youtube_analytics_and_public_statistics",
                "avg_view_pct": 70,
                "total_views": 100,
                "shorts_tracked": 1,
            }
        ),
        encoding="utf-8",
    )
    out = build_health(tmp_path)
    assert out["queue"]["pending"] == 1
    assert out["seo"]["average_score"] >= 90
    assert "agency" in out
    assert out["analytics"]["metric_scope"] == "youtube_analytics_and_public_statistics"


def test_automation_health_flags_duplicate_scripts(tmp_path: Path):
    data = tmp_path / "_data"
    data.mkdir(parents=True)
    script = "Cats purr to heal their bones."
    (data / "stories_queue.json").write_text(
        json.dumps(
            {
                "stories": [
                    {"id": "a", "category": "cats", "seo_title": "Cats purr to heal", "script": script},
                    {"id": "b", "category": "cats", "seo_title": "Cats purr to heal", "script": script},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = build_health(tmp_path)
    assert out["queue"]["duplicate_scripts"] == 1
    assert "duplicate_scripts_in_queue" in out["issues"]


def test_automation_health_counts_only_operationally_publish_ready_items(tmp_path: Path):
    data = tmp_path / "_data"
    data.mkdir(parents=True)
    ready_fields = {
        "queue_prune": {"state": "publish_ready"},
        "publish_score": {"approved": True, "state": "publish_ready"},
        "editorial": {"approved": True},
    }
    (data / "stories_queue.json").write_text(
        json.dumps(
            {
                "stories": [
                    {
                        **ready_fields,
                        "id": "held",
                        "category": "birds",
                        "seo_title": "Birds see ultraviolet patterns we miss",
                        "script": "Birds see ultraviolet patterns before the feather signal changes.",
                    },
                    {
                        **ready_fields,
                        "id": "paused",
                        "category": "wildlife",
                        "seo_title": "Elephants feel rumbles through the ground",
                        "script": "Elephants feel rumbles through the ground before the herd turns.",
                    },
                    {
                        **ready_fields,
                        "id": "active",
                        "category": "plants",
                        "seo_title": "Plants count touches before snapping shut",
                        "script": "Plants count touches before snapping shut around an insect.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (data / "agency_gate.json").write_text(
        json.dumps({"held_items": [{"id": "held", "reasons": ["success_recovery_hook_required"]}]}),
        encoding="utf-8",
    )
    (data / "ops_guardian.json").write_text(
        json.dumps({"paused_topics": [{"category": "wildlife", "reason": "low_retention"}]}),
        encoding="utf-8",
    )

    out = build_health(tmp_path)

    assert out["queue"]["pending"] == 3
    assert out["queue"]["publish_ready"] == 1


def test_automation_health_counts_nature_subject_frontload(tmp_path: Path):
    data = tmp_path / "_data"
    data.mkdir(parents=True)
    (data / "stories_queue.json").write_text(
        json.dumps(
            {
                "stories": [
                    {
                        "id": "trees",
                        "category": "trees",
                        "seo_title": "Trees signal through root network",
                        "script": "Trees signal through root network before the forest changes.",
                    },
                    {
                        "id": "earth",
                        "category": "earth_from_space",
                        "seo_title": "Earth systems signal through cloud patterns",
                        "script": "Earth systems signal through cloud patterns before the weather changes.",
                    },
                    {
                        "id": "plant",
                        "category": "plants",
                        "seo_title": "Carnivorous Plant uses movement before it moves",
                        "script": "Carnivorous Plant uses movement before the insect gets close.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    out = build_health(tmp_path)

    assert out["seo"]["average_score"] >= 90
    assert out["seo"]["subject_frontloaded_pct"] == 100.0
    assert "seo_average_below_target" not in out["issues"]
    assert "subject_frontload_below_target" not in out["issues"]
