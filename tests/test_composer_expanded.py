"""Tests for the expanded composer (new modes, song forms, genre compositions)."""

from __future__ import annotations

import pytest

from utils.genres.registry import GENRES, get_genre
from utils.liquid_wire_composer import (
    MODES,
    SONG_FORMS,
    build_composition_for_genre,
)

NEW_MODES = {
    "ionian",
    "phrygian",
    "locrian",
    "pentatonic_major",
    "pentatonic_minor",
    "blues",
    "harmonic_minor",
    "melodic_minor",
    "diminished",
    "whole_tone",
}

EXISTING_MODES = {"dorian", "aeolian", "lydian", "mixolydian"}


def test_existing_modes_preserved() -> None:
    assert EXISTING_MODES <= set(MODES)
    assert MODES["dorian"] == (0, 2, 3, 5, 7, 9, 10)
    assert MODES["aeolian"] == (0, 2, 3, 5, 7, 8, 10)
    assert MODES["lydian"] == (0, 2, 4, 6, 7, 9, 11)
    assert MODES["mixolydian"] == (0, 2, 4, 5, 7, 9, 10)


@pytest.mark.parametrize("mode_name", sorted(NEW_MODES))
def test_new_modes_present(mode_name: str) -> None:
    assert mode_name in MODES, f"{mode_name} missing from MODES"
    scale = MODES[mode_name]
    assert isinstance(scale, tuple)
    assert all(isinstance(i, int) for i in scale)
    assert scale[0] == 0


def test_ionian_intervals() -> None:
    assert MODES["ionian"] == (0, 2, 4, 5, 7, 9, 11)


def test_phrygian_intervals() -> None:
    assert MODES["phrygian"] == (0, 1, 3, 5, 7, 8, 10)


def test_blues_intervals() -> None:
    assert MODES["blues"] == (0, 3, 5, 6, 7, 10)


def test_harmonic_minor_intervals() -> None:
    assert MODES["harmonic_minor"] == (0, 2, 3, 5, 7, 8, 11)


def test_whole_tone_intervals() -> None:
    assert MODES["whole_tone"] == (0, 2, 4, 6, 8, 10)


def test_song_forms_present() -> None:
    expected_forms = {
        "four_section_arc",
        "verse_chorus_bridge",
        "head_solos_head",
        "intro_build_drop_outro",
        "verse_chorus",
        "loop_hook",
        "twelve_bar",
        "through_composed",
        "rondo",
        "sonata",
        "groove_based",
        "verse_dub_break",
    }
    assert expected_forms <= set(SONG_FORMS)


def test_song_form_four_section_arc_sections() -> None:
    assert SONG_FORMS["four_section_arc"] == ["emergence", "drift", "transformation", "release"]


def test_song_form_verse_chorus_bridge_sections() -> None:
    assert SONG_FORMS["verse_chorus_bridge"] == ["verse", "chorus", "verse", "chorus", "bridge", "chorus"]


def test_song_form_twelve_bar_present() -> None:
    assert "twelve_bar" in SONG_FORMS
    assert isinstance(SONG_FORMS["twelve_bar"], list)


@pytest.mark.parametrize("name", sorted(GENRES))
def test_build_composition_for_genre_works(name: str) -> None:
    preset = get_genre(name)
    plan = build_composition_for_genre(123, 30.0, preset)
    assert plan.sections, f"{name} produced no sections"
    assert plan.notes, f"{name} produced no notes"
    assert plan.tempo_map, f"{name} produced no tempo_map"
    assert plan.swing == preset.swing
    assert plan.arrangement, f"{name} produced no arrangement"


@pytest.mark.parametrize("name", sorted(GENRES))
def test_composition_uses_genre_modes(name: str) -> None:
    preset = get_genre(name)
    plan = build_composition_for_genre(7, 30.0, preset)
    # The chosen mode must come from one of the genre's allowed modes (by interval
    # match, since the mode name may differ if a custom tuple was used).
    assert plan.mode in MODES
    chosen_scale = MODES[plan.mode]
    assert chosen_scale in preset.modes, f"{name} chose mode {plan.mode} not in preset"


@pytest.mark.parametrize("name", sorted(GENRES))
def test_composition_uses_genre_progressions(name: str) -> None:
    preset = get_genre(name)
    plan = build_composition_for_genre(99, 30.0, preset)
    assert plan.progression in preset.progressions, f"{name} chose {plan.progression}"


@pytest.mark.parametrize("name", sorted(GENRES))
def test_song_forms_produce_correct_section_counts(name: str) -> None:
    preset = get_genre(name)
    plan = build_composition_for_genre(11, 40.0, preset)
    form_names = SONG_FORMS.get(preset.song_form, [preset.song_form])
    assert len(plan.sections) == len(form_names), f"{name} section count mismatch"
    assert [s.name for s in plan.sections] == form_names


@pytest.mark.parametrize("name", sorted(GENRES))
def test_sections_cover_full_duration(name: str) -> None:
    preset = get_genre(name)
    plan = build_composition_for_genre(55, 35.0, preset)
    assert plan.sections[0].start == 0.0
    assert abs(plan.sections[-1].end - 35.0) < 1e-9


@pytest.mark.parametrize("name", sorted(GENRES))
def test_arrangement_roles_match_instruments(name: str) -> None:
    preset = get_genre(name)
    plan = build_composition_for_genre(33, 30.0, preset)
    all_roles = set(preset.instruments.keys())
    for _section, roles in plan.arrangement:
        for role in roles:
            assert role in all_roles, f"{name} arrangement references unknown role {role}"


def test_composition_for_genre_is_deterministic() -> None:
    preset = get_genre("rock")
    a = build_composition_for_genre(42, 30.0, preset)
    b = build_composition_for_genre(42, 30.0, preset)
    assert a == b


def test_composition_for_genre_tempo_map_bounded() -> None:
    preset = get_genre("edm_house")
    plan = build_composition_for_genre(5, 30.0, preset)
    lo, hi = preset.tempo_range
    for _time, bpm in plan.tempo_map:
        # Tempo map may include gentle variation; stay within +/-15% of range.
        assert lo * 0.85 <= bpm <= hi * 1.15


def test_build_composition_for_genre_has_bass_voice() -> None:
    preset = get_genre("jazz")
    plan = build_composition_for_genre(1, 30.0, preset)
    voices = {note.voice for note in plan.notes}
    assert "bass" in voices
    assert "motif" in voices


def test_seeds_change_genre_compositions() -> None:
    preset = get_genre("lofi_ambient")
    identities = set()
    for seed in range(10, 30):
        plan = build_composition_for_genre(seed, 30.0, preset)
        identities.add((plan.mode, plan.progression, plan.tonic))
    assert len(identities) >= 3
