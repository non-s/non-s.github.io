"""Tests for utils/video_compose.py â€” verify the FFmpeg filtergraph
construction, no actual encoding."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import video_compose


@pytest.fixture
def stub_ffprobe(monkeypatch):
    """ffprobe returns a known audio duration."""
    monkeypatch.setattr(video_compose, "_audio_duration_s", lambda p: 45.0)


@pytest.fixture
def stub_ffmpeg_ok(monkeypatch):
    """ffmpeg subprocess always succeeds."""
    calls: list[list[str]] = []

    def _fake_run(cmd, **kw):
        calls.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(video_compose.subprocess, "run", _fake_run)
    return calls


@pytest.fixture
def stub_ffmpeg_fail(monkeypatch):
    """ffmpeg subprocess returns rc=1."""

    def _fake_run(cmd, **kw):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "fake ffmpeg error"
        return result

    monkeypatch.setattr(video_compose.subprocess, "run", _fake_run)


def _touch(path: Path, size: int = 100_000) -> Path:
    path.write_bytes(b"x" * size)
    return path


def test_build_broll_short_succeeds(tmp_path, stub_ffprobe, stub_ffmpeg_ok, monkeypatch):
    # The brand-card overlay also runs by default. To keep this test
    # focused on the b-roll concat (and avoid pulling Pillow + the
    # PNG render path into a unit test), disable brand cards here.
    monkeypatch.setattr(video_compose, "BRAND_CARDS_ENABLED", False)
    out = tmp_path / "out.mp4"
    audio = _touch(tmp_path / "a.mp3")
    clips = [_touch(tmp_path / f"c{i}.mp4") for i in range(3)]
    ok = video_compose.build_broll_short(
        broll_paths=clips,
        audio_path=audio,
        output_path=out,
    )
    assert ok
    # Inspect the last ffmpeg invocation.
    last_cmd = stub_ffmpeg_ok[-1]
    # Must include all three -i broll paths plus the audio.
    input_idxs = [i for i, a in enumerate(last_cmd) if a == "-i"]
    assert len(input_idxs) == 4  # 3 clips + 1 audio (no brand cards)
    # Filtergraph references concat.
    fg_idx = last_cmd.index("-filter_complex")
    assert "concat=n=3" in last_cmd[fg_idx + 1]


def test_build_broll_short_with_brand_cards(tmp_path, stub_ffprobe, stub_ffmpeg_ok, monkeypatch):
    """When brand cards are enabled, the concat chain grows to 5
    (intro + 3 clips + outro) and there are 2 extra -i inputs."""
    monkeypatch.setattr(video_compose, "BRAND_CARDS_ENABLED", True)
    fake_intro = tmp_path / "intro.png"
    fake_outro = tmp_path / "outro.png"
    fake_intro.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 5000)
    fake_outro.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 5000)

    def fake_cards():
        return fake_intro, fake_outro

    # video_compose imports brand_card lazily; patch the sys.modules
    # entry it expects to find.
    import types, sys

    fake_module = types.ModuleType("utils.brand_card")
    fake_module.get_intro_outro_cards = fake_cards
    monkeypatch.setitem(sys.modules, "utils.brand_card", fake_module)

    out = tmp_path / "out.mp4"
    audio = _touch(tmp_path / "a.mp3")
    clips = [_touch(tmp_path / f"c{i}.mp4") for i in range(3)]
    ok = video_compose.build_broll_short(
        broll_paths=clips,
        audio_path=audio,
        output_path=out,
    )
    assert ok
    last_cmd = stub_ffmpeg_ok[-1]
    input_idxs = [i for i, a in enumerate(last_cmd) if a == "-i"]
    # 3 clips + 2 brand cards + 1 audio.
    assert len(input_idxs) == 6
    # Filtergraph concats intro + 3 clips + outro = 5 segments.
    fg_idx = last_cmd.index("-filter_complex")
    assert "concat=n=5" in last_cmd[fg_idx + 1]


def test_build_broll_short_returns_false_without_clips(tmp_path, stub_ffprobe):
    audio = _touch(tmp_path / "a.mp3")
    assert not video_compose.build_broll_short(
        broll_paths=[],
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
    )


def test_build_broll_short_returns_false_without_audio(tmp_path):
    audio = tmp_path / "missing.mp3"
    clips = [_touch(tmp_path / "c.mp4")]
    assert not video_compose.build_broll_short(
        broll_paths=clips,
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
    )


def test_build_broll_short_with_hook_overlay(tmp_path, stub_ffprobe, stub_ffmpeg_ok, monkeypatch):
    monkeypatch.setattr(video_compose, "_font_path", lambda: "/tmp/fake-font.ttf")
    audio = _touch(tmp_path / "a.mp3")
    clips = [_touch(tmp_path / "c.mp4")]
    video_compose.build_broll_short(
        broll_paths=clips,
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
        hook_text="This octopus vanished against coral",
    )
    fg = next(arg for arg in stub_ffmpeg_ok[-1] if isinstance(arg, str) and "drawtext" in arg)
    assert "This octopus vanished against coral" in fg
    assert "between(t,0,3)" in fg


def test_build_broll_short_with_cta_overlay(tmp_path, stub_ffprobe, stub_ffmpeg_ok, monkeypatch):
    monkeypatch.setattr(video_compose, "_font_path", lambda: "/tmp/fake-font.ttf")
    audio = _touch(tmp_path / "a.mp3")
    clips = [_touch(tmp_path / "c.mp4")]
    video_compose.build_broll_short(
        broll_paths=clips,
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
        cta_text="SUBSCRIBE FOR MORE ANIMAL FACTS",
    )
    fg = next(arg for arg in stub_ffmpeg_ok[-1] if isinstance(arg, str) and "drawtext" in arg)
    assert "SUBSCRIBE" in fg


def test_build_broll_short_with_opening_cover(tmp_path, stub_ffprobe, stub_ffmpeg_ok, monkeypatch):
    monkeypatch.setattr(video_compose, "_font_path", lambda: "/tmp/fake-font.ttf")
    audio = _touch(tmp_path / "a.mp3")
    clips = [_touch(tmp_path / "c.mp4")]
    video_compose.build_broll_short(
        broll_paths=clips,
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
        cover_text="OCTOPUS VANISHES",
    )
    fg = next(arg for arg in stub_ffmpeg_ok[-1] if isinstance(arg, str) and "drawtext" in arg)
    assert "OCTOPUS VANISHES" in fg
    assert "between(t,0,1.2)" in fg


def test_static_fallback_keeps_channel_cta(tmp_path, stub_ffprobe, stub_ffmpeg_ok, monkeypatch):
    monkeypatch.setattr(video_compose, "_font_path", lambda: "/tmp/fake-font.ttf")
    frame = _touch(tmp_path / "frame.png")
    audio = _touch(tmp_path / "a.mp3")
    video_compose.build_static_short(
        frame_path=frame,
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
        cover_text="OWL NIGHT VISION",
        cta_text="SUBSCRIBE FOR MORE ANIMAL FACTS",
    )
    fg = next(arg for arg in stub_ffmpeg_ok[-1] if isinstance(arg, str) and "drawtext" in arg)
    assert "OWL NIGHT VISION" in fg
    assert "SUBSCRIBE" in fg


def test_build_broll_short_with_ass_subtitles(tmp_path, stub_ffprobe, stub_ffmpeg_ok):
    audio = _touch(tmp_path / "a.mp3")
    clips = [_touch(tmp_path / "c.mp4")]
    ass = _touch(tmp_path / "subs.ass", size=500)
    video_compose.build_broll_short(
        broll_paths=clips,
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
        ass_subtitle_path=ass,
    )
    fg = next(arg for arg in stub_ffmpeg_ok[-1] if isinstance(arg, str) and "ass=" in arg)
    assert "subs.ass" in fg


def test_build_broll_short_propagates_ffmpeg_failure(tmp_path, stub_ffprobe, stub_ffmpeg_fail):
    audio = _touch(tmp_path / "a.mp3")
    clips = [_touch(tmp_path / "c.mp4")]
    assert not video_compose.build_broll_short(
        broll_paths=clips,
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
    )


def test_build_static_short_basic(tmp_path, stub_ffprobe, stub_ffmpeg_ok):
    frame = _touch(tmp_path / "frame.png")
    audio = _touch(tmp_path / "a.mp3")
    ok = video_compose.build_static_short(
        frame_path=frame,
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
    )
    assert ok


def test_build_static_short_missing_frame(tmp_path):
    audio = _touch(tmp_path / "a.mp3")
    assert not video_compose.build_static_short(
        frame_path=tmp_path / "no.png",
        audio_path=audio,
        output_path=tmp_path / "out.mp4",
    )


def test_ffmpeg_escape_handles_special_chars():
    out = video_compose._ffmpeg_escape("hello: world's 'test' \\path")
    # ":" â†’ "\:"; "'" â†’ "\'"
    assert "\\:" in out
    assert "\\'" in out


def test_ffmpeg_escape_handles_empty():
    assert video_compose._ffmpeg_escape("") == ""
    assert video_compose._ffmpeg_escape(None) == ""


def test_overlay_copy_keeps_mobile_text_compact():
    text = "Cats purr to heal their own bones and reduce stress after injuries."
    compact = video_compose._overlay_copy(text)
    assert len(compact) <= 42
    assert compact.endswith("...")


def test_max_duration_targets_shorts_completion_rate():
    """YouTube Shorts reward completion rate; we cap
    at 35s so a 90 % completion rate is achievable on every Short
    instead of a 50 % rate on 55s+ videos. Hard ceiling is 35s â€” the
    AI prompt is tuned to 70-90 words which renders to ~25-30s."""
    assert video_compose.MAX_DURATION_S <= 24.0
