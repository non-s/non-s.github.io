from __future__ import annotations

from datetime import datetime, timezone

from utils.publish_schedule import (
    active_slot_label,
    canonical_slots,
    event_schedule_slot_label,
    is_active_slot,
    next_slot,
    slot_label,
)


def test_active_slot_honors_adaptive_schedule():
    env = {"ADAPTIVE_CADENCE_ENABLED": "1"}
    schedule = {"recommended_slots": ["05:23", "14:23", "23:23"]}

    assert is_active_slot(datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc), schedule, env) is True
    assert is_active_slot(datetime(2026, 6, 11, 19, 23, tzinfo=timezone.utc), schedule, env) is False


def test_active_slot_allows_late_recovery_inside_grace_window():
    env = {"ADAPTIVE_CADENCE_ENABLED": "1", "PUBLISH_SLOT_GRACE_MINUTES": "90"}
    schedule = {"recommended_slots": ["05:23", "14:23", "23:23"]}

    late = datetime(2026, 6, 11, 15, 43, tzinfo=timezone.utc)

    assert active_slot_label(late, schedule, env) == "14:23"
    assert is_active_slot(late, schedule, env) is True


def test_active_slot_rejects_late_recovery_after_grace_window():
    env = {"ADAPTIVE_CADENCE_ENABLED": "1", "PUBLISH_SLOT_GRACE_MINUTES": "90"}
    schedule = {"recommended_slots": ["05:23", "14:23", "23:23"]}

    assert is_active_slot(datetime(2026, 6, 11, 16, 0, tzinfo=timezone.utc), schedule, env) is False


def test_delayed_github_schedule_event_recovers_intended_slot():
    env = {
        "ADAPTIVE_CADENCE_ENABLED": "1",
        "GITHUB_EVENT_NAME": "schedule",
        "PUBLISH_EVENT_SCHEDULE_CRON": "43 0,6,15,20 * * *",
    }
    schedule = {"recommended_slots": ["05:23", "14:23", "23:23"]}
    delayed = datetime(2026, 6, 12, 9, 39, tzinfo=timezone.utc)

    assert event_schedule_slot_label(delayed, schedule, env) == "05:23"
    assert active_slot_label(delayed, schedule, env) == "05:23"
    assert is_active_slot(delayed, schedule, env) is True


def test_delayed_github_schedule_event_honors_max_delay():
    env = {
        "ADAPTIVE_CADENCE_ENABLED": "1",
        "GITHUB_EVENT_NAME": "schedule",
        "PUBLISH_EVENT_SCHEDULE_CRON": "43 0,6,15,20 * * *",
        "PUBLISH_EVENT_MAX_DELAY_MINUTES": "120",
    }
    schedule = {"recommended_slots": ["05:23", "14:23", "23:23"]}

    assert event_schedule_slot_label(datetime(2026, 6, 12, 9, 39, tzinfo=timezone.utc), schedule, env) == ""


def test_hourly_recovery_crons_map_to_top_of_hour_slot():
    schedule = {"recommended_slots": ["06:00"]}

    for minute in ("20", "40"):
        env = {
            "ADAPTIVE_CADENCE_ENABLED": "1",
            "GITHUB_EVENT_NAME": "schedule",
            "PUBLISH_EVENT_SCHEDULE_CRON": f"{minute} * * * *",
        }
        delayed = datetime(2026, 6, 12, 6, 55, tzinfo=timezone.utc)

        assert event_schedule_slot_label(delayed, schedule, env) == "06:00"


def test_legacy_mode_allows_current_behavior():
    env = {"ADAPTIVE_CADENCE_ENABLED": "0"}
    schedule = {"recommended_slots": ["05:23"]}

    assert is_active_slot(datetime(2026, 6, 11, 19, 23, tzinfo=timezone.utc), schedule, env) is True


def test_slot_helpers_return_stable_utc_labels():
    env = {"ADAPTIVE_CADENCE_ENABLED": "1"}
    schedule = {"recommended_slots": ["05:23", "14:23", "23:23"]}

    assert slot_label(datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc)) == "05:23"
    assert next_slot(datetime(2026, 6, 11, 5, 24, tzinfo=timezone.utc), schedule, env) == "14:23"


def test_optional_flex_slot_is_added_when_enabled():
    env = {"ALLOW_FLEX_SLOT": "1", "FLEX_SLOT_UTC": "07:13"}

    assert "07:13" in canonical_slots(env)
