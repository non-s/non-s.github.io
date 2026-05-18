"""Tests for utils/intro_outro.py — cache + concat behaviour, no real TTS."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import intro_outro


def test_concat_audio_no_intro_no_outro_copies_body(tmp_path):
    body = tmp_path / "body.mp3"
    body.write_bytes(b"BODY")
    out = tmp_path / "out.mp3"
    assert intro_outro.concat_audio(None, body, None, out)
    assert out.read_bytes() == b"BODY"


def test_concat_audio_returns_false_when_body_missing(tmp_path):
    body = tmp_path / "missing.mp3"
    out = tmp_path / "out.mp3"
    # No actual concat possible — should fail cleanly.
    assert not intro_outro.concat_audio(None, body, None, out)


def test_wrap_with_intro_outro_disabled_returns_body(tmp_path, monkeypatch):
    monkeypatch.setattr(intro_outro, "ENABLED", False)
    body = tmp_path / "body.mp3"
    body.write_bytes(b"BODY")
    out = intro_outro.wrap_with_intro_outro(body, voice="en-US-AriaNeural",
                                              tmp_dir=tmp_path)
    assert out == body


def test_wrap_with_intro_outro_falls_back_when_render_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(intro_outro, "ENABLED", True)
    monkeypatch.setattr(intro_outro, "get_or_render", lambda *a, **kw: None)
    body = tmp_path / "body.mp3"
    body.write_bytes(b"BODY")
    out = intro_outro.wrap_with_intro_outro(body, voice="en-US-AriaNeural",
                                              tmp_dir=tmp_path)
    # Both intro + outro returned None → original body returned unchanged.
    assert out == body


def test_wrap_with_intro_outro_concats_when_renders_succeed(tmp_path, monkeypatch):
    monkeypatch.setattr(intro_outro, "ENABLED", True)
    fake_intro = tmp_path / "intro.mp3"
    fake_intro.write_bytes(b"INTRO")
    fake_outro = tmp_path / "outro.mp3"
    fake_outro.write_bytes(b"OUTRO")

    def fake_render(line, voice, fn=None):
        return fake_intro if "brief" in line.lower() else fake_outro

    monkeypatch.setattr(intro_outro, "get_or_render", fake_render)

    body = tmp_path / "body.mp3"
    body.write_bytes(b"BODY")

    def fake_concat(intro, body_p, outro, out):
        # Verify both intro + outro flow through.
        assert intro is not None
        assert outro is not None
        out.write_bytes(b"WRAPPED")
        return True

    monkeypatch.setattr(intro_outro, "concat_audio", fake_concat)
    out = intro_outro.wrap_with_intro_outro(body, voice="en-US-AriaNeural",
                                              tmp_dir=tmp_path)
    assert out != body
    assert out.read_bytes() == b"WRAPPED"


def test_get_or_render_returns_cached_path(tmp_path, monkeypatch):
    monkeypatch.setattr(intro_outro, "ENABLED", True)
    monkeypatch.setattr(intro_outro, "INTRO_OUTRO_CACHE", tmp_path / "cache")
    # Seed the cache directly.
    cache = tmp_path / "cache"
    cache.mkdir(parents=True)
    key = intro_outro._cache_key("hello", "en-US-AriaNeural")
    cached = cache / f"{key}.mp3"
    cached.write_bytes(b"X" * 5000)
    out = intro_outro.get_or_render("hello", "en-US-AriaNeural")
    assert out == cached


def test_get_or_render_skips_when_line_empty():
    assert intro_outro.get_or_render("", "en-US-AriaNeural") is None
    assert intro_outro.get_or_render("   ", "en-US-AriaNeural") is None
