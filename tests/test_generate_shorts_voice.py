"""Tests for the TTS voice picker in generate_shorts.py.

The picker has to be deterministic (same title → same voice) AND well-
distributed across the panel (so a year of stories doesn't all map to
one voice). It also has to bias by category — high-stakes news to
authoritative voices, lifestyle to lighter ones.
"""
from __future__ import annotations

import pytest

# generate_shorts.py pulls in Pillow + edge-tts at module import. Skip
# the suite cleanly when those aren't installed in the sandbox.
pytest.importorskip("PIL")


def test_pick_voice_is_deterministic():
    from generate_shorts import pick_voice
    seed = "Fed cuts interest rates — markets rally"
    assert pick_voice(seed, "BUSINESS") == pick_voice(seed, "BUSINESS")


def test_pick_voice_returns_valid_panel_member():
    from generate_shorts import VOICE_PANEL, pick_voice
    for title in ["Tech news today", "War in Ukraine", "Movie release"]:
        for cat in ["AI", "WAR", "ENTERTAINMENT", "TECH", "UNKNOWN", ""]:
            assert pick_voice(title, cat) in VOICE_PANEL


def test_pick_voice_distributes_across_panel():
    from generate_shorts import pick_voice
    seen = set()
    for i in range(200):
        seen.add(pick_voice(f"Story number {i}", "WORLD"))
    # Should hit at least 2 distinct voices for WORLD category (panel of British + Guy).
    assert len(seen) >= 2


def test_pick_voice_war_uses_authoritative_subset():
    """High-stakes categories should bias toward British / male voices."""
    from generate_shorts import pick_voice
    seen = set()
    for i in range(50):
        v = pick_voice(f"Headline {i}", "WAR")
        seen.add(v)
        # Should NEVER pick a lifestyle voice for war coverage.
        assert "Natasha" not in v
        assert "Jenny" not in v
    assert len(seen) >= 1


def test_pick_voice_entertainment_uses_lifestyle_subset():
    from generate_shorts import pick_voice
    seen = set()
    for i in range(50):
        v = pick_voice(f"Headline {i}", "ENTERTAINMENT")
        seen.add(v)
    # All picks must be from the lifestyle pool (Jenny / Natasha).
    assert all(("Jenny" in v or "Natasha" in v) for v in seen)


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
