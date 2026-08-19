"""Tests for the extended composer (build_composition_extended).

Verifies voice coverage, genre-specific voices (walking_bass for jazz,
arpeggio for edm_house) and determinism.
"""

from __future__ import annotations

import pytest

from utils.composer_extended import build_composition_extended
from utils.genres.registry import get_genre

GENRES_TO_TEST = ["jazz", "edm_house", "ambient"]


@pytest.mark.parametrize("name", GENRES_TO_TEST)
def test_composition_has_notes_and_voices(name):
    preset = get_genre(name)
    plan = build_composition_extended(seed=123, duration=10.0, genre_preset=preset)
    assert len(plan.notes) > 0
    voices = {n.voice for n in plan.notes}
    assert "motif" in voices
    assert "bass" in voices or "walking_bass" in voices
    assert "pad" in voices


def test_jazz_has_walking_bass():
    preset = get_genre("jazz")
    plan = build_composition_extended(seed=42, duration=12.0, genre_preset=preset)
    voices = {n.voice for n in plan.notes}
    assert "walking_bass" in voices


def test_edm_house_has_arpeggio():
    preset = get_genre("edm_house")
    plan = build_composition_extended(seed=7, duration=12.0, genre_preset=preset)
    voices = {n.voice for n in plan.notes}
    assert "arpeggio" in voices


@pytest.mark.parametrize("name", GENRES_TO_TEST)
def test_notes_within_duration(name):
    preset = get_genre(name)
    duration = 10.0
    plan = build_composition_extended(seed=5, duration=duration, genre_preset=preset)
    for note in plan.notes:
        assert note.start >= 0.0
        assert note.start < duration


@pytest.mark.parametrize("name", GENRES_TO_TEST)
def test_composition_determinism(name):
    preset = get_genre(name)
    a = build_composition_extended(seed=99, duration=10.0, genre_preset=preset)
    b = build_composition_extended(seed=99, duration=10.0, genre_preset=preset)
    assert a.to_dict() == b.to_dict()
