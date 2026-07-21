"""Tests for scripts/generate_storm_scene.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import scripts.generate_storm_scene as storm_scene


def test_build_storm_frame_returns_expected_size_and_mode():
    frame = storm_scene.build_storm_frame(0.5)
    assert frame.size == (storm_scene.W, storm_scene.H)
    assert frame.mode == "RGB"


def test_build_storm_frame_phase_0_equals_phase_1():
    """Same invariant as utils/brand_motion.py's animated layers: the loop
    must be mathematically seamless, not just visually close."""
    a = storm_scene.build_storm_frame(0.0)
    b = storm_scene.build_storm_frame(1.0)
    assert list(a.getdata()) == list(b.getdata())


def test_build_storm_frame_at_a_flash_phase_is_brighter_than_between_flashes():
    flash_frame = storm_scene.build_storm_frame(storm_scene.FLASH_PHASES[0])
    calm_frame = storm_scene.build_storm_frame((storm_scene.FLASH_PHASES[0] + 0.5) % 1.0)
    assert sum(flash_frame.getpixel((10, 10))) > sum(calm_frame.getpixel((10, 10)))


def test_storm_clouds_draws_something():
    layer = storm_scene.storm_clouds(400, 300, seed=1)
    assert layer.size == (400, 300)
    assert any(pixel[3] > 0 for pixel in layer.getdata())


def test_build_storm_short_frame_returns_expected_size_and_mode():
    frame = storm_scene.build_storm_short_frame(0.5)
    assert frame.size == (storm_scene.W_SHORT, storm_scene.H_SHORT)
    assert frame.mode == "RGB"


def test_build_storm_short_frame_phase_0_equals_phase_1():
    a = storm_scene.build_storm_short_frame(0.0)
    b = storm_scene.build_storm_short_frame(1.0)
    assert list(a.getdata()) == list(b.getdata())


def test_encode_loop_builds_expected_ffmpeg_command(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(storm_scene.subprocess, "run", fake_run)

    out_path = tmp_path / "pinned_storm_clip.mp4"
    ok = storm_scene._encode_loop(tmp_path, out_path)

    assert ok is True
    cmd = calls[-1]
    assert "-framerate" in cmd
    assert str(storm_scene.LOOP_FPS) in cmd
    assert out_path.exists()


def test_encode_loop_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(storm_scene.subprocess, "run", fake_run)

    ok = storm_scene._encode_loop(tmp_path, tmp_path / "out.mp4")
    assert ok is False
