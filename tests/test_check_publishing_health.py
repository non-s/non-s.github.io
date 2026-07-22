"""Tests for scripts/check_publishing_health.py."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import scripts.check_publishing_health as health


def _write_marker(videos_dir, name, created_at: str | None):
    marker = {"upload_intent": {"created_at": created_at}} if created_at is not None else {}
    (videos_dir / name).write_text(json.dumps(marker), encoding="utf-8")


def test_most_recent_upload_ts_returns_none_when_no_markers(tmp_path):
    assert health.most_recent_upload_ts(tmp_path) is None


def test_most_recent_upload_ts_ignores_markers_without_a_timestamp(tmp_path):
    _write_marker(tmp_path, "short-1.done", None)
    assert health.most_recent_upload_ts(tmp_path) is None


def test_most_recent_upload_ts_picks_the_latest_across_markers(tmp_path):
    _write_marker(tmp_path, "short-1.done", "2026-07-01T00:00:00+00:00")
    _write_marker(tmp_path, "short-2.done", "2026-07-10T12:00:00+00:00")
    _write_marker(tmp_path, "mix-1.done", "2026-07-05T00:00:00+00:00")

    latest = health.most_recent_upload_ts(tmp_path)
    assert latest == datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


def test_check_reports_healthy_when_a_recent_upload_exists(tmp_path):
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    _write_marker(tmp_path, "short-1.done", (now - timedelta(hours=2)).isoformat())

    result = health.check(stale_hours=26.0, now=now, videos_dir=tmp_path)

    assert result["degraded"] is False
    assert result["reason"] == "healthy"
    assert result["hours_since"] == 2.0


def test_check_reports_degraded_when_the_latest_upload_is_too_old(tmp_path):
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    _write_marker(tmp_path, "short-1.done", (now - timedelta(hours=30)).isoformat())

    result = health.check(stale_hours=26.0, now=now, videos_dir=tmp_path)

    assert result["degraded"] is True
    assert result["reason"] == "stale"
    assert result["hours_since"] == 30.0


def test_check_reports_degraded_when_no_markers_exist_at_all(tmp_path):
    result = health.check(stale_hours=26.0, videos_dir=tmp_path)

    assert result["degraded"] is True
    assert result["reason"] == "no_uploads_found"


def test_main_returns_zero_when_publishing_is_disabled(monkeypatch, tmp_path):
    monkeypatch.delenv("YOUTUBE_PUBLISHING_ENABLED", raising=False)
    monkeypatch.setattr(health, "VIDEOS_DIR", tmp_path)

    assert health.main() == 0


def test_main_returns_one_when_publishing_enabled_and_degraded(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUTUBE_PUBLISHING_ENABLED", "1")
    monkeypatch.setattr(health, "VIDEOS_DIR", tmp_path)

    assert health.main() == 1


def test_main_returns_zero_when_publishing_enabled_and_healthy(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUTUBE_PUBLISHING_ENABLED", "1")
    monkeypatch.setattr(health, "VIDEOS_DIR", tmp_path)
    _write_marker(tmp_path, "short-1.done", datetime.now(timezone.utc).isoformat())

    assert health.main() == 0


def test_main_honors_a_custom_stale_hours_override(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUTUBE_PUBLISHING_ENABLED", "1")
    monkeypatch.setenv("PUBLISHING_STALE_HOURS", "1")
    monkeypatch.setattr(health, "VIDEOS_DIR", tmp_path)
    _write_marker(tmp_path, "short-1.done", (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())

    assert health.main() == 1
