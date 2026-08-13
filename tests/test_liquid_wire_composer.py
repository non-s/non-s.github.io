from __future__ import annotations

from utils.liquid_wire_composer import build_composition
from utils.liquid_wire_timeline import build_timeline

MUSIC = {"key_shift": 2, "beat_seconds": 0.88, "meter": 4, "density": 0.8}


def test_composition_is_deterministic_and_sectional() -> None:
    timeline = build_timeline(123, 35.0, MUSIC)
    first = build_composition(123, 35.0, MUSIC, timeline)
    second = build_composition(123, 35.0, MUSIC, timeline)
    assert first == second
    assert [section.name for section in first.sections] == ["emergence", "drift", "transformation", "release"]
    assert first.sections[0].start == 0.0
    assert first.sections[-1].end == 35.0


def test_composed_notes_are_valid_and_include_event_gestures() -> None:
    timeline = build_timeline(888, 35.0, MUSIC)
    plan = build_composition(888, 35.0, MUSIC, timeline)
    assert plan.notes
    assert all(0.0 <= note.start < 35.0 for note in plan.notes)
    assert all(note.duration > 0.0 for note in plan.notes)
    assert {note.voice for note in plan.notes} >= {"motif", "gesture"}


def test_seeds_change_musical_identity() -> None:
    plans = []
    for seed in range(20, 30):
        timeline = build_timeline(seed, 35.0, MUSIC)
        plans.append(build_composition(seed, 35.0, MUSIC, timeline))
    assert len({(plan.mode, plan.progression) for plan in plans}) >= 5
