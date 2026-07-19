"""Tests for utils/lofi_branding.py."""

from __future__ import annotations

from utils.lofi_branding import branded_title, playlist_bucket_for_title


def test_branded_title_uses_known_mood_hook():
    assert branded_title("rain window") == "Rainy Night Anime Lofi — Amber Hours \U0001f327️"


def test_branded_title_falls_back_for_unknown_mood():
    assert branded_title("Foggy Harbor") == "Foggy Harbor Anime Lofi — Amber Hours \U0001f319"


def test_branded_title_covers_the_2026_07_19_variety_expansion_moods():
    assert branded_title("autumn rain") == "Autumn Rain Anime Lofi — Amber Hours \U0001f327️"
    assert branded_title("rooftop night") == "Rooftop Rain Anime Lofi — Amber Hours \U0001f327️"
    assert branded_title("train window") == "Late Night Train Anime Lofi — Amber Hours \U0001f327️"
    assert branded_title("foggy morning") == "Foggy Morning Anime Lofi — Amber Hours \U0001f319"


def test_branded_title_inserts_suffix_before_the_brand_dash():
    assert branded_title("cat sleeping", suffix="(1 Hour)") == "Sleepy Cat Anime Lofi (1 Hour) — Amber Hours \U0001f43e"


def test_playlist_bucket_groups_rain_moods_together():
    assert playlist_bucket_for_title("Rainy Night Anime Lofi — Amber Hours \U0001f327️") == "Rainy Night Lofi"
    assert playlist_bucket_for_title("Rain on the Window Anime Lofi — Amber Hours \U0001f327️") == "Rainy Night Lofi"


def test_playlist_bucket_groups_different_cat_hooks_into_one_playlist():
    assert playlist_bucket_for_title("Sleepy Cat Anime Lofi — Amber Hours \U0001f43e") == "Cozy Cat Lofi"
    assert playlist_bucket_for_title("Cat Nap Anime Lofi — Amber Hours \U0001f43e") == "Cozy Cat Lofi"
    assert playlist_bucket_for_title("Purring Through the Night — Amber Hours \U0001f43e") == "Cozy Cat Lofi"


def test_playlist_bucket_falls_back_to_default_for_unmatched_title():
    assert playlist_bucket_for_title("Cozy Fireplace Anime Lofi — Amber Hours \U0001f319") == "Cozy Anime Lofi"
    assert playlist_bucket_for_title("") == "Cozy Anime Lofi"
