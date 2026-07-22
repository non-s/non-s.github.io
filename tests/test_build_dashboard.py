"""Tests for scripts/build_dashboard.py's trend history."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_dashboard as dashboard  # noqa: E402


def test_load_history_returns_empty_list_when_file_missing(tmp_path):
    assert dashboard._load_history(tmp_path / "missing.jsonl") == []


def test_append_history_snapshot_writes_one_row_per_day(tmp_path):
    path = tmp_path / "history.jsonl"
    day1 = datetime(2026, 7, 1, tzinfo=timezone.utc)

    dashboard.append_history_snapshot(total_views=100, subscribers_gained=5, shorts_published=10, now=day1, path=path)

    rows = dashboard._load_history(path)
    assert rows == [
        {
            "day": "2026-07-01",
            "total_views": 100,
            "subscribers_gained": 5,
            "shorts_published": 10,
            "title_collision_rate": 0.0,
        }
    ]


def test_append_history_snapshot_updates_same_day_instead_of_duplicating(tmp_path):
    path = tmp_path / "history.jsonl"
    day1 = datetime(2026, 7, 1, tzinfo=timezone.utc)

    dashboard.append_history_snapshot(total_views=100, subscribers_gained=5, shorts_published=10, now=day1, path=path)
    dashboard.append_history_snapshot(total_views=150, subscribers_gained=8, shorts_published=11, now=day1, path=path)

    rows = dashboard._load_history(path)
    assert len(rows) == 1
    assert rows[0]["total_views"] == 150


def test_append_history_snapshot_accumulates_across_days(tmp_path):
    path = tmp_path / "history.jsonl"
    day1 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    day2 = datetime(2026, 7, 2, tzinfo=timezone.utc)

    dashboard.append_history_snapshot(total_views=100, subscribers_gained=5, shorts_published=10, now=day1, path=path)
    dashboard.append_history_snapshot(total_views=200, subscribers_gained=9, shorts_published=12, now=day2, path=path)

    rows = dashboard._load_history(path)
    assert [r["day"] for r in rows] == ["2026-07-01", "2026-07-02"]


def test_load_history_skips_malformed_lines(tmp_path):
    path = tmp_path / "history.jsonl"
    path.write_text('{"day": "2026-07-01", "total_views": 1}\nnot json\n', encoding="utf-8")
    rows = dashboard._load_history(path)
    assert len(rows) == 1


def test_sparkline_svg_returns_empty_string_for_fewer_than_two_points():
    assert dashboard._sparkline_svg([]) == ""
    assert dashboard._sparkline_svg([5.0]) == ""


def test_sparkline_svg_renders_a_polyline_for_two_or_more_points():
    svg = dashboard._sparkline_svg([10.0, 20.0, 5.0])
    assert svg.startswith("<svg")
    assert "<polyline" in svg


def test_render_html_shows_trend_table_once_history_has_two_or_more_days(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "_data" / "analytics").mkdir(parents=True)
    (tmp_path / "_videos").mkdir()

    history_path = tmp_path / "_data" / "analytics" / "dashboard_history.jsonl"
    dashboard.append_history_snapshot(
        total_views=100,
        subscribers_gained=5,
        shorts_published=1,
        now=datetime(2026, 7, 1, tzinfo=timezone.utc),
        path=history_path,
    )
    dashboard.append_history_snapshot(
        total_views=200,
        subscribers_gained=9,
        shorts_published=2,
        now=datetime(2026, 7, 2, tzinfo=timezone.utc),
        path=history_path,
    )

    body = dashboard.render_html()

    assert "Trend (last" in body
    assert "2026-07-01" in body
    assert "2026-07-02" in body
    assert "<polyline" in body


def test_append_history_snapshot_records_title_collision_rate(tmp_path):
    path = tmp_path / "history.jsonl"
    dashboard.append_history_snapshot(
        total_views=100,
        subscribers_gained=5,
        shorts_published=10,
        title_collision_rate=0.5,
        now=datetime(2026, 7, 1, tzinfo=timezone.utc),
        path=path,
    )
    rows = dashboard._load_history(path)
    assert rows[0]["title_collision_rate"] == 0.5


def test_render_html_shows_branding_mix_and_collision_rate_from_real_markers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "_data" / "analytics").mkdir(parents=True)
    videos_dir = tmp_path / "_videos"
    videos_dir.mkdir()
    (videos_dir / "short-1.done").write_text(
        json.dumps(
            {
                "video_id": "V1",
                "title": "Trovão ao Longe e Chuva para Aliviar a Insônia",
                "upload_title_dedupe": {"applied": True},
            }
        ),
        encoding="utf-8",
    )
    (videos_dir / "short-2.done").write_text(
        json.dumps(
            {
                "video_id": "V2",
                "title": "Som de Chuva Suave para Ajudar o Bebê a Dormir",
                "upload_title_dedupe": {"applied": False},
            }
        ),
        encoding="utf-8",
    )

    body = dashboard.render_html()

    assert "Branding mix" in body
    assert "Som de Trovão" in body
    assert "Chuva para o Bebê Dormir" in body
    assert "Title collision rate" in body
    assert "50%" in body


def test_render_html_shows_placeholder_when_history_has_fewer_than_two_days(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "_data" / "analytics").mkdir(parents=True)
    (tmp_path / "_videos").mkdir()

    body = dashboard.render_html()

    assert "Not enough daily snapshots yet" in body


def test_main_appends_a_history_row_reflecting_shorts_published(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "_data" / "analytics").mkdir(parents=True)
    videos_dir = tmp_path / "_videos"
    videos_dir.mkdir()
    (videos_dir / "short-1.done").write_text(json.dumps({"video_id": "VID1"}), encoding="utf-8")

    dashboard.main()

    rows = dashboard._load_history(tmp_path / "_data" / "analytics" / "dashboard_history.jsonl")
    assert len(rows) == 1
    assert rows[0]["shorts_published"] == 1
