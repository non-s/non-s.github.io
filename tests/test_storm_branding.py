"""Tests for utils/storm_branding.py."""

from __future__ import annotations

from utils.storm_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title


def test_branded_title_uses_known_scene_hook():
    assert branded_title("deep sleep") == "Heavy Rain & Distant Thunder for Deep Sleep -- Amber Hours \U0001f634"


def test_branded_title_falls_back_for_unknown_scene():
    assert branded_title("Foggy Harbor") == "Foggy Harbor Rain Sounds -- Amber Hours \U0001f327️"


def test_branded_title_inserts_suffix_before_the_brand_dash():
    assert (
        branded_title("focus", suffix="(3 Hours)")
        == "Rain Sounds for Studying & Deep Focus (3 Hours) -- Amber Hours \U0001f4d6"
    )


def test_playlist_bucket_groups_thunder_scenes_together():
    assert playlist_bucket_for_title("Distant Thunder & Rain for Insomnia Relief") == "Thunderstorm Sounds"
    assert playlist_bucket_for_title("Heavy Rain & Distant Thunder for Deep Sleep") == "Thunderstorm Sounds"


def test_playlist_bucket_falls_back_to_default_for_unmatched_title():
    assert playlist_bucket_for_title("Rain on a Cabin Roof") == "Rain & Storm Ambience"
    assert playlist_bucket_for_title("") == "Rain & Storm Ambience"


def test_no_two_scenes_share_the_same_hook_text():
    """Same regression guard as utils.lofi_branding's -- two scenes with
    byte-identical hook text would guarantee a title collision the first
    time both got picked."""
    hooks = [hook for hook, _emoji in HOOK_BY_SCENE.values()]
    assert len(hooks) == len(set(hooks))


def test_no_scene_or_hook_mentions_anime_or_lofi():
    """This pillar exists specifically to stop competing on the
    "anime lofi" search term this channel's other format already leans
    into -- its own vocabulary must not reintroduce it."""
    blocked_terms = ("anime", "lofi", "lofi girl")
    for scene, (hook, _emoji) in HOOK_BY_SCENE.items():
        haystack = f"{scene} {hook}".lower()
        for term in blocked_terms:
            assert term not in haystack, f"{scene!r} references {term!r}"
