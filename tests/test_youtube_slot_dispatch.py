from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from scripts import youtube_slot_dispatch as dispatch


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_run_covers_only_its_own_hourly_slot():
    previous_slot_run = {"created_at": "2026-06-21T10:55:12Z"}
    current_slot_run = {"created_at": "2026-06-21T11:02:03Z"}
    slot = _dt("2026-06-21T11:00:00Z")

    assert not dispatch.run_covers_slot(previous_slot_run, slot)
    assert dispatch.run_covers_slot(current_slot_run, slot)


def test_run_at_next_hour_does_not_cover_previous_slot():
    next_slot_run = {"created_at": "2026-06-21T12:00:01Z"}
    slot = _dt("2026-06-21T11:00:00Z")

    assert not dispatch.run_covers_slot(next_slot_run, slot)


def test_latest_auditable_slot_respects_grace_window():
    now = _dt("2026-06-21T11:50:00Z")
    slot = dispatch.latest_auditable_slot(
        now,
        grace=timedelta(minutes=12),
        publish_slots=("10:00", "11:00", "12:00"),
    )

    assert slot == _dt("2026-06-21T11:00:00Z")


def test_parse_slots_defaults_to_full_day():
    slots = dispatch.parse_slots("")

    assert slots[0] == "00:00"
    assert slots[-1] == "23:00"
    assert len(slots) == 24


def test_successful_run_without_upload_intent_does_not_satisfy_slot(tmp_path):
    run = {
        "created_at": "2026-06-21T13:07:00Z",
        "status": "completed",
        "conclusion": "success",
    }
    slot = _dt("2026-06-21T13:00:00Z")

    assert not dispatch.successful_run_satisfies_slot(
        run,
        slot,
        upload_intents_path=tmp_path / "upload_intents.jsonl",
    )


def test_successful_run_requires_uploaded_slot_intent(tmp_path):
    path = tmp_path / "upload_intents.jsonl"
    path.write_text(
        json.dumps({"slot": "2026-06-21T13:00Z", "status": "uploaded", "video_id": "abc123"}) + "\n",
        encoding="utf-8",
    )
    run = {
        "created_at": "2026-06-21T13:07:00Z",
        "status": "completed",
        "conclusion": "success",
    }
    slot = _dt("2026-06-21T13:00:00Z")

    assert dispatch.successful_run_satisfies_slot(run, slot, upload_intents_path=path)


def test_dispatch_recovers_success_run_without_uploaded_intent(monkeypatch, tmp_path):
    calls = []

    def fake_request_json(token, method, url, body=None):
        calls.append((method, url, body))
        if method == "GET":
            return {
                "workflow_runs": [
                    {
                        "created_at": "2026-06-21T13:07:00Z",
                        "status": "completed",
                        "conclusion": "success",
                        "event": "workflow_dispatch",
                        "html_url": "https://example.test/run",
                    }
                ]
            }
        return None

    monkeypatch.setattr(dispatch, "request_json", fake_request_json)

    result = dispatch.dispatch_if_missing(
        token="token",
        repo="non-s/non-s.github.io",
        workflow="youtube-bot.yml",
        slot=_dt("2026-06-21T13:00:00Z"),
        reason="recover uncovered slot",
        upload_intents_path=tmp_path / "upload_intents.jsonl",
    )

    assert result == 0
    assert any(method == "POST" for method, _, _ in calls)


def test_dispatch_skips_recovery_when_slot_has_uploaded_intent(monkeypatch, tmp_path):
    path = tmp_path / "upload_intents.jsonl"
    path.write_text(
        json.dumps({"slot": "2026-06-21T13:00Z", "status": "uploaded", "video_id": "abc123"}) + "\n",
        encoding="utf-8",
    )
    calls = []

    def fake_request_json(token, method, url, body=None):
        calls.append((method, url, body))
        if method == "GET":
            return {
                "workflow_runs": [
                    {
                        "created_at": "2026-06-21T13:07:00Z",
                        "status": "completed",
                        "conclusion": "success",
                        "event": "workflow_dispatch",
                        "html_url": "https://example.test/run",
                    }
                ]
            }
        return None

    monkeypatch.setattr(dispatch, "request_json", fake_request_json)

    result = dispatch.dispatch_if_missing(
        token="token",
        repo="non-s/non-s.github.io",
        workflow="youtube-bot.yml",
        slot=_dt("2026-06-21T13:00:00Z"),
        reason="recover covered slot",
        upload_intents_path=path,
    )

    assert result == 0
    assert not any(method == "POST" for method, _, _ in calls)
