"""Tests for the soft-wait-for-audit behaviour in upload_tiktok.

When TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE and the TikTok app is still in
review, every cron run hits the
`unaudited_client_can_only_post_to_private_accounts` error. Rather
than falling back to Inbox (which would dump unwanted drafts on the
operator's phone), the runtime now:

  1. Increments `_audit_pending_count`.
  2. Logs a single line saying the video stays queued.
  3. Returns None from upload_video (no .done, .json sticks around).
  4. main() exits 0 when EVERY pending video skipped for this reason
     (workflow stays green; cron retries on the next run).

Once TikTok approves the app, the very next cron starts publishing
publicly with no additional config — the same code path that today
soft-skips, tomorrow succeeds.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import upload_tiktok


def _meta(tmp_path: Path) -> dict:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"\x00" * 1024)
    return {
        "video":       str(video),
        "title":       "test",
        "description": "test",
        "tags":        [],
    }


def _unaudited_error():
    return RuntimeError(
        "TikTok API .../init/ → HTTP 403: {'error': {'code': "
        "'unaudited_client_can_only_post_to_private_accounts'}}"
    )


def test_public_unaudited_skips_without_inbox_fallback(tmp_path, monkeypatch):
    """The headline behaviour: PUBLIC_TO_EVERYONE + unaudited = soft skip.
    No Inbox draft is created on the operator's phone."""
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "direct")
    monkeypatch.setenv("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE")
    upload_tiktok._audit_pending_count = 0

    inbox_calls = {"n": 0}

    monkeypatch.setattr(upload_tiktok, "_init_direct_post",
                         lambda *a, **kw: (_ for _ in ()).throw(_unaudited_error()))
    def _inbox(*a, **kw):
        inbox_calls["n"] += 1
        return {"data": {"publish_id": "x", "upload_url": "y"}}
    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload", _inbox)

    pid = upload_tiktok.upload_video("token", _meta(tmp_path))
    assert pid is None
    assert inbox_calls["n"] == 0  # NO Inbox draft
    assert upload_tiktok._audit_pending_count == 1


def test_self_only_unaudited_still_falls_back_to_inbox(tmp_path, monkeypatch):
    """The auto-fallback path stays for SELF_ONLY (operator explicitly
    asked for private direct; Inbox is the natural recovery)."""
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "direct")
    monkeypatch.setenv("TIKTOK_PRIVACY", "SELF_ONLY")
    upload_tiktok._audit_pending_count = 0

    inbox_calls = {"n": 0}

    monkeypatch.setattr(upload_tiktok, "_init_direct_post",
                         lambda *a, **kw: (_ for _ in ()).throw(_unaudited_error()))
    def _inbox(*a, **kw):
        inbox_calls["n"] += 1
        return {"data": {"publish_id": "p123", "upload_url": "y"}}
    monkeypatch.setattr(upload_tiktok, "_init_inbox_upload", _inbox)
    monkeypatch.setattr(upload_tiktok, "_upload_chunks", lambda *a, **kw: None)
    monkeypatch.setattr(upload_tiktok, "_poll_publish_status",
                         lambda *a, **kw: {"status": "SEND_TO_USER_INBOX"})

    pid = upload_tiktok.upload_video("token", _meta(tmp_path))
    assert pid == "p123"          # inbox publish OK
    assert inbox_calls["n"] == 1
    assert upload_tiktok._audit_pending_count == 0   # didn't count this one


def test_main_exits_zero_when_all_pending_are_audit_waiting(
    tmp_path, monkeypatch, caplog
):
    """The full workflow guard: a run where every pending video skipped
    waiting for audit should exit 0 so the GitHub Actions UI shows green."""
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "direct")
    monkeypatch.setenv("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE")
    monkeypatch.setattr(upload_tiktok, "VIDEOS_DIR", tmp_path)
    monkeypatch.setattr(upload_tiktok, "TOKEN_FILE", tmp_path / "tok.json")
    (tmp_path / "tok.json").write_text('{"access_token":"a","refresh_token":"r","expires_in":3600}')

    # Two pending videos that both hit unaudited.
    for i in range(2):
        (tmp_path / f"short-x{i}.json").write_text(
            f'{{"video": "{tmp_path}/v{i}.mp4", "title":"t{i}", '
            f'"description":"d{i}", "is_short": true}}'
        )
        (tmp_path / f"v{i}.mp4").write_bytes(b"\x00" * 1024)

    monkeypatch.setattr(upload_tiktok, "get_access_token",
                         lambda: ("a", {}))
    monkeypatch.setattr(upload_tiktok, "_init_direct_post",
                         lambda *a, **kw: (_ for _ in ()).throw(_unaudited_error()))

    upload_tiktok.main()


def test_main_exits_nonzero_on_real_failure(tmp_path, monkeypatch):
    """If a real (non-audit) error hits, exit 1 still. We don't want to
    mask actual bugs by always exit-0-ing."""
    monkeypatch.setenv("TIKTOK_PUBLISH_MODE", "direct")
    monkeypatch.setenv("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE")
    monkeypatch.setattr(upload_tiktok, "VIDEOS_DIR", tmp_path)
    monkeypatch.setattr(upload_tiktok, "TOKEN_FILE", tmp_path / "tok.json")
    (tmp_path / "tok.json").write_text('{"access_token":"a","refresh_token":"r","expires_in":3600}')
    (tmp_path / "short-bad.json").write_text(
        f'{{"video": "{tmp_path}/v.mp4", "title":"t", '
        f'"description":"d", "is_short": true}}'
    )
    (tmp_path / "v.mp4").write_bytes(b"\x00" * 1024)

    monkeypatch.setattr(upload_tiktok, "get_access_token",
                         lambda: ("a", {}))
    monkeypatch.setattr(upload_tiktok, "_init_direct_post",
                         lambda *a, **kw: (_ for _ in ()).throw(
                             RuntimeError("TikTok API → HTTP 400: 'invalid_params'")))

    with pytest.raises(SystemExit) as exc:
        upload_tiktok.main()
    assert exc.value.code == 1
