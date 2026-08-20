from __future__ import annotations

import numpy as np

from utils.liquid_wire_timeline import (
    CreativeEvent,
    audit_narrative_arc,
    build_timeline,
    ensure_narrative_arc,
    event_envelope,
    narrative_state,
    visual_state,
)

MUSIC = {"beat_seconds": 0.9, "meter": 4}


def test_timeline_is_deterministic_and_has_dramatic_variety() -> None:
    first = build_timeline(1234, 35.0, MUSIC)
    second = build_timeline(1234, 35.0, MUSIC)
    assert first == second
    assert len(first) >= 3
    assert len({event.kind for event in first}) >= 2


def test_events_are_inside_duration_and_never_repeat_immediately() -> None:
    events = build_timeline(99, 180.0, MUSIC)
    assert all(0.0 <= event.start < 180.0 for event in events)
    assert all(left.kind != right.kind for left, right in zip(events, events[1:], strict=False))


def test_event_envelope_is_smooth_and_bounded() -> None:
    event = build_timeline(42, 35.0, MUSIC)[0]
    times = np.linspace(event.start - 0.1, event.start + event.duration + 0.1, 1000)
    envelope = event_envelope(times, event)
    assert float(np.min(envelope)) == 0.0
    assert 0.99 < float(np.max(envelope)) <= 1.0
    assert float(event_envelope(event.start, event)) == 0.0
    assert float(event_envelope(event.start + event.duration, event)) < 1e-20


def test_visual_state_responds_to_event_center() -> None:
    event = build_timeline(7, 35.0, MUSIC)[0]
    idle = visual_state(0.0, [event])
    peak = visual_state(event.start + event.duration / 2, [event])
    assert idle["total"] == 0.0
    assert peak[event.kind] > 0.0
    assert peak["total"] == peak[event.kind]


def test_every_procedural_timeline_has_complete_dramatic_grammar() -> None:
    for seed in range(50):
        events = build_timeline(seed, 35, MUSIC)
        report = audit_narrative_arc(events, 35)
        assert report["passed"] is True
        assert all(report["criteria"].values())


def test_flat_external_plan_is_completed_and_transformations_have_memory() -> None:
    flat = [CreativeEvent("bloom", 10, 2, .4, 0, 5)]
    completed = ensure_narrative_arc(flat, 40, 7)
    assert audit_narrative_arc(completed, 40)["passed"] is True
    before = narrative_state(0, completed)
    after = narrative_state(39, completed)
    assert before["metamorphosis"] == 0
    assert after["metamorphosis"] != 0
    assert after["scar"] > 0
