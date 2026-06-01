"""Tests for utils/music_bed.py — track pick + mood selection only.
The actual download + FFmpeg mix is exercised via integration tests
since they need network + ffmpeg respectively."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


def test_pick_track_is_deterministic(monkeypatch):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    story = {"slug": "abc-123", "category": "cats"}
    a = music_bed.pick_track(story)
    b = music_bed.pick_track(story)
    assert a is not None
    assert a == b


def test_pick_track_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", False)
    assert music_bed.pick_track({"slug": "x", "category": "cats"}) is None


def test_pick_track_falls_back_when_no_mood_match(monkeypatch):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    # Force an unknown mood by mocking _mood_for_story to return "xxx".
    monkeypatch.setattr(music_bed, "_mood_for_story", lambda s: "xxx")
    track = music_bed.pick_track({"slug": "x"})
    assert track is not None
    assert track in music_bed.PANEL


def test_add_music_bed_returns_original_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", False)
    fake_tts = tmp_path / "tts.mp3"
    fake_tts.write_bytes(b"x")
    out = music_bed.add_music_bed(fake_tts, {"slug": "x"}, tmp_path)
    assert out == fake_tts


def test_add_music_bed_returns_original_when_download_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    fake_tts = tmp_path / "tts.mp3"
    fake_tts.write_bytes(b"x")
    monkeypatch.setattr(music_bed, "download_track", lambda track: None)
    out = music_bed.add_music_bed(fake_tts, {"slug": "x"}, tmp_path)
    assert out == fake_tts


def test_add_music_bed_returns_mixed_when_pipeline_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    fake_tts = tmp_path / "tts.mp3"
    fake_tts.write_bytes(b"x")
    fake_music = tmp_path / "music.mp3"
    fake_music.write_bytes(b"x")
    monkeypatch.setattr(music_bed, "download_track", lambda track: fake_music)

    def fake_mix(tts_path, music_path, output_path, music_volume_db=-22.0):
        output_path.write_bytes(b"mixed")
        return True

    monkeypatch.setattr(music_bed, "mix_tts_with_music", fake_mix)
    out = music_bed.add_music_bed(fake_tts, {"slug": "x"}, tmp_path)
    assert out != fake_tts
    assert out.read_bytes() == b"mixed"


def test_download_track_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(music_bed, "MUSIC_CACHE_DIR", tmp_path / "cache")
    track = music_bed.MusicTrack(name="x", url="https://e.test/x.mp3", mood="upbeat")
    fake_resp = MagicMock(status_code=200)
    body = b"\x00" * 100_000   # 100 KB ≥ 50 KB min
    fake_resp.iter_content.return_value = [body]
    with patch("utils.music_bed.requests.get", return_value=fake_resp):
        a = music_bed.download_track(track)
        b = music_bed.download_track(track)
    assert a == b
    assert a is not None
    assert a.exists()


def test_download_track_rejects_too_small(monkeypatch, tmp_path):
    monkeypatch.setattr(music_bed, "MUSIC_CACHE_DIR", tmp_path / "cache")
    track = music_bed.MusicTrack(name="x", url="https://e.test/x.mp3", mood="upbeat")
    fake_resp = MagicMock(status_code=200)
    fake_resp.iter_content.return_value = [b"tiny"]
    with patch("utils.music_bed.requests.get", return_value=fake_resp):
        out = music_bed.download_track(track)
    assert out is None
