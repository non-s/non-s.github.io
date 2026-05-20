"""Tests for upload_tiktok upload_video — auto-fallback logic.

The Content Posting API rejects Direct Post requests from unaudited
apps with specific error codes ('scope_not_authorized',
'unaudited_client', etc.). When that happens the uploader should fall
back to Inbox mode automatically so the operator finalizes from the
TikTok mobile app, instead of dropping the upload for the run.
"""
from __future__ import annotations

from unittest.mock import patch

import upload_tiktok


def _make_meta(tmp_path):
    """Minimum meta dict + video file the uploader needs."""
    video = tmp_path / "short-foo.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 30_000)
    return {
        "video":          str(video),
        "title":          "A surprising cat fact",
        "description":    "Cats purr to heal their own bones.\n\n#fyp #foryou",
        "channel_handle": "@wildbrief_x",
    }


def test_direct_post_falls_back_to_inbox_on_unauthorized(tmp_path, monkeypatch):
    """When TikTok rejects Direct Post with a scope/unaudited error,
    the uploader retries via Inbox automatically — provided the
    operator hasn't opted into PUBLIC_TO_EVERYONE soft-skip behaviour
    (which prefers to wait for app audit instead of Inbox flooding)."""
    monkeypatch.setenv("TIKTOK_PRIVACY", "SELF_ONLY")
    meta = _make_meta(tmp_path)

    direct_called = {"n": 0}
    inbox_called  = {"n": 0}

    def fake_direct(*args, **kwargs):
        direct_called["n"] += 1
        raise RuntimeError(
            "TikTok API .../publish/video/init/ → error "
            "{'code': 'scope_not_authorized', 'message': 'unaudited_client_..."
            "can_only_post_to_private_accounts'}"
        )

    def fake_inbox(_token, _size):
        inbox_called["n"] += 1
        return {"data": {
            "publish_id": "v_inbox.test123",
            "upload_url": "https://upload.tiktok.test/path",
        }}

    monkeypatch.setattr(upload_tiktok, "_init_direct_post", fake_direct)
    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload", fake_inbox)
    # Stub the chunk upload + status polling so the test doesn't try
    # to actually PUT to TikTok.
    monkeypatch.setattr(upload_tiktok, "_upload_chunks", lambda *a, **kw: None)
    monkeypatch.setattr(upload_tiktok, "_poll_publish_status",
                        lambda *a, **kw: {"status": "PUBLISH_COMPLETE",
                                          "publicaly_available_post_id": "vid_xyz"})

    publish_id = upload_tiktok.upload_video("tk_fake_access_token", meta)
    assert publish_id  # uploaded successfully via fallback
    assert direct_called["n"] == 1
    assert inbox_called["n"] == 1


def test_direct_post_does_not_fall_back_on_other_errors(tmp_path, monkeypatch):
    """A generic non-scope error (e.g. bad request) should NOT silently
    drop into Inbox mode — that would mask real bugs."""
    meta = _make_meta(tmp_path)

    inbox_called = {"n": 0}

    def fake_direct(*args, **kwargs):
        raise RuntimeError("TikTok API .../init/ → HTTP 400: bad_request")

    monkeypatch.setattr(upload_tiktok, "_init_direct_post", fake_direct)
    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload",
                        lambda _t, _s: inbox_called.update(n=inbox_called["n"] + 1))

    publish_id = upload_tiktok.upload_video("tk_fake_access_token", meta)
    assert publish_id is None  # propagated as failure
    assert inbox_called["n"] == 0  # NOT called


def test_inbox_mode_skips_direct_post(tmp_path, monkeypatch):
    """When TIKTOK_PUBLISH_MODE=inbox is set explicitly, we never try
    Direct Post first."""
    meta = _make_meta(tmp_path)
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "inbox")

    direct_called = {"n": 0}

    monkeypatch.setattr(
        upload_tiktok, "_init_direct_post",
        lambda *a, **kw: direct_called.update(n=direct_called["n"] + 1),
    )
    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload",
                        lambda _t, _s: {"data": {
                            "publish_id": "v_inbox.test",
                            "upload_url": "https://upload.tiktok.test/path",
                        }})
    monkeypatch.setattr(upload_tiktok, "_upload_chunks", lambda *a, **kw: None)
    monkeypatch.setattr(upload_tiktok, "_poll_publish_status",
                        lambda *a, **kw: {"status": "PUBLISH_COMPLETE"})

    upload_tiktok.upload_video("tk_fake", meta)
    assert direct_called["n"] == 0
