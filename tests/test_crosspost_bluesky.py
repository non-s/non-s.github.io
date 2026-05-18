"""Tests for utils/crosspost_bluesky.py — auth/upload/post, no live HTTP."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import crosspost_bluesky as cb


def _touch_mp4(tmp_path: Path, size: int = 5 * 1024 * 1024) -> Path:
    p = tmp_path / "v.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * (size - 8))
    return p


def test_skips_when_no_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    video = _touch_mp4(tmp_path)
    assert cb.crosspost_video(video, caption="x") is None


def test_skips_when_video_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "h")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "p")
    assert cb.crosspost_video(tmp_path / "no.mp4", caption="x") is None


def test_skips_when_video_too_large(monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "h")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "p")
    video = _touch_mp4(tmp_path, size=50 * 1024 * 1024)
    assert cb.crosspost_video(video, caption="x") is None


def test_login_failure_aborts(monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "h")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "p")
    video = _touch_mp4(tmp_path)
    bad = MagicMock(status_code=401, text="bad")
    with patch("utils.crosspost_bluesky.requests.post", return_value=bad):
        assert cb.crosspost_video(video, caption="x") is None


def test_happy_path_returns_uri(monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "h")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "p")
    video = _touch_mp4(tmp_path)

    login_resp = MagicMock(status_code=200)
    login_resp.json.return_value = {"accessJwt": "JWT", "did": "did:test:abc"}
    upload_resp = MagicMock(status_code=200)
    upload_resp.json.return_value = {"blob": {"$type": "blob", "ref": "x"}}
    create_resp = MagicMock(status_code=200)
    create_resp.json.return_value = {
        "uri": "at://did:test:abc/app.bsky.feed.post/abc123",
        "cid": "bafyabc",
    }

    calls = {"n": 0}
    def fake_post(url, *a, **kw):
        calls["n"] += 1
        if "createSession" in url: return login_resp
        if "uploadBlob"   in url: return upload_resp
        if "createRecord" in url: return create_resp
        raise AssertionError("unexpected URL " + url)

    with patch("utils.crosspost_bluesky.requests.post", side_effect=fake_post):
        uri = cb.crosspost_video(video, caption="hello", alt_text="world",
                                  youtube_url="https://yt/abc")
    assert uri and uri.startswith("at://")
    assert calls["n"] == 3  # login, upload, create


def test_handles_create_record_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "h")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "p")
    video = _touch_mp4(tmp_path)

    login_resp = MagicMock(status_code=200)
    login_resp.json.return_value = {"accessJwt": "JWT", "did": "did:test"}
    upload_resp = MagicMock(status_code=200)
    upload_resp.json.return_value = {"blob": {"ref": "x"}}
    create_resp = MagicMock(status_code=400, text="bad")

    def fake_post(url, *a, **kw):
        if "createSession" in url: return login_resp
        if "uploadBlob"   in url: return upload_resp
        return create_resp

    with patch("utils.crosspost_bluesky.requests.post", side_effect=fake_post):
        assert cb.crosspost_video(video, caption="x") is None
