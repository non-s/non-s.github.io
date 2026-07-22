"""Tests for generate_baby_noise_ambience.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import generate_baby_noise_ambience as noise_ambience


def test_pick_scene_returns_a_known_hook_scene():
    from utils.baby_noise_branding import HOOK_BY_SCENE

    scene = noise_ambience._pick_scene()
    assert scene.lower() in HOOK_BY_SCENE


def test_pick_color_returns_a_known_noise_color():
    from utils.noise_audio import NOISE_COLORS

    assert noise_ambience._pick_color() in NOISE_COLORS


def test_build_metadata_uses_ai_copy_when_available(tmp_path, monkeypatch):
    ai_result = {
        "title": "Ruído Marrom para o Bebê Dormir a Noite Toda -- Amber Hours",
        "description": "Um som grave e constante para acalmar.",
        "hashtags": ["ruidomarrom", "bebe"],
    }
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: ai_result)
    video_path = tmp_path / "noise-ambience-ai.mp4"

    meta = noise_ambience._build_metadata("brown noise", "brown", 3600.0, video_path, slug="s-ai", broll_meta={})

    assert meta["title"] == ai_result["title"]
    assert "Um som grave e constante para acalmar." in meta["description"]
    assert "amber hours" in meta["tags"]
    assert "ruidomarrom" in meta["tags"]


def test_build_metadata_always_appends_the_synthesized_disclosure(tmp_path, monkeypatch):
    ai_result = {"title": "T -- Amber Hours", "description": "Sem menção a síntese aqui.", "hashtags": ["ruido"]}
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: ai_result)
    video_path = tmp_path / "noise-ambience-disclosure.mp4"

    meta = noise_ambience._build_metadata("white noise", "white", 3600.0, video_path, slug="s-disc", broll_meta={})

    assert "sintetizado por computador" in meta["description"]


def test_build_metadata_falls_back_to_template_when_ai_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-ambience-fallback.mp4"

    meta = noise_ambience._build_metadata("focus", "pink", 3600.0, video_path, slug="s-fb", broll_meta={})

    assert meta["title"] == noise_ambience.branded_title("focus", suffix="(1.0 Horas)")


def test_build_metadata_uses_hours_label_for_long_videos(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-ambience-1.mp4"

    meta = noise_ambience._build_metadata(
        "brown noise", "brown", 3.5 * 3600, video_path, slug="ambience-1700000000-1234", broll_meta={}
    )

    assert "(3.5 Horas)" in meta["title"]
    assert meta["category"] == "baby_noise_ambience"
    assert meta["is_short"] is False


def test_build_metadata_uses_minutes_label_under_an_hour(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-ambience-2.mp4"

    meta = noise_ambience._build_metadata(
        "focus", "pink", 45 * 60, video_path, slug="ambience-1700000000-5678", broll_meta={}
    )

    assert "(45 Min)" in meta["title"]


def test_build_metadata_disclosure_mentions_noise_not_rain(tmp_path, monkeypatch):
    """Regression: this pillar's disclosure must not accidentally reuse
    the rain pillar's "chuva e trovão" wording."""
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-ambience-3.mp4"

    meta = noise_ambience._build_metadata("white noise", "white", 3600.0, video_path, slug="s-3", broll_meta={})

    assert "ruído" in meta["description"].lower()
    assert "chuva" not in meta["description"].lower()


def test_build_metadata_tags_lead_with_the_scene_then_default_tags(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-ambience-4.mp4"

    meta = noise_ambience._build_metadata("brown noise", "brown", 3600.0, video_path, slug="s-4", broll_meta={})

    assert meta["tags"][0] == "brown noise"
    assert "ruído marrom" in meta["tags"]


def test_build_metadata_publish_slot_uses_the_noise_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-ambience-5.mp4"

    meta = noise_ambience._build_metadata("focus", "pink", 3600.0, video_path, slug="s-5", broll_meta={})

    assert meta["publish_slot"].startswith("noise-")
    assert meta["publish_slot_key"].startswith("noise-")


def test_build_metadata_carries_real_broll_source_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "generate_baby_noise_copy", lambda **kwargs: None)
    broll_meta = {
        "source": "pixabay",
        "pixabay_video_id": "555",
        "license": "Pixabay Content License (free for commercial use, no attribution required)",
        "license_evidence": "https://pixabay.com/videos/id-555",
    }
    video_path = tmp_path / "noise-ambience-6.mp4"

    meta = noise_ambience._build_metadata("focus", "pink", 3600.0, video_path, slug="s-6", broll_meta=broll_meta)

    assert meta["source"] == "pixabay"
    assert meta["source_clip_id"] == "555"
    assert meta["source_url"] == "https://pixabay.com/videos/id-555"
    assert meta["source_license"] == broll_meta["license"]


def test_prepare_seamless_loop_clip_returns_raw_clip_for_short_source(tmp_path, monkeypatch):
    import utils.ffmpeg_helpers as fh

    monkeypatch.setattr(fh, "media_duration_s", lambda path: 0.0)
    clip_path = tmp_path / "pixabay_1.mp4"

    out = noise_ambience._prepare_seamless_loop_clip(clip_path)

    assert out == clip_path


def test_prepare_seamless_loop_clip_bakes_a_crossfade_for_a_longer_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "TEMP_DIR", tmp_path)
    import utils.ffmpeg_helpers as fh

    monkeypatch.setattr(fh, "media_duration_s", lambda path: 12.0)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(fh.subprocess, "run", fake_run)
    clip_path = tmp_path / "pixabay_1.mp4"

    out = noise_ambience._prepare_seamless_loop_clip(clip_path)

    assert out == tmp_path / "seamless_pixabay_1.mp4"
    assert "xfade" in calls[-1][calls[-1].index("-filter_complex") + 1]


def test_bake_filtered_segment_builds_expected_ffmpeg_command(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "TEMP_DIR", tmp_path)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(noise_ambience.subprocess, "run", fake_run)

    out = noise_ambience._bake_filtered_segment(tmp_path / "pixabay_1.mp4")

    assert out is not None
    assert out.exists()
    cmd = calls[-1]
    assert "-vf" in cmd
    assert "-an" in cmd


def test_bake_filtered_segment_returns_none_on_ffmpeg_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "TEMP_DIR", tmp_path)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(noise_ambience.subprocess, "run", fake_run)

    assert noise_ambience._bake_filtered_segment(tmp_path / "clip.mp4") is None


def test_prepare_noise_bed_writes_a_wav_file(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(noise_ambience, "NOISE_BED_SECONDS", 1.0)

    path = noise_ambience._prepare_noise_bed(seed=1, color="brown")

    assert path.exists()
    assert path.stat().st_size > 0


def test_compose_ambience_builds_pure_noise_ffmpeg_command(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(noise_ambience.subprocess, "run", fake_run)

    segment = tmp_path / "segment.mp4"
    noise = tmp_path / "noise.wav"
    out_path = tmp_path / "out.mp4"

    assert noise_ambience._compose_ambience(segment, noise, out_path, 120.0) is True

    cmd = calls[0]
    assert "-c:v" in cmd and "copy" in cmd
    assert cmd[cmd.index("-t") + 1] == "120.000"


def test_compose_ambience_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(noise_ambience.subprocess, "run", fake_run)

    ok = noise_ambience._compose_ambience(tmp_path / "s.mp4", tmp_path / "n.wav", tmp_path / "out.mp4", 60.0)
    assert ok is False


def test_main_returns_error_when_broll_pool_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_ambience, "NOISE_BROLL_DIR", tmp_path)
    monkeypatch.setattr(noise_ambience, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(noise_ambience, "TEMP_DIR", tmp_path / "_videos" / "temp")

    assert noise_ambience.main() == 1
