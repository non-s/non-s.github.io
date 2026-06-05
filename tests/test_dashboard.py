"""Tests for scripts/build_dashboard.py — pure render, no network."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    """Reload the script in an isolated cwd so its module-level path
    constants honour the temp directory."""
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import importlib
    if "build_dashboard" in sys.modules:
        del sys.modules["build_dashboard"]
    import build_dashboard
    importlib.reload(build_dashboard)
    yield build_dashboard


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in rows for k in r.keys()})
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def test_main_writes_html_even_with_no_data(dashboard, tmp_path):
    dashboard.main()
    out = tmp_path / "_site" / "index.html"
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "channel dashboard" in body.lower()
    assert "<html" in body


def test_dashboard_includes_top_performers(dashboard, tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "latest.json").write_text(json.dumps({
        "pulled_at": "2026-05-18",
        "total_views_14d": 12345,
        "avg_view_pct": 67.5,
        "avg_humanity_score": 79.2,
        "humanity_label_counts": {"human": 3, "signature": 1},
        "below_60_pct": [],
        "category_avg_view_pct": {"cats": 72.0, "ocean": 55.0},
        "category_avg_growth_score": {"cats": 180.0, "ocean": 90.0},
        "format_avg_growth_score": {"animal_memory": 210.0},
        "production_recommendations": {
            "hot_categories": ["cats"],
            "slow_categories": ["ocean"],
            "hot_formats": ["animal_memory"],
            "exploit_mode": True,
            "double_down_titles": ["Major event today"],
            "next_actions": ["Make the next Short shorter."],
        },
        "top_performers": [
            {"video_id": "abc", "title": "Major event today",
             "story_format": "animal_memory",
             "views": 5000, "view_pct": 82.0,
             "humanity_score": 91, "humanity_label": "signature",
             "views_per_hour": 120.5, "growth_score": 420.0},
        ],
    }))
    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")
    assert "Major event today" in body
    assert "5,000" in body or "5000" in body
    assert "82.0" in body or "82" in body
    assert "Production recommendations" in body
    assert "Growth score by category" in body
    assert "Growth score by story format" in body
    assert "Exploit mode active" in body
    assert "120.5/h" in body
    assert "Avg humanity score" in body
    assert "signature" in body
    assert "Humanity mix" in body


def test_dashboard_renders_studio_queue_health(dashboard, tmp_path, monkeypatch):
    from utils import editorial
    monkeypatch.setattr(editorial.channel_memory, "_iter_recent", lambda days: iter(()))
    queue = tmp_path / "_data" / "stories_queue.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(json.dumps({"stories": [{
        "id": "a",
        "seo_title": "Chickens remember your face",
        "title": "Chickens remember your face",
        "category": "farm",
        "description": "A clip of chickens walking around a farmyard.",
        "hook": "Chickens remember your face.",
        "script": (
            "Chickens remember your face. I love this detail: they watch "
            "your eyes and voice, because familiar people make the flock "
            "calmer. That's why one farmer can walk in quietly while a "
            "stranger makes them freeze. Which farm animal should we "
            "decode next?"
        ),
        "thumbnail_text": "CHICKEN MEMORY",
        "yt_tags": ["chickens", "memory"],
        "score": 9,
        "source_url": "https://www.pexels.com/video/chickens/",
    }]}), encoding="utf-8")
    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")
    assert "Studio queue health" in body
    assert "Next best candidates" in body
    assert "Chickens remember your face" in body


def test_dashboard_renders_ab_winners(dashboard, tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "latest.json").write_text(json.dumps({
        "pulled_at": "2026-05-18", "total_views_14d": 100,
        "avg_view_pct": 60.0,
    }))
    (analytics / "experiments.json").write_text(json.dumps({
        "winners":    {"hook_style": "outcome_first"},
        "lift":       {"hook_style": {"lift": 8.4}},
        "axis_stats": {"hook_style": {"outcome_first": {"n": 10, "mean": 78.4},
                                       "question":      {"n": 10, "mean": 70.0}}},
    }))
    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")
    assert "outcome_first" in body
    assert "+8.4" in body


def test_dashboard_accepts_new_retention_field_name(dashboard, tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "latest.json").write_text(json.dumps({
        "pulled_at": "2026-06-02",
        "total_views": 321,
        "avg_view_percentage": 74.2,
        "top_performers": [{"title": "Octopus", "views": 100,
                            "average_view_percentage": 81.5}],
    }))
    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")
    assert "74.2" in body
    assert "81.5" in body


def test_dashboard_renders_cohort_timing(dashboard, tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "latest.json").write_text(json.dumps({
        "pulled_at": "2026-05-18", "total_views_14d": 100, "avg_view_pct": 60.0,
    }))
    (analytics / "cohort_timing.json").write_text(json.dumps({
        "recommended_utc_hours": [
            {"country": "US", "views": 500, "local_offset_h": -5, "utc_hour": 23},
            {"country": "BR", "views": 200, "local_offset_h": -3, "utc_hour": 21},
        ],
    }))
    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")
    assert "23:00 UTC" in body
    assert "21:00 UTC" in body
    assert "US" in body and "BR" in body


def test_dashboard_renders_sparkline(dashboard, tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    _write_csv(analytics / "2026-05-15.csv", [
        {"video_id": "a", "an_views": "100", "avg_view_pct": "60", "pulled_at": "2026-05-15"},
    ])
    _write_csv(analytics / "2026-05-16.csv", [
        {"video_id": "a", "an_views": "200", "avg_view_pct": "65", "pulled_at": "2026-05-16"},
    ])
    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")
    assert "<svg" in body
    assert "polyline" in body


def test_sparkline_handles_empty(dashboard):
    out = dashboard._sparkline_svg([])
    assert out == ""


def test_sparkline_produces_svg(dashboard):
    svg = dashboard._sparkline_svg([1.0, 2.0, 3.0])
    assert svg.startswith("<svg")
    assert "polyline" in svg
