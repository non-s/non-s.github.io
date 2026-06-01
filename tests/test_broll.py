"""Tests for utils/broll.py — discovery + download, no live HTTP."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import broll


# ── _build_query ─────────────────────────────────────────────────

def test_build_query_strips_stopwords():
    out = broll._build_query("The octopus just changed colour near coral today")
    assert "the" not in out.lower().split()
    assert "octopus" in out
    assert "colour" in out


def test_build_query_empty_input():
    assert broll._build_query("") == ""
    assert broll._build_query(None) == ""


def test_build_query_caps_tokens():
    """Long titles should still produce a short search query."""
    out = broll._build_query("Octopus Dolphin Whale Owl Eagle Cat Dog Horse Goat")
    assert len(out.split()) <= 6


# ── Pexels ────────────────────────────────────────────────────────

def _pexels_payload():
    return {
        "videos": [
            {
                "url": "https://www.pexels.com/video/x/",
                "duration": 12,
                "user": {"name": "Test Author"},
                "video_files": [
                    {"link": "https://cdn.pexels.com/big.mp4",  "width": 1080, "height": 1920},
                    {"link": "https://cdn.pexels.com/small.mp4","width": 720,  "height": 1280},
                ],
            },
        ]
    }


def test_pexels_returns_clips_when_key_set(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=200)
    fake.json.return_value = _pexels_payload()
    with patch.object(broll, "_session") as factory:
        s = MagicMock(); s.get.return_value = fake; factory.return_value = s
        clips = broll.fetch_pexels("octopus animal")
    assert len(clips) == 1
    assert clips[0].source == "pexels"
    assert clips[0].download_url.endswith(".mp4")
    assert clips[0].height >= 1920 or clips[0].width >= 1080


def test_pexels_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    assert broll.fetch_pexels("anything") == []


def test_pexels_returns_empty_on_non_200(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=429); fake.json.return_value = {}
    with patch.object(broll, "_session") as factory:
        s = MagicMock(); s.get.return_value = fake; factory.return_value = s
        assert broll.fetch_pexels("x") == []


def test_pexels_cache_avoids_second_call(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=200); fake.json.return_value = _pexels_payload()
    calls = {"n": 0}

    def make_session():
        s = MagicMock()
        def _get(*a, **kw):
            calls["n"] += 1
            return fake
        s.get.side_effect = _get
        return s
    with patch.object(broll, "_session", side_effect=make_session):
        broll.fetch_pexels("identical query")
        broll.fetch_pexels("identical query")
    assert calls["n"] == 1


# ── fetch_broll_clips orchestration ────────────────────────────── 

def test_fetch_broll_returns_vetted_pexels_clips(monkeypatch):
    fake_pexels = [
        broll.BrollClip(source="pexels", url="", download_url=f"https://a/{i}",
                         width=1080, height=1920, duration_s=10) for i in range(2)
    ]
    with patch.object(broll, "fetch_pexels", return_value=fake_pexels):
        out = broll.fetch_broll_clips("octopus underwater animal", want_n=3)
    assert len(out) == 2
    sources = {c.source for c in out}
    assert "pexels" in sources


def test_fetch_broll_deduplicates_by_url(monkeypatch):
    same = broll.BrollClip(source="pexels", url="", download_url="https://dup",
                            width=1080, height=1920, duration_s=10)
    with patch.object(broll, "fetch_pexels", return_value=[same]):
        out = broll.fetch_broll_clips("x", want_n=5)
    assert len(out) == 1


def test_fetch_broll_returns_empty_on_total_failure(monkeypatch):
    with patch.object(broll, "fetch_pexels", return_value=[]):
        out = broll.fetch_broll_clips("x", want_n=3)
    assert out == []


def test_fetch_broll_animal_only_uses_pexels(monkeypatch):
    pexels = [
        broll.BrollClip(source="pexels", url="", download_url="https://animal",
                        width=1080, height=1920, duration_s=10),
    ]
    with patch.object(broll, "fetch_pexels", return_value=pexels):
        out = broll.fetch_broll_clips("octopus underwater animal",
                                      want_n=3, animal_only=True)
    assert out == pexels


# ── download_clip ────────────────────────────────────────────────

def test_download_clip_writes_valid_mp4(tmp_path):
    dest = tmp_path / "out.mp4"
    # Tiny valid-looking MP4: starts with `....ftyp` after some bytes.
    body = b"\x00\x00\x00\x18ftypmp42" + b"x" * 60_000
    fake = MagicMock(status_code=200)
    fake.iter_content.return_value = [body]
    clip = broll.BrollClip(source="test", url="", download_url="https://e/x.mp4",
                            width=1080, height=1920, duration_s=10)
    with patch.object(broll, "_session") as factory:
        s = MagicMock(); s.get.return_value = fake; factory.return_value = s
        ok = broll.download_clip(clip, dest)
    assert ok
    assert dest.exists()
    assert dest.read_bytes().startswith(b"\x00\x00\x00\x18ftyp")


def test_download_clip_rejects_non_mp4(tmp_path):
    dest = tmp_path / "out.mp4"
    body = b"<html>not a video</html>" * 1000
    fake = MagicMock(status_code=200)
    fake.iter_content.return_value = [body]
    clip = broll.BrollClip(source="test", url="", download_url="https://e/x.mp4",
                            width=1, height=1, duration_s=10)
    with patch.object(broll, "_session") as factory:
        s = MagicMock(); s.get.return_value = fake; factory.return_value = s
        assert not broll.download_clip(clip, dest)


def test_download_clip_aborts_oversized(tmp_path):
    dest = tmp_path / "out.mp4"
    # 35 MB > max_bytes=30 MB.
    chunks = [b"a" * (1024 * 1024) for _ in range(35)]
    fake = MagicMock(status_code=200)
    fake.iter_content.return_value = chunks
    clip = broll.BrollClip(source="test", url="", download_url="https://e/x.mp4",
                            width=1, height=1, duration_s=10)
    with patch.object(broll, "_session") as factory:
        s = MagicMock(); s.get.return_value = fake; factory.return_value = s
        assert not broll.download_clip(clip, dest)
