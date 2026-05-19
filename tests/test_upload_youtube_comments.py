"""Tests for the first-comment posting path in upload_youtube.py.

Covers the 403-insufficientPermissions latch added so the workflow log
isn't spammed once per video when the OAuth token wasn't granted
`youtube.force-ssl`. The latch makes the actionable "re-run
auth_youtube.py" warning fire exactly once per run.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("google.oauth2.credentials")
pytest.importorskip("googleapiclient.discovery")

from googleapiclient.errors import HttpError

import upload_youtube


def _http_error(status: int, reason: str = "") -> HttpError:
    """Mint an HttpError that quacks like the real Google API one.

    `HttpError.status_code` is a @property derived from `self.resp.status`
    — we set the latter and the former reads through.
    """
    resp = MagicMock()
    resp.status = status
    err = HttpError(resp=resp, content=b"{}")
    err.error_details = [{"reason": reason}] if reason else []
    return err


def test_is_insufficient_permissions_true_for_403_reason():
    err = _http_error(403, "insufficientPermissions")
    assert upload_youtube._is_insufficient_permissions(err) is True


def test_is_insufficient_permissions_false_for_other_403():
    err = _http_error(403, "quotaExceeded")
    assert upload_youtube._is_insufficient_permissions(err) is False


def test_is_insufficient_permissions_false_for_other_status():
    err = _http_error(500, "insufficientPermissions")
    assert upload_youtube._is_insufficient_permissions(err) is False


def test_is_insufficient_permissions_handles_missing_details():
    err = _http_error(403)
    # No error_details and no reason → not "insufficientPermissions"
    # specifically, so the helper returns False (and we fall through
    # to the generic warning path).
    assert upload_youtube._is_insufficient_permissions(err) is False


def test_try_post_first_comment_success_does_not_latch(monkeypatch):
    """Happy path: comment posts, the disable-latch stays open."""
    yt = MagicMock()
    monkeypatch.setattr(upload_youtube, "_post_first_comment", lambda *a, **kw: None)
    upload_youtube._try_post_first_comment(yt, "v1", {})
    assert upload_youtube._COMMENTS_DISABLED_THIS_RUN is False


def test_try_post_first_comment_latches_on_403_insufficient_permissions(monkeypatch, caplog):
    yt = MagicMock()
    err = _http_error(403, "insufficientPermissions")
    monkeypatch.setattr(upload_youtube, "_post_first_comment",
                        MagicMock(side_effect=err))
    with caplog.at_level("WARNING"):
        upload_youtube._try_post_first_comment(yt, "v1", {})
    assert upload_youtube._COMMENTS_DISABLED_THIS_RUN is True
    # Actionable instruction is in the warning, not a generic "failed".
    msg = "\n".join(r.getMessage() for r in caplog.records)
    assert "youtube.force-ssl" in msg
    assert "auth_youtube.py" in msg


def test_try_post_first_comment_latch_skips_subsequent_attempts(monkeypatch):
    """After the latch closes, _post_first_comment must not be called
    again in this run — otherwise we'd burn quota and log the same
    warning N times."""
    yt = MagicMock()
    upload_youtube._COMMENTS_DISABLED_THIS_RUN = True
    post = MagicMock()
    monkeypatch.setattr(upload_youtube, "_post_first_comment", post)
    upload_youtube._try_post_first_comment(yt, "v1", {})
    upload_youtube._try_post_first_comment(yt, "v2", {})
    post.assert_not_called()


def test_try_post_first_comment_other_http_error_does_not_latch(monkeypatch):
    """A 500 / 403-quotaExceeded / etc. should be logged but NOT close
    the latch — those are transient or different issues, not a missing
    scope."""
    yt = MagicMock()
    err = _http_error(500, "internalError")
    monkeypatch.setattr(upload_youtube, "_post_first_comment",
                        MagicMock(side_effect=err))
    upload_youtube._try_post_first_comment(yt, "v1", {})
    assert upload_youtube._COMMENTS_DISABLED_THIS_RUN is False


def test_try_post_first_comment_generic_exception_does_not_latch(monkeypatch):
    """Non-HttpError exceptions hit the catch-all warning, no latch."""
    yt = MagicMock()
    monkeypatch.setattr(upload_youtube, "_post_first_comment",
                        MagicMock(side_effect=RuntimeError("boom")))
    upload_youtube._try_post_first_comment(yt, "v1", {})
    assert upload_youtube._COMMENTS_DISABLED_THIS_RUN is False
