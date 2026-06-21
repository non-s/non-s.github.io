from __future__ import annotations

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
