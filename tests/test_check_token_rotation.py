"""Tests for scripts/check_token_rotation.py."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import scripts.check_token_rotation as rotation


def test_check_is_overdue_when_state_file_does_not_exist(tmp_path):
    result = rotation.check(path=tmp_path / "missing.json")
    assert result["overdue"] is True
    assert result["reason"] == "never_recorded"


def test_check_is_overdue_when_last_rotated_is_null(tmp_path):
    path = tmp_path / "token_rotation.json"
    path.write_text(json.dumps({"last_rotated": None, "rotate_after_days": 180}), encoding="utf-8")

    result = rotation.check(path=path)
    assert result["overdue"] is True
    assert result["reason"] == "never_recorded"


def test_check_is_current_within_the_rotation_window(tmp_path):
    path = tmp_path / "token_rotation.json"
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    rotated_at = now - timedelta(days=30)
    path.write_text(json.dumps({"last_rotated": rotated_at.isoformat(), "rotate_after_days": 180}), encoding="utf-8")

    result = rotation.check(now=now, path=path)
    assert result["overdue"] is False
    assert result["days_since"] == 30


def test_check_is_overdue_past_the_rotation_window(tmp_path):
    path = tmp_path / "token_rotation.json"
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    rotated_at = now - timedelta(days=200)
    path.write_text(json.dumps({"last_rotated": rotated_at.isoformat(), "rotate_after_days": 180}), encoding="utf-8")

    result = rotation.check(now=now, path=path)
    assert result["overdue"] is True
    assert result["reason"] == "overdue"


def test_check_honors_a_custom_rotate_after_days(tmp_path):
    path = tmp_path / "token_rotation.json"
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    rotated_at = now - timedelta(days=40)
    path.write_text(json.dumps({"last_rotated": rotated_at.isoformat(), "rotate_after_days": 30}), encoding="utf-8")

    result = rotation.check(now=now, path=path)
    assert result["overdue"] is True


def test_check_handles_an_unparseable_date_as_overdue(tmp_path):
    path = tmp_path / "token_rotation.json"
    path.write_text(json.dumps({"last_rotated": "not-a-date"}), encoding="utf-8")

    result = rotation.check(path=path)
    assert result["overdue"] is True
    assert result["reason"] == "unparseable_date"


def test_mark_rotated_records_today_and_check_then_reports_current(tmp_path):
    path = tmp_path / "token_rotation.json"
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)

    rotation.mark_rotated(now=now, path=path)
    result = rotation.check(now=now, path=path)

    assert result["overdue"] is False
    assert result["days_since"] == 0


def test_mark_rotated_preserves_a_custom_rotate_after_days(tmp_path):
    path = tmp_path / "token_rotation.json"
    path.write_text(json.dumps({"last_rotated": None, "rotate_after_days": 90}), encoding="utf-8")

    state = rotation.mark_rotated(path=path)

    assert state["rotate_after_days"] == 90


def test_main_returns_one_when_overdue(monkeypatch, tmp_path):
    monkeypatch.setattr(rotation, "STATE_PATH", tmp_path / "missing.json")
    monkeypatch.setattr("sys.argv", ["check_token_rotation.py"])
    assert rotation.main() == 1


def test_main_mark_rotated_flag_returns_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(rotation, "STATE_PATH", tmp_path / "token_rotation.json")
    monkeypatch.setattr("sys.argv", ["check_token_rotation.py", "--mark-rotated"])
    assert rotation.main() == 0
    assert json.loads((tmp_path / "token_rotation.json").read_text())["last_rotated"]
