"""Tests for upload_tiktok._poll_publish_status terminal states."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import upload_tiktok


def _payload(status: str) -> dict:
    return {"data": {"status": status, "publish_id": "p123"}}


def test_publish_complete_is_terminal(monkeypatch):
    """Direct post success state."""
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_INITIAL", 0)
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_MAX_S", 10)
    with patch.object(upload_tiktok, "_post_json",
                       return_value=_payload("PUBLISH_COMPLETE")):
        out = upload_tiktok._poll_publish_status("tok", "p123")
    assert out["status"] == "PUBLISH_COMPLETE"


def test_send_to_user_inbox_is_terminal(monkeypatch):
    """Inbox uploads stop here — TikTok parks the video in the user's
    mobile app, waiting for them to tap Post. We must NOT keep polling
    for PUBLISH_COMPLETE because that state never arrives.

    Before this fix, the runtime timed out 5 min later and reported the
    upload as failed even though the video was sitting in Inbox ready
    to publish."""
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_INITIAL", 0)
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_MAX_S", 10)
    with patch.object(upload_tiktok, "_post_json",
                       return_value=_payload("SEND_TO_USER_INBOX")):
        out = upload_tiktok._poll_publish_status("tok", "p123")
    assert out["status"] == "SEND_TO_USER_INBOX"


def test_failed_status_raises(monkeypatch):
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_INITIAL", 0)
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_MAX_S", 10)
    payload = {"data": {"status": "FAILED", "fail_reason": "moderation"}}
    with patch.object(upload_tiktok, "_post_json", return_value=payload):
        with pytest.raises(RuntimeError, match="FAILED"):
            upload_tiktok._poll_publish_status("tok", "p123")


def test_processing_states_continue_polling(monkeypatch):
    """Intermediate states should NOT return — only progress to next
    poll. Use a sequence: 2x PROCESSING_UPLOAD, then PUBLISH_COMPLETE."""
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_INITIAL", 0)
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_BACKOFF", 1.0)
    monkeypatch.setattr(upload_tiktok, "STATUS_POLL_MAX_S", 10)
    sequence = [
        _payload("PROCESSING_UPLOAD"),
        _payload("PROCESSING_UPLOAD"),
        _payload("PUBLISH_COMPLETE"),
    ]
    with patch.object(upload_tiktok, "_post_json", side_effect=sequence):
        out = upload_tiktok._poll_publish_status("tok", "p123")
    assert out["status"] == "PUBLISH_COMPLETE"
