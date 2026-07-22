"""Tests for generate_storm_ambience.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import generate_storm_ambience as storm


def test_pick_scene_returns_a_known_hook_scene():
    from utils.storm_branding import HOOK_BY_SCENE

    scene = storm._pick_scene()
    assert scene.lower() in HOOK_BY_SCENE


def test_build_metadata_uses_ai_copy_when_available(tmp_path, monkeypatch):
    ai_result = {
        "title": "Deep Sleep Rain & Thunder -- Amber Hours",
        "description": "A calm rain session for deep sleep.",
        "hashtags": ["rainsounds", "sleep"],
    }
    monkeypatch.setattr(storm, "generate_video_copy", lambda **kwargs: ai_result)
    video_path = tmp_path / "storm-ambience-ai.mp4"

    meta = storm._build_metadata("deep sleep", 3600.0, video_path, slug="s-ai", music_meta=None, broll_meta={})

    assert meta["title"] == ai_result["title"]
    assert "A calm rain session for deep sleep." in meta["description"]
    assert "amber hours" in meta["tags"]
    assert "rainsounds" in meta["tags"]


def test_build_metadata_always_appends_the_synthesized_disclosure(tmp_path, monkeypatch):
    """Regardless of whether the AI or the template wrote the description,
    the "not a recording" disclosure must always be present -- it's a
    factual/no-fake-claims guarantee, not something left to the AI's
    discretion."""
    ai_result = {
        "title": "T -- Amber Hours",
        "description": "Some AI text with no mention of synthesis.",
        "hashtags": ["rain"],
    }
    monkeypatch.setattr(storm, "generate_video_copy", lambda **kwargs: ai_result)
    video_path = tmp_path / "storm-ambience-disclosure.mp4"

    meta = storm._build_metadata("focus", 3600.0, video_path, slug="s-disc", music_meta=None, broll_meta={})

    assert "sintetizados por computador" in meta["description"]


def test_build_metadata_falls_back_to_template_when_ai_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(storm, "generate_video_copy", lambda **kwargs: None)
    video_path = tmp_path / "storm-ambience-fallback.mp4"

    meta = storm._build_metadata("focus", 3600.0, video_path, slug="s-fb", music_meta=None, broll_meta={})

    assert meta["title"] == storm.branded_title("focus", suffix="(1.0 Horas)")


def test_build_metadata_uses_hours_label_for_long_videos(tmp_path):
    video_path = tmp_path / "storm-ambience-1.mp4"

    meta = storm._build_metadata(
        "deep sleep", 3.5 * 3600, video_path, slug="ambience-1700000000-1234", music_meta=None, broll_meta={}
    )

    assert "(3.5 Horas)" in meta["title"]
    assert meta["category"] == "storm_ambience"
    assert meta["is_short"] is False


def test_build_metadata_uses_minutes_label_under_an_hour(tmp_path):
    video_path = tmp_path / "storm-ambience-2.mp4"

    meta = storm._build_metadata(
        "focus", 45 * 60, video_path, slug="ambience-1700000000-5678", music_meta=None, broll_meta={}
    )

    assert "(45 Min)" in meta["title"]


def test_build_metadata_never_rounds_a_short_duration_down_to_zero_minutes(tmp_path):
    """Regression: round(30 / 60) is 0 (Python's round-half-to-even), which
    produced the nonsensical "(0 Min)" title for anything under 90s."""
    video_path = tmp_path / "storm-ambience-2b.mp4"

    meta = storm._build_metadata("focus", 30.0, video_path, slug="s-0", music_meta=None, broll_meta={})

    assert "(0 Min)" not in meta["title"]
    assert "(1 Min)" in meta["title"]


def test_build_metadata_credits_music_only_when_a_track_was_used(tmp_path):
    video_path = tmp_path / "storm-ambience-3.mp4"
    music_meta = {"track_name": "Soft Rain Piano", "artist_name": "Someone", "license_ccurl": "http://example.com"}

    with_music = storm._build_metadata("focus", 3600.0, video_path, slug="s-1", music_meta=music_meta, broll_meta={})
    without_music = storm._build_metadata("focus", 3600.0, video_path, slug="s-2", music_meta=None, broll_meta={})

    assert "Soft Rain Piano" in with_music["description"]
    assert "Soft Rain Piano" not in without_music["description"]


def test_build_metadata_tags_lead_with_the_scene_then_default_tags(tmp_path):
    video_path = tmp_path / "storm-ambience-4.mp4"

    meta = storm._build_metadata("deep sleep", 3600.0, video_path, slug="s-3", music_meta=None, broll_meta={})

    assert meta["tags"][0] == "deep sleep"
    assert "chuva para dormir" in meta["tags"]


def test_build_metadata_publish_slot_uses_the_storm_prefix(tmp_path):
    video_path = tmp_path / "storm-ambience-5.mp4"

    meta = storm._build_metadata("focus", 3600.0, video_path, slug="s-4", music_meta=None, broll_meta={})

    assert meta["publish_slot"].startswith("storm-")
    assert meta["publish_slot_key"].startswith("storm-")


def test_build_metadata_carries_real_broll_source_fields(tmp_path):
    video_path = tmp_path / "storm-ambience-6.mp4"
    broll_meta = {
        "source": "pixabay",
        "pixabay_video_id": "555",
        "license": "Pixabay Content License (free for commercial use, no attribution required)",
        "license_evidence": "https://pixabay.com/videos/id-555",
    }

    meta = storm._build_metadata("focus", 3600.0, video_path, slug="s-5", music_meta=None, broll_meta=broll_meta)

    assert meta["source"] == "pixabay"
    assert meta["source_clip_id"] == "555"
    assert meta["source_url"] == "https://pixabay.com/videos/id-555"
    assert meta["source_license"] == broll_meta["license"]


def test_prepare_seamless_loop_clip_returns_raw_clip_for_short_source(tmp_path, monkeypatch):
    monkeypatch.setattr(storm, "_media_duration_s", lambda path: 0.0)
    clip_path = tmp_path / "pixabay_1.mp4"

    out = storm._prepare_seamless_loop_clip(clip_path)

    assert out == clip_path


def test_prepare_seamless_loop_clip_bakes_a_crossfade_for_a_longer_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(storm, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(storm, "_media_duration_s", lambda path: 12.0)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(storm.subprocess, "run", fake_run)
    clip_path = tmp_path / "pixabay_1.mp4"

    out = storm._prepare_seamless_loop_clip(clip_path)

    assert out == tmp_path / "seamless_pixabay_1.mp4"
    assert "xfade" in calls[-1][calls[-1].index("-filter_complex") + 1]


def test_bake_filtered_segment_builds_expected_ffmpeg_command(tmp_path, monkeypatch):
    monkeypatch.setattr(storm, "TEMP_DIR", tmp_path)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(storm.subprocess, "run", fake_run)

    out = storm._bake_filtered_segment(tmp_path / "pinned_storm_clip.mp4")

    assert out is not None
    assert out.exists()
    cmd = calls[-1]
    assert "-vf" in cmd
    assert "-an" in cmd


def test_bake_filtered_segment_returns_none_on_ffmpeg_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(storm, "TEMP_DIR", tmp_path)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(storm.subprocess, "run", fake_run)

    assert storm._bake_filtered_segment(tmp_path / "clip.mp4") is None


def test_prepare_rain_bed_writes_a_wav_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storm, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(storm, "RAIN_BED_SECONDS", 1.0)

    path = storm._prepare_rain_bed(seed=1)

    assert path.exists()
    assert path.stat().st_size > 0


def test_compose_storm_mixes_music_only_when_a_track_is_given(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(storm.subprocess, "run", fake_run)

    segment = tmp_path / "segment.mp4"
    rain = tmp_path / "rain.wav"
    music = tmp_path / "music.mp3"
    out_with_music = tmp_path / "out_with_music.mp4"
    out_without_music = tmp_path / "out_without_music.mp4"

    assert storm._compose_storm(segment, rain, music, out_with_music, 120.0) is True
    assert storm._compose_storm(segment, rain, None, out_without_music, 120.0) is True

    with_music_cmd = calls[0]
    without_music_cmd = calls[1]
    assert str(music) in with_music_cmd
    assert "amix" in with_music_cmd[with_music_cmd.index("-filter_complex") + 1]
    assert str(music) not in without_music_cmd
    assert "amix" not in without_music_cmd[without_music_cmd.index("-filter_complex") + 1]


def test_compose_storm_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(storm.subprocess, "run", fake_run)

    ok = storm._compose_storm(tmp_path / "s.mp4", tmp_path / "r.wav", None, tmp_path / "out.mp4", 60.0)
    assert ok is False
