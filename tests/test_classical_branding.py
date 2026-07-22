"""Tests for utils/classical_branding.py."""

from __future__ import annotations

from utils.classical_branding import HOOK_BY_MOOD, branded_title, playlist_bucket_for_title


def test_branded_title_uses_known_mood_hook():
    title = branded_title("sleep")

    assert title.startswith(HOOK_BY_MOOD["sleep"][0])
    assert title.endswith("-- Amber Hours Classical " + HOOK_BY_MOOD["sleep"][1])


def test_branded_title_falls_back_for_unknown_mood():
    title = branded_title("nocturne")

    assert "Classical Piano -- nocturne" in title
    assert "Amber Hours Classical" in title


def test_branded_title_inserts_suffix_before_brand():
    title = branded_title("deep focus", suffix="(45 Min)")

    assert "(45 Min) -- Amber Hours Classical" in title


def test_branded_title_is_english_not_portuguese():
    """This is the one pillar that must never emit pt-BR words the way
    every other pillar's branding module does."""
    for mood in HOOK_BY_MOOD:
        title = branded_title(mood)
        assert "som de" not in title.lower()
        assert "chuva" not in title.lower()


def test_playlist_bucket_matches_focus_signal():
    title = branded_title("deep focus")

    assert playlist_bucket_for_title(title) == "Classical Music for Focus"


def test_playlist_bucket_defaults_when_no_signal_matches():
    assert playlist_bucket_for_title("Something Unrelated -- Amber Hours Classical") == "Classical Ambience"
