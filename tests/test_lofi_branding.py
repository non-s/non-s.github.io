"""Tests for utils/lofi_branding.py."""

from __future__ import annotations

from utils.lofi_branding import (
    HOOK_BY_MOOD,
    bgm_speeds_for_mood,
    branded_title,
    mood_energy,
    playlist_bucket_for_title,
)


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


def test_mood_energy_is_lively_only_for_the_two_visually_busy_moods():
    assert mood_energy("night city") == "lively"
    assert mood_energy("Cafe Jazz") == "lively"
    assert mood_energy("rain window") == "calm"
    assert mood_energy("cat sleeping") == "calm"
    assert mood_energy("some unknown mood") == "calm"


def test_bgm_speeds_for_mood_excludes_high_energy_tracks_from_calm_moods():
    assert bgm_speeds_for_mood("rain window") == {"verylow", "low", "medium"}
    assert bgm_speeds_for_mood("night city") == {"medium", "high"}


def test_no_two_moods_share_the_same_hook_text():
    """Regression guard for the 2026-07-21 incident: "lofi girl" and "study
    desk" both hooked to "Late Night Study Anime Lofi", so the two moods
    were guaranteed to collide on title eventually -- which tripped
    upload_youtube.py's collision dedup and published "... | Lofi girl" (a
    competitor's brand name) as a visible tag suffix. Every mood's hook
    must stay unique so _pick_mood() can never reproduce that."""
    hooks = [hook for hook, _emoji in HOOK_BY_MOOD.values()]
    assert len(hooks) == len(set(hooks))


def test_no_mood_or_hook_names_a_third_party_channel_or_brand():
    """ "lofi girl" specifically -- and any future mood -- must not put a
    well-known competitor's name in a public title/tag/description."""
    blocked_terms = ("lofi girl", "chilledcow", "chillhop")
    for mood, (hook, _emoji) in HOOK_BY_MOOD.items():
        haystack = f"{mood} {hook}".lower()
        for term in blocked_terms:
            assert term not in haystack, f"{mood!r} references {term!r}"
