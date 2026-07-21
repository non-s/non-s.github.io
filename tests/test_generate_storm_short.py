"""Tests for generate_storm_short.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import generate_storm_short as storm_short


def test_pick_scene_returns_a_known_hook_scene():
    from utils.storm_branding import HOOK_BY_SCENE

    scene = storm_short._pick_scene()
    assert scene.lower() in HOOK_BY_SCENE


def test_build_metadata_uses_template_title_by_default(tmp_path):
    video_path = tmp_path / "storm-stormshort-1.mp4"

    meta = storm_short._build_metadata("deep sleep", 45.0, video_path, slug="stormshort-1700000000-1234")

    assert meta["title"] == storm_short.branded_title("deep sleep")
    assert meta["category"] == "storm_ambience"
    assert "is_short" not in meta  # defaults to True in upload_youtube.py, matching generate_lofi_short.py


def test_build_metadata_includes_shorts_hashtag(tmp_path):
    video_path = tmp_path / "storm-stormshort-2.mp4"

    meta = storm_short._build_metadata("focus", 45.0, video_path, slug="s-1")

    assert "#Shorts" in meta["description"]


def test_build_metadata_uses_ai_copy_when_available(tmp_path, monkeypatch):
    ai_result = {
        "title": "Quick Rain Break -- Amber Hours",
        "description": "A short rain moment to reset.",
        "hashtags": ["rain", "shorts"],
    }
    monkeypatch.setattr(storm_short, "generate_video_copy", lambda **kwargs: ai_result)
    video_path = tmp_path / "storm-stormshort-3.mp4"

    meta = storm_short._build_metadata("focus", 45.0, video_path, slug="s-2")

    assert meta["title"] == ai_result["title"]
    assert "A short rain moment to reset." in meta["description"]
    assert "#Shorts" in meta["description"]
    assert "amber hours" in meta["tags"]


def test_build_metadata_falls_back_to_template_when_ai_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(storm_short, "generate_video_copy", lambda **kwargs: None)
    video_path = tmp_path / "storm-stormshort-4.mp4"

    meta = storm_short._build_metadata("focus", 45.0, video_path, slug="s-3")

    assert meta["title"] == storm_short.branded_title("focus")


def test_prepare_rain_bed_writes_a_wav_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storm_short, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(storm_short, "RAIN_BED_SECONDS", 1.0)

    path = storm_short._prepare_rain_bed(seed=1)

    assert path.exists()
    assert path.stat().st_size > 0


def test_compose_short_builds_looping_ffmpeg_command(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(storm_short.subprocess, "run", fake_run)

    broll_path = tmp_path / "pinned_storm_short_clip.mp4"
    rain_path = tmp_path / "rain.wav"
    output_path = tmp_path / "storm-stormshort-5.mp4"

    ok = storm_short._compose_short(broll_path, rain_path, output_path, 45.0)

    assert ok is True
    cmd = calls[-1]
    assert "-stream_loop" in cmd
    assert str(broll_path) in cmd
    assert str(rain_path) in cmd
    assert cmd[cmd.index("-t") + 1] == "45.000"


def test_compose_short_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(storm_short.subprocess, "run", fake_run)

    ok = storm_short._compose_short(tmp_path / "b.mp4", tmp_path / "r.wav", tmp_path / "out.mp4", 30.0)
    assert ok is False
