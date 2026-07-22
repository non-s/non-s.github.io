"""Tests for generate_baby_noise_short.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import generate_baby_noise_short as noise_short


def test_pick_scene_returns_a_known_hook_scene():
    from utils.baby_noise_branding import HOOK_BY_SCENE

    scene = noise_short._pick_scene()
    assert scene.lower() in HOOK_BY_SCENE


def test_pick_color_returns_a_known_noise_color():
    from utils.noise_audio import NOISE_COLORS

    assert noise_short._pick_color() in NOISE_COLORS


def test_build_metadata_uses_template_title_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_short, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-noiseshort-1.mp4"

    meta = noise_short._build_metadata("white noise", "white", 45.0, video_path, slug="s-1", broll_meta={})

    assert meta["title"] == noise_short.branded_title("white noise")
    assert meta["category"] == "baby_noise_ambience"


def test_build_metadata_includes_shorts_hashtag(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_short, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-noiseshort-2.mp4"

    meta = noise_short._build_metadata("brown noise", "brown", 45.0, video_path, slug="s-2", broll_meta={})

    assert "#Shorts" in meta["description"]


def test_build_metadata_disclosure_names_the_actual_color(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_short, "generate_baby_noise_copy", lambda **kwargs: None)
    video_path = tmp_path / "noise-noiseshort-3.mp4"

    meta = noise_short._build_metadata("brown noise", "brown", 45.0, video_path, slug="s-3", broll_meta={})

    assert "marrom" in meta["description"]
    assert "sintetizado por computador" in meta["description"]


def test_build_metadata_carries_real_broll_source_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_short, "generate_baby_noise_copy", lambda **kwargs: None)
    broll_meta = {
        "source": "pixabay",
        "pixabay_video_id": "555",
        "license": "Pixabay Content License (free for commercial use, no attribution required)",
        "license_evidence": "https://pixabay.com/videos/id-555",
    }
    video_path = tmp_path / "noise-noiseshort-4.mp4"

    meta = noise_short._build_metadata("white noise", "white", 45.0, video_path, slug="s-4", broll_meta=broll_meta)

    assert meta["source"] == "pixabay"
    assert meta["source_clip_id"] == "555"
    assert meta["source_url"] == "https://pixabay.com/videos/id-555"
    assert meta["source_license"] == broll_meta["license"]


def test_build_metadata_uses_ai_copy_when_available(tmp_path, monkeypatch):
    ai_result = {
        "title": "Ruído Branco para o Bebê -- Amber Hours",
        "description": "Som calmo e constante.",
        "hashtags": ["ruidobranco", "bebe"],
    }
    monkeypatch.setattr(noise_short, "generate_baby_noise_copy", lambda **kwargs: ai_result)
    video_path = tmp_path / "noise-noiseshort-5.mp4"

    meta = noise_short._build_metadata("white noise", "white", 45.0, video_path, slug="s-5", broll_meta={})

    assert meta["title"] == ai_result["title"]
    assert "Som calmo e constante." in meta["description"]
    assert "amber hours" in meta["tags"]
    assert "ruidobranco" in meta["tags"]


def test_prepare_seamless_loop_clip_returns_raw_clip_for_short_source(tmp_path, monkeypatch):
    import utils.ffmpeg_helpers as fh

    monkeypatch.setattr(fh, "media_duration_s", lambda path: 0.0)
    clip_path = tmp_path / "pixabay_1.mp4"

    out = noise_short._prepare_seamless_loop_clip(clip_path)

    assert out == clip_path


def test_prepare_seamless_loop_clip_bakes_a_crossfade_for_a_longer_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_short, "TEMP_DIR", tmp_path)
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

    out = noise_short._prepare_seamless_loop_clip(clip_path)

    assert out == tmp_path / "seamless_pixabay_1.mp4"
    assert "xfade" in calls[-1][calls[-1].index("-filter_complex") + 1]


def test_compose_short_builds_expected_command(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(noise_short.subprocess, "run", fake_run)

    broll_path = tmp_path / "pixabay_1.mp4"
    noise_bed_path = tmp_path / "noise.wav"
    output_path = tmp_path / "noise-1.mp4"

    ok = noise_short._compose_short(broll_path, noise_bed_path, output_path, 45.0)

    assert ok is True
    cmd = calls[-1]
    assert cmd[cmd.index("-t") + 1] == "45.000"


def test_compose_short_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(noise_short.subprocess, "run", fake_run)

    ok = noise_short._compose_short(tmp_path / "b.mp4", tmp_path / "n.wav", tmp_path / "out.mp4", 30.0)
    assert ok is False


def test_load_sidecar_returns_empty_dict_when_missing(tmp_path):
    assert noise_short._load_sidecar(tmp_path / "missing.mp4") == {}


def test_load_sidecar_reads_matching_json(tmp_path):
    video_path = tmp_path / "clip.mp4"
    video_path.with_suffix(".json").write_text('{"source": "pixabay"}', encoding="utf-8")

    assert noise_short._load_sidecar(video_path) == {"source": "pixabay"}


def test_extract_thumbnail_frame_returns_none_on_ffmpeg_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_short, "TEMP_DIR", tmp_path)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(noise_short.subprocess, "run", fake_run)

    assert noise_short._extract_thumbnail_frame(tmp_path / "clip.mp4", seed=1) is None


def test_extract_thumbnail_frame_returns_path_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_short, "TEMP_DIR", tmp_path)

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"fake-jpg")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(noise_short.subprocess, "run", fake_run)

    out = noise_short._extract_thumbnail_frame(tmp_path / "clip.mp4", seed=42)

    assert out == tmp_path / "thumb_42.jpg"
    assert out.exists()


def test_main_returns_error_when_broll_pool_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(noise_short, "NOISE_BROLL_DIR", tmp_path)
    monkeypatch.setattr(noise_short, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(noise_short, "TEMP_DIR", tmp_path / "_videos" / "temp")

    assert noise_short.main() == 1
