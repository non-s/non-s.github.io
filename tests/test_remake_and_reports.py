"""Tests for remake backlog, weekly report and publish-window helpers."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.remake_engine import build_backlog
from scripts.weekly_report import build_markdown


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_remake_engine_builds_backlog(tmp_path: Path):
    _write(tmp_path / "_data" / "analytics" / "latest.json", {
        "remake_candidates": [{
            "video_id": "abc",
            "title": "Cats remember faces",
            "views": 500,
            "retention": 67,
            "growth_score": 180,
            "action": "make sequel",
        }]
    })
    out = build_backlog(tmp_path)
    assert out["count"] == 1
    assert out["remakes"][0]["source_video_id"] == "abc"
    assert out["remakes"][0]["candidate_titles"]
    assert "retention_surgery" in out["remakes"][0]


def test_remake_engine_falls_back_to_top_performers(tmp_path: Path):
    _write(tmp_path / "_data" / "analytics" / "latest.json", {
        "top_performers": [{
            "video_id": "top1",
            "title": "Ducklings know math before they swim",
            "views": 1200,
            "view_pct": 0,
            "growth_score": 500,
            "postmortem": {"likely_causes": ["hook_needs_work"]},
        }]
    })
    out = build_backlog(tmp_path)
    assert out["count"] == 1
    assert out["remakes"][0]["source_video_id"] == "top1"


def test_weekly_report_contains_core_sections(tmp_path: Path):
    _write(tmp_path / "_data" / "analytics" / "latest.json", {
        "total_views": 1000,
        "avg_view_pct": 62,
        "subscribers_gained": 5,
        "production_recommendations": {"hot_categories": ["farm"]},
    })
    _write(tmp_path / "_data" / "ops_guardian.json", {
        "risk": {"level": "normal", "score": 12},
        "paused_topics": [{"category": "cats", "reason": "retention_below_45", "retention": 37}],
        "executive_report": {"next_actions": ["Scale farm."]},
    })
    _write(tmp_path / "_data" / "automation_health.json", {"state": "excellent", "score": 100})
    _write(tmp_path / "_data" / "remake_backlog.json", {
        "remakes": [{"source_title": "Cows remember faces", "action": "make sequel"}],
    })
    _write(tmp_path / "_data" / "trend_radar.json", {
        "topics": [{"animal": "orca", "category": "ocean", "trend_score": 88,
                    "mentions": 3, "top_titles": ["Rare orca behavior"]}],
    })
    body = build_markdown(tmp_path)
    assert "# Wild Brief Weekly Report" in body
    assert "## What To Scale" in body
    assert "farm" in body
    assert "## Trend Radar" in body
    assert "orca" in body
    assert "Cows remember faces" in body
