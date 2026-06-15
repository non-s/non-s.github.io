"""Tests for the disabled background music hook."""

from __future__ import annotations

from utils import music_bed


def test_mood_breaking_picks_tense():
    story = {"slug": "x", "breaking": True}
    assert music_bed._mood_for_story(story) == "tense"


def test_mood_negative_picks_tense():
    story = {"slug": "x", "sentiment": "negative"}
    assert music_bed._mood_for_story(story) == "tense"


def test_mood_ocean_picks_reflective():
    story = {"slug": "x", "category": "ocean"}
    assert music_bed._mood_for_story(story) == "reflective"


def test_mood_default_upbeat():
    story = {"slug": "x", "category": "cats"}
    assert music_bed._mood_for_story(story) == "upbeat"


def test_music_bed_has_no_external_provider_flags():
    assert not hasattr(music_bed, "download_track")
    assert not hasattr(music_bed, "pick_track")


def test_add_music_bed_returns_original_file(tmp_path):
    fake_tts = tmp_path / "tts.mp3"
    fake_tts.write_bytes(b"x")
    story = {"slug": "x"}

    out = music_bed.add_music_bed(fake_tts, story, tmp_path)

    assert out == fake_tts
    assert story["music_bed_track"] == {}
