"""Tests for utils/baby_noise_branding.py."""

from __future__ import annotations

from utils.baby_noise_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title


def test_branded_title_uses_known_scene_hook():
    title = branded_title("brown noise")

    assert title.startswith(HOOK_BY_SCENE["brown noise"][0])
    assert title.endswith("-- Amber Hours " + HOOK_BY_SCENE["brown noise"][1])


def test_branded_title_falls_back_for_unknown_scene():
    title = branded_title("gray noise")

    assert "Ruído Branco -- gray noise" in title
    assert "Amber Hours" in title


def test_branded_title_inserts_suffix_before_brand():
    title = branded_title("white noise", suffix="(3.0 Horas)")

    assert "(3.0 Horas) -- Amber Hours" in title


def test_reuses_amber_hours_brand_unlike_pata_jazz():
    """Deliberately the opposite assertion from test_animal_branding.py's
    identical test -- this pillar's whole point is sharing the rain
    pillar's brand, since the promise is the same."""
    for scene in HOOK_BY_SCENE:
        assert "amber hours" in branded_title(scene).lower()


def test_playlist_bucket_matches_brown_signal():
    title = branded_title("brown noise")

    assert playlist_bucket_for_title(title) == "Ruído Marrom"


def test_playlist_bucket_matches_baby_signal():
    title = branded_title("baby sleep")

    assert playlist_bucket_for_title(title) == "Ruído para o Bebê Dormir"


def test_playlist_bucket_defaults_when_no_signal_matches():
    assert playlist_bucket_for_title("Something Unrelated -- Amber Hours") == "Ruído para Dormir e Focar"
