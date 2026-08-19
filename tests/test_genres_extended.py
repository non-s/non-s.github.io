"""Tests for the 20 new genres and build_composition_extended.

Validates each preset's metadata, drum pattern membership, modes and tempo
range, then exercises build_composition_extended for a representative subset.
"""

from __future__ import annotations

import pytest

from utils.composer_extended import build_composition_extended
from utils.drums import PATTERNS
from utils.genres.registry import GENRES, get_genre

NEW_GENRES = [
    "techno", "trance", "dubstep", "dnb", "metal", "country", "folk", "pop",
    "soul", "disco", "salsa", "bossa_nova", "samba", "afrobeat", "flamenco",
    "gamelan", "vaporwave", "chiptune", "industrial", "shoegaze",
]


@pytest.mark.parametrize("name", NEW_GENRES)
def test_genre_registered(name):
    preset = get_genre(name)
    assert preset.name == name
    assert isinstance(preset.instruments, dict) and len(preset.instruments) > 0
    assert preset.drum_pattern in PATTERNS, f"{name}: {preset.drum_pattern} not in PATTERNS"
    assert isinstance(preset.modes, list) and len(preset.modes) > 0
    assert isinstance(preset.tempo_range, tuple) and len(preset.tempo_range) == 2
    assert preset.tempo_range[0] <= preset.tempo_range[1]
    assert preset.tempo_range[0] > 0.0


@pytest.mark.parametrize("name", NEW_GENRES)
def test_genre_composition(name):
    preset = get_genre(name)
    plan = build_composition_extended(seed=123, duration=10.0, genre_preset=preset)
    assert len(plan.notes) > 0
    voices = {n.voice for n in plan.notes}
    assert len(voices) > 0
    assert plan.tonic > 0
    assert len(plan.sections) > 0


def test_new_genres_count_is_20():
    assert len(NEW_GENRES) == 20


def test_all_new_genres_present_in_registry():
    missing = [g for g in NEW_GENRES if g not in GENRES]
    assert missing == []


@pytest.mark.parametrize("name", ["techno", "chiptune", "vaporwave"])
def test_composition_determinism(name):
    preset = get_genre(name)
    a = build_composition_extended(seed=7, duration=5.0, genre_preset=preset)
    b = build_composition_extended(seed=7, duration=5.0, genre_preset=preset)
    assert a.to_dict() == b.to_dict()
