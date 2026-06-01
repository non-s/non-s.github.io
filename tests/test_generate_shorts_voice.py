"""Tests for the TTS voice picker in generate_shorts.py.

The picker has to be deterministic (same title → same voice) AND well-
distributed across the panel (so a year of stories doesn't all map to
one voice). It also has to stay stable across animal categories.
"""
from __future__ import annotations

import pytest

# generate_shorts.py pulls in Pillow + edge-tts at module import. Skip
# the suite cleanly when those aren't installed in the sandbox.
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


def test_pick_voice_returns_signature_voice_consistently():
    """Post-humanization pivot: the channel commits to ONE host voice.
    The picker is now deterministic to that single voice, so 200 calls
    return the same voice — that's the desired behaviour."""
    from generate_shorts import pick_voice, HOST_VOICE_PRIMARY
    seen = set()
    for i in range(200):
        seen.add(pick_voice(f"Story number {i}", "WORLD"))
    # ONE voice per language → seen contains exactly one element.
    assert seen == {HOST_VOICE_PRIMARY}


def test_pick_voice_ignores_category_after_humanization_pivot():
    """Post-pivot the host commits to a single signature voice — the
    category-bias logic that used to scatter voices is intentionally
    gone. These tests pin the new behaviour so we don't accidentally
    re-introduce voice scatter under "improving variety"."""
    from generate_shorts import pick_voice, HOST_VOICE_PRIMARY
    for cat in ("WAR", "ENTERTAINMENT", "AI", "POLITICS", "WORLD", "TECH", ""):
        assert pick_voice("Some headline", cat) == HOST_VOICE_PRIMARY


def test_pick_voice_handles_empty_seed():
    from generate_shorts import pick_voice, VOICE_PANEL
    # Empty / missing seed must still return a valid voice.
    assert pick_voice("", "") in VOICE_PANEL
    assert pick_voice("", "AI") in VOICE_PANEL


def test_pick_voice_pt_br_uses_locale_panel():
    """A pt-BR voice_tag should switch to the Portuguese panel."""
    from generate_shorts import pick_voice, VOICE_PANEL_BY_LOCALE
    for title in ("manchete 1", "manchete 2", "manchete 3", "manchete 4"):
        v = pick_voice(title, "WORLD", voice_tag="pt-BR")
        assert v in VOICE_PANEL_BY_LOCALE["pt-BR"]


def test_pick_voice_es_es_uses_locale_panel():
    from generate_shorts import pick_voice, VOICE_PANEL_BY_LOCALE
    v = pick_voice("noticia importante", "WORLD", voice_tag="es-ES")
    assert v in VOICE_PANEL_BY_LOCALE["es-ES"]


def test_pick_voice_unknown_locale_falls_back_to_english():
    """An unrecognised voice_tag falls through to the English panel."""
    from generate_shorts import pick_voice, VOICE_PANEL
    v = pick_voice("title", "WORLD", voice_tag="zz-ZZ")
    assert v in VOICE_PANEL


def test_pick_voice_pt_br_is_deterministic():
    from generate_shorts import pick_voice
    seed = "Mesma manchete brasileira"
    assert pick_voice(seed, "WORLD", voice_tag="pt-BR") == \
           pick_voice(seed, "WORLD", voice_tag="pt-BR")
