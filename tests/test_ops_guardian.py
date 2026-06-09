"""Tests for the operations guardian."""
from __future__ import annotations

import json
from pathlib import Path

from utils.ops_guardian import build_ops_report, should_enforce_pause


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ops_guardian_normal_with_healthy_retention(tmp_path: Path):
    _write(tmp_path / "_data" / "analytics" / "latest.json", {
        "total_views": 1000,
        "shorts_tracked": 10,
        "avg_view_pct": 68,
        "below_60_pct": ["a"],
        "category_avg_view_pct": {"cats": 70, "ocean": 64},
        "production_recommendations": {"hot_categories": ["cats"]},
    })
    _write(tmp_path / "_data" / "automation_health.json", {"state": "excellent"})
    out = build_ops_report(tmp_path)
    assert out["risk"]["level"] == "normal"
    assert [item["utc_hour"] for item in out["scheduler"]["recommended_utc_hours"]] == [5, 14, 19, 23]
    assert out["scheduler"]["recommended_utc_hours"][0]["reason"] == "default_global_daypart"
    assert out["inventory_forecast"]["state"] == "thin"
    assert out["executive_report"]["what_to_scale"] == ["cats"]
    assert not should_enforce_pause(out)


def test_ops_guardian_pauses_weak_topics_and_can_enforce(tmp_path: Path):
    _write(tmp_path / "_data" / "analytics" / "latest.json", {
        "shorts_tracked": 6,
        "avg_view_pct": 48,
        "below_60_pct": ["a", "b", "c", "d"],
        "category_avg_view_pct": {"cats": 38, "farm": 34, "ocean": 42},
        "category_avg_growth_score": {"cats": 30, "farm": 20, "ocean": 40},
    })
    _write(tmp_path / "_data" / "automation_health.json", {"state": "watch"})
    out = build_ops_report(tmp_path)
    assert out["risk"]["level"] == "critical"
    assert [item["category"] for item in out["paused_topics"]] == ["farm", "cats", "ocean"]
    assert should_enforce_pause(out)


def test_ops_guardian_uses_cohort_timing_when_available(tmp_path: Path):
    _write(tmp_path / "_data" / "analytics" / "latest.json", {
        "shorts_tracked": 1,
        "avg_view_pct": 60,
    })
    _write(tmp_path / "_data" / "analytics" / "cohort_timing.json", {
        "recommended_utc_hours": [
            {"utc_hour": 23, "country": "US", "views": 500},
            {"utc_hour": 21, "country": "BR", "views": 200},
        ]
    })
    out = build_ops_report(tmp_path)
    assert [item["utc_hour"] for item in out["scheduler"]["recommended_utc_hours"][:2]] == [23, 21]
    assert out["scheduler"]["recommended_utc_hours"][0]["reason"] == "audience_cohort"


def test_ops_guardian_aggregates_visual_qa(tmp_path: Path):
    marker = {
        "visual_qa": {
            "checked": True,
            "approved": False,
            "thumbnail_quality": 4,
            "reason": "unrelated animal",
        },
        "local_visual_qa": {"checked": True, "score": 4, "reason": "too_dark"},
    }
    _write(tmp_path / "_videos" / "a.done", marker)
    _write(tmp_path / "_data" / "analytics" / "latest.json", {"avg_view_pct": 70, "shorts_tracked": 1})
    out = build_ops_report(tmp_path)
    assert out["visual_quality"]["checked"] == 1
    assert out["visual_quality"]["rejected"] == 1
    assert out["visual_quality"]["low_quality"] == 1
    assert out["visual_quality"]["local_checked"] == 1
    assert out["visual_quality"]["local_low_quality"] == 1
    assert out["visual_quality"]["top_reasons"] == {"unrelated animal": 1, "too_dark": 1}


def test_ops_guardian_series_plan_reads_queue(tmp_path: Path):
    _write(tmp_path / "_data" / "analytics" / "latest.json", {
        "avg_view_pct": 62,
        "shorts_tracked": 3,
        "series_avg_engagement": {"Pet Secrets": 5, "Ocean Mysteries": 2},
    })
    _write(tmp_path / "_data" / "stories_queue.json", {
        "stories": [
            {"category": "cats"},
            {"category": "cats"},
            {"category": "ocean", "consumed": True},
        ]
    })
    out = build_ops_report(tmp_path)
    assert out["series_plan"]["series_to_scale"] == ["Pet Secrets", "Ocean Mysteries"]
    assert out["series_plan"]["queue_categories"] == {"cats": 2}
