import json
from datetime import datetime, timedelta, timezone

import pytest

import scripts.check_mix_publish_due as check_mix_publish_due


def _write_marker(directory, name, *, publish_ts_utc, video_id="VID1"):
    path = directory / name
    path.write_text(json.dumps({"publish_ts_utc": publish_ts_utc, "video_id": video_id}), encoding="utf-8")
    return path


def test_prefers_upload_intent_created_at_over_publish_ts_utc(tmp_path):
    """Regression: publish_ts_utc can be a *future* scheduled-publish time
    when YOUTUBE_SCHEDULE_UPLOADS is on (same reasoning as
    scripts/check_publishing_health.py) -- the real upload completion
    time must win so a scheduled-for-later marker can't understate how
    long it's actually been since a mix last published."""
    real_upload = datetime.now(timezone.utc) - timedelta(hours=10)
    future_scheduled = datetime.now(timezone.utc) + timedelta(hours=6)
    path = tmp_path / "mix-lofimix-1-1.done"
    path.write_text(
        json.dumps(
            {
                "publish_ts_utc": future_scheduled.isoformat(),
                "upload_intent": {"created_at": real_upload.isoformat()},
                "video_id": "SCHEDULED1",
            }
        ),
        encoding="utf-8",
    )

    last_ts, last_id = check_mix_publish_due.last_mix_publish(tmp_path)

    assert abs((last_ts - real_upload).total_seconds()) < 1
    assert last_id == "SCHEDULED1"


def test_due_when_no_marker_exists_yet(tmp_path):
    """Regression: a repo with no mix ever published must not be blocked
    forever waiting for a marker that can never appear."""
    last_ts, last_id = check_mix_publish_due.last_mix_publish(tmp_path)
    assert last_ts is None
    assert last_id == ""


def test_not_due_before_3_hours_have_passed(tmp_path, monkeypatch):
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    _write_marker(tmp_path, "mix-lofimix-1-1.done", publish_ts_utc=recent.isoformat())
    monkeypatch.setattr(check_mix_publish_due, "VIDEOS_DIR", tmp_path)

    last_ts, _ = check_mix_publish_due.last_mix_publish(tmp_path)
    hours_since = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600.0
    assert hours_since < check_mix_publish_due.MIN_HOURS_BETWEEN_PUBLISHES


def test_due_once_3_hours_have_passed(tmp_path):
    old = datetime.now(timezone.utc) - timedelta(hours=4)
    _write_marker(tmp_path, "mix-lofimix-1-1.done", publish_ts_utc=old.isoformat())

    last_ts, last_id = check_mix_publish_due.last_mix_publish(tmp_path)
    hours_since = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600.0
    assert hours_since >= check_mix_publish_due.MIN_HOURS_BETWEEN_PUBLISHES
    assert last_id == "VID1"


def test_picks_the_newest_marker_when_several_exist(tmp_path):
    older = datetime.now(timezone.utc) - timedelta(hours=48)
    newer = datetime.now(timezone.utc) - timedelta(hours=2)
    _write_marker(tmp_path, "mix-lofimix-1-1.done", publish_ts_utc=older.isoformat(), video_id="OLD")
    _write_marker(tmp_path, "mix-lofimix-2-2.done", publish_ts_utc=newer.isoformat(), video_id="NEW")

    last_ts, last_id = check_mix_publish_due.last_mix_publish(tmp_path)
    assert last_id == "NEW"
    assert abs((last_ts - newer).total_seconds()) < 1


def test_ignores_markers_with_missing_or_unparseable_timestamp(tmp_path):
    _write_marker(tmp_path, "mix-lofimix-1-1.done", publish_ts_utc="")
    _write_marker(tmp_path, "mix-lofimix-2-2.done", publish_ts_utc="not-a-timestamp")

    last_ts, last_id = check_mix_publish_due.last_mix_publish(tmp_path)
    assert last_ts is None
    assert last_id == ""


def test_main_json_output_reports_due_and_hours_since(tmp_path, monkeypatch, capsys):
    old = datetime.now(timezone.utc) - timedelta(hours=30)
    _write_marker(tmp_path, "mix-lofimix-1-1.done", publish_ts_utc=old.isoformat(), video_id="ABC123")
    monkeypatch.setattr(check_mix_publish_due, "VIDEOS_DIR", tmp_path)
    monkeypatch.setattr(check_mix_publish_due.sys, "argv", ["check_mix_publish_due.py", "--json"])

    assert check_mix_publish_due.main() == 0

    out = json.loads(capsys.readouterr().out)
    assert out["due"] is True
    assert out["hours_since_last_publish"] == pytest.approx(30.0, abs=0.1)
    assert out["last_video_id"] == "ABC123"


def test_main_json_output_not_due_yet(tmp_path, monkeypatch, capsys):
    recent = datetime.now(timezone.utc) - timedelta(minutes=10)
    _write_marker(tmp_path, "mix-lofimix-1-1.done", publish_ts_utc=recent.isoformat())
    monkeypatch.setattr(check_mix_publish_due, "VIDEOS_DIR", tmp_path)
    monkeypatch.setattr(check_mix_publish_due.sys, "argv", ["check_mix_publish_due.py", "--json"])

    check_mix_publish_due.main()

    out = json.loads(capsys.readouterr().out)
    assert out["due"] is False
