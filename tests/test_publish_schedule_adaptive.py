from __future__ import annotations

from datetime import datetime, timezone

from utils.publish_schedule import active_slot_label, canonical_slots, is_active_slot, next_slot, slot_label


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
