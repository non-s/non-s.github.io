"""Tests for upload_tiktok.upload_video's direct→inbox fallback.

When TikTok rejects a direct-post init for an unaudited client (typical
during the multi-week app-review window), upload_video retries via the
Inbox endpoint in the same run instead of bailing. The video lands as
a draft in the user's TikTok app for manual publish.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import upload_tiktok


def _meta(tmp_path: Path) -> dict:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"\x00" * 1024)  # 1KB stub
    return {
        "video":       str(video),
        "title":       "test",
        "description": "test",
        "tags":        [],
    }


def _ok_init(publish_id: str = "p123") -> dict:
    return {
        "data": {
            "publish_id":  publish_id,
            "upload_url":  "https://upload.tiktokapis.com/fake",
        }
    }


def test_falls_back_to_inbox_on_unaudited_error(tmp_path, monkeypatch):
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "direct")
    monkeypatch.delenv("LANGUAGE", raising=False)
    meta = _meta(tmp_path)

    direct_called = {"n": 0}
    inbox_called  = {"n": 0}

    def _direct(*a, **kw):
        direct_called["n"] += 1
        raise RuntimeError(
            "TikTok API .../init/ → error {'code': "
            "'unaudited_client_can_only_post_to_private_accounts', ...}"
        )

    def _inbox(*a, **kw):
        inbox_called["n"] += 1
        return _ok_init()

    monkeypatch.setattr(upload_tiktok, "_init_direct_post", _direct)
    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload", _inbox)
    monkeypatch.setattr(upload_tiktok, "_upload_chunks", lambda *a, **kw: None)
    monkeypatch.setattr(upload_tiktok, "_poll_publish_status",
                         lambda *a, **kw: {"status": "PUBLISH_COMPLETE"})

    pid = upload_tiktok.upload_video("fake_token", meta)
    assert pid == "p123"
    assert direct_called["n"] == 1
    assert inbox_called["n"] == 1


@pytest.mark.parametrize("signal", [
    "scope_not_authorized",
    "unaudited_client",
    "unaudited_client_can_only_post_to_private_accounts",
])
def test_falls_back_for_each_unaudited_signal(tmp_path, monkeypatch, signal):
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "direct")
    meta = _meta(tmp_path)

    monkeypatch.setattr(
        upload_tiktok, "_init_direct_post",
        lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError(f"TikTok API → error {{'code': '{signal}'}}")
        ),
    )
    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload",
                         lambda *a, **kw: _ok_init("p-inbox"))
    monkeypatch.setattr(upload_tiktok, "_upload_chunks", lambda *a, **kw: None)
    monkeypatch.setattr(upload_tiktok, "_poll_publish_status",
                         lambda *a, **kw: {"status": "PUBLISH_COMPLETE"})

    assert upload_tiktok.upload_video("fake_token", meta) == "p-inbox"


def test_does_not_fallback_on_generic_400(tmp_path, monkeypatch):
    """A generic 400 (e.g. malformed body, missing scope unrelated to
    audit status) should propagate as a failed publish, not silently
    fall back — otherwise real bugs get masked as drafts."""
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "direct")
    meta = _meta(tmp_path)

    monkeypatch.setattr(
        upload_tiktok, "_init_direct_post",
        lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("TikTok API → HTTP 400: 'invalid_params'")
        ),
    )
    inbox_called = {"n": 0}
    def _inbox(*a, **kw):
        inbox_called["n"] += 1
        return _ok_init()
    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload", _inbox)

    assert upload_tiktok.upload_video("fake_token", meta) is None
    assert inbox_called["n"] == 0


def test_explicit_inbox_mode_does_not_double_call(tmp_path, monkeypatch):
    """If the operator already set TIKTOK_PUBLISH_MODE=inbox, an init
    failure shouldn't trigger another inbox attempt (no loop)."""
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "inbox")
    meta = _meta(tmp_path)

    call_count = {"n": 0}
    def _inbox(*a, **kw):
        call_count["n"] += 1
        raise RuntimeError("permanent inbox failure")

    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload", _inbox)
    assert upload_tiktok.upload_video("fake_token", meta) is None
    assert call_count["n"] == 1  # NO retry
