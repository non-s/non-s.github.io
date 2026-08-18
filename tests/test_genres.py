"""Tests for the genre preset library."""

from __future__ import annotations

import pytest

from utils.drums import PATTERNS
from utils.genres.registry import get_genre, list_genres

EXPECTED_GENRES = [
    "lofi_ambient",
    "rock",
    "edm_house",
    "synthwave",
    "jazz",
    "hip_hop",
    "classical",
    "ambient",
    "reggae_dub",
    "blues",
    "funk",
    "cinematic",
    # Extended genres (Engine 4.0 expansion).
    "techno",
    "trance",
    "dubstep",
    "dnb",
    "metal",
    "country",
    "folk",
    "pop",
    "soul",
    "disco",
    "salsa",
    "bossa_nova",
    "samba",
    "afrobeat",
    "flamenco",
    "gamelan",
    "vaporwave",
    "chiptune",
    "industrial",
    "shoegaze",
]


def test_list_genres_returns_all() -> None:
    names = list_genres()
    assert len(names) == 32
    assert set(names) == set(EXPECTED_GENRES)


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_each_genre_loadable(name: str) -> None:
    preset = get_genre(name)
    assert preset.name == name


def test_get_genre_returns_correct_preset() -> None:
    preset = get_genre("jazz")
    assert preset.name == "jazz"
    assert preset.swing == 0.66
    assert preset.song_form == "head_solos_head"
    assert "AcousticPiano" in preset.instruments.values()


def test_get_genre_unknown_raises() -> None:
    try:
        get_genre("does_not_exist")
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown genre")


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_has_valid_instruments(name: str) -> None:
    preset = get_genre(name)
    assert preset.instruments, f"{name} has no instruments"
    for role, instrument in preset.instruments.items():
        assert isinstance(role, str)
        assert isinstance(instrument, str)
        assert instrument, f"{name} role {role} has empty instrument name"


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_has_valid_modes(name: str) -> None:
    preset = get_genre(name)
    assert preset.modes, f"{name} has no modes"
    for mode in preset.modes:
        assert isinstance(mode, tuple)
        assert all(isinstance(interval, int) for interval in mode)
        assert mode[0] == 0, f"{name} mode {mode} does not start at 0"


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_has_valid_progressions(name: str) -> None:
    preset = get_genre(name)
    assert preset.progressions, f"{name} has no progressions"
    for prog in preset.progressions:
        assert isinstance(prog, tuple)
        assert all(isinstance(deg, int) and deg >= 0 for deg in prog), f"{name} prog {prog}"


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_drum_pattern_exists(name: str) -> None:
    preset = get_genre(name)
    assert preset.drum_pattern in PATTERNS, f"{name} drum_pattern {preset.drum_pattern!r} not in PATTERNS"


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_tempo_range_valid(name: str) -> None:
    preset = get_genre(name)
    lo, hi = preset.tempo_range
    assert 20.0 <= lo < hi <= 320.0, f"{name} tempo_range {preset.tempo_range}"


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_meter_options_valid(name: str) -> None:
    preset = get_genre(name)
    assert preset.meter_options, f"{name} has no meter options"
    for meter in preset.meter_options:
        assert 1 <= meter <= 12


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_chord_types_valid(name: str) -> None:
    preset = get_genre(name)
    assert preset.chord_types, f"{name} has no chord types"
    for chord in preset.chord_types:
        assert isinstance(chord, list)
        assert all(isinstance(interval, int) for interval in chord)


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_mix_config_has_buses(name: str) -> None:
    preset = get_genre(name)
    assert "buses" in preset.mix_config, f"{name} mix_config missing buses"
    assert "master" in preset.mix_config, f"{name} mix_config missing master"
    assert "reverb" in preset.mix_config, f"{name} mix_config missing reverb"


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_arrangement_has_sections(name: str) -> None:
    preset = get_genre(name)
    assert preset.arrangement, f"{name} has no arrangement"
    for section, roles in preset.arrangement.items():
        assert isinstance(section, str)
        assert isinstance(roles, list)
        assert all(isinstance(r, str) for r in roles)


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_effects_chain_present(name: str) -> None:
    preset = get_genre(name)
    assert isinstance(preset.effects_chain, list)
    assert preset.effects_chain, f"{name} has empty effects_chain"


@pytest.mark.parametrize("name", EXPECTED_GENRES)
def test_genre_swing_in_range(name: str) -> None:
    preset = get_genre(name)
    assert 0.0 <= preset.swing <= 0.66, f"{name} swing {preset.swing}"


def test_all_presets_are_frozen() -> None:
    for name in EXPECTED_GENRES:
        preset = get_genre(name)
        try:
            preset.name = "mutated"  # type: ignore[misc]
        except Exception:
            continue
        raise AssertionError(f"{name} preset is not frozen")
