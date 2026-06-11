"""Tests for the TTS voice picker in generate_shorts.py."""
from __future__ import annotations

import pytest

pytest.importorskip("PIL")


def test_pick_voice_is_deterministic():
    from generate_shorts import pick_voice
    seed = "Octopus changes colour near reef"
    assert pick_voice(seed, "OCEAN") == pick_voice(seed, "OCEAN")


def test_pick_voice_returns_valid_panel_member():
    from generate_shorts import VOICE_PANEL, pick_voice
    for title in ["Octopus fact", "Owl fact", "Dog fact"]:
        for cat in ["OCEAN", "BIRDS", "DOGS", "WILDLIFE", "UNKNOWN", ""]:
            assert pick_voice(title, cat) in VOICE_PANEL


def test_pick_voice_uses_single_english_host_voice():
    from generate_shorts import HOST_VOICE_PRIMARY, pick_voice

    seen = {pick_voice(f"Animal fact number {i}", "WILDLIFE") for i in range(200)}
    assert seen == {HOST_VOICE_PRIMARY}


def test_pick_voice_stays_deterministic_across_categories():
    from generate_shorts import pick_voice
    for cat in ("CATS", "DOGS", "BIRDS", "OCEAN", "WILDLIFE", "FARM", ""):
        assert pick_voice("Some animal fact", cat) == pick_voice("Some animal fact", cat)


def test_pick_voice_handles_empty_seed():
    from generate_shorts import pick_voice, VOICE_PANEL
    assert pick_voice("", "") in VOICE_PANEL
    assert pick_voice("", "OCEAN") in VOICE_PANEL


def test_pick_voice_accepts_narrator_variant():
    from generate_shorts import HOST_VOICE_PRIMARY, pick_voice

    assert pick_voice("cat fact", "CATS", narrator_variant="jenny") == HOST_VOICE_PRIMARY
    assert pick_voice("snake fact", "REPTILES", narrator_variant="guy") == HOST_VOICE_PRIMARY
    assert pick_voice("owl fact", "BIRDS", narrator_variant="documentary") == HOST_VOICE_PRIMARY


def test_pick_voice_pt_br_uses_locale_panel():
    from generate_shorts import pick_voice, VOICE_PANEL_BY_LOCALE
    for title in ("polvo 1", "coruja 2", "gato 3", "golfinho 4"):
        v = pick_voice(title, "WILDLIFE", voice_tag="pt-BR")
        assert v in VOICE_PANEL_BY_LOCALE["pt-BR"]


def test_pick_voice_es_es_uses_locale_panel():
    from generate_shorts import pick_voice, VOICE_PANEL_BY_LOCALE
    v = pick_voice("dato curioso del pulpo", "OCEAN", voice_tag="es-ES")
    assert v in VOICE_PANEL_BY_LOCALE["es-ES"]


def test_pick_voice_unknown_locale_falls_back_to_english():
    from generate_shorts import pick_voice, VOICE_PANEL
    v = pick_voice("owl fact", "BIRDS", voice_tag="zz-ZZ")
    assert v in VOICE_PANEL


def test_pick_voice_pt_br_is_deterministic():
    from generate_shorts import pick_voice
    seed = "Mesmo fato sobre animais"
    assert pick_voice(seed, "WILDLIFE", voice_tag="pt-BR") == \
           pick_voice(seed, "WILDLIFE", voice_tag="pt-BR")
