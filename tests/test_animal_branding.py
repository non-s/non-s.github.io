"""Tests for utils/animal_branding.py."""

from __future__ import annotations

from utils.animal_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title


def test_branded_title_uses_known_scene_hook():
    title = branded_title("cat")

    assert title.startswith(HOOK_BY_SCENE["cat"][0])
    assert title.endswith("-- Pata Jazz " + HOOK_BY_SCENE["cat"][1])


def test_branded_title_falls_back_for_unknown_scene():
    title = branded_title("iguana")

    assert "Fofura Total -- iguana" in title
    assert "Pata Jazz" in title


def test_branded_title_inserts_suffix_before_brand():
    title = branded_title("puppy", suffix="(Parte 2)")

    assert "(Parte 2) -- Pata Jazz" in title


def test_does_not_reuse_amber_hours_brand():
    for scene in HOOK_BY_SCENE:
        assert "amber hours" not in branded_title(scene).lower()


def test_playlist_bucket_matches_cat_signal():
    title = branded_title("cat")

    assert playlist_bucket_for_title(title) == "Gatinhos Fofos"


def test_playlist_bucket_defaults_when_no_signal_matches():
    assert playlist_bucket_for_title("Something Unrelated -- Pata Jazz") == "Fofura Total"
