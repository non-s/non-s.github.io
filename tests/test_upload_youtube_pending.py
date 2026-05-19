"""Tests for upload_youtube._collect_pending_meta.

Regression coverage for the bug that froze the daily Shorts cadence
between 2026-05-16 and 2026-05-19: the uploader globbed `*.json`
inside `_videos/`, which also matched `shorts_done.json` (a list of
slugs the generator writes for idempotency). The uploader then
crashed with `AttributeError: 'list' object has no attribute 'get'`
after the first successful upload, abandoning the rest of the queue.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# upload_youtube.py pulls google.oauth2 at module import. Skip the
# suite cleanly when those libs aren't installed in the sandbox; CI
# has them so coverage is preserved there.
pytest.importorskip("google.oauth2.credentials")
pytest.importorskip("googleapiclient.discovery")

from upload_youtube import _collect_pending_meta


def _touch(p: Path, content: str = "{}") -> None:
    p.write_text(content, encoding="utf-8")


def test_includes_short_and_roundup_meta(tmp_path: Path):
    _touch(tmp_path / "short-2026-05-19-foo.json")
    _touch(tmp_path / "roundup-2026-05-19-14.json")
    pending = _collect_pending_meta(tmp_path)
    names = {p.name for p in pending}
    assert names == {
        "short-2026-05-19-foo.json",
        "roundup-2026-05-19-14.json",
    }


def test_filters_out_shorts_done_ledger(tmp_path: Path):
    """The poison pill: a JSON list that broke the old glob."""
    _touch(tmp_path / "short-2026-05-19-foo.json")
    _touch(tmp_path / "shorts_done.json", content='["slug-a", "slug-b"]')
    pending = _collect_pending_meta(tmp_path)
    assert [p.name for p in pending] == ["short-2026-05-19-foo.json"]


def test_filters_out_unrelated_json(tmp_path: Path):
    """Stray *.json files (config, scratch, anything) must not be
    treated as meta sidecars."""
    _touch(tmp_path / "short-2026-05-19-foo.json")
    _touch(tmp_path / "scratch.json")
    _touch(tmp_path / "config.json")
    _touch(tmp_path / "yt_playlists.json")  # mirrors the real PLAYLIST_DATA_FILE name
    pending = _collect_pending_meta(tmp_path)
    assert [p.name for p in pending] == ["short-2026-05-19-foo.json"]


def test_returns_empty_when_no_meta(tmp_path: Path):
    _touch(tmp_path / "shorts_done.json", content='[]')
    assert _collect_pending_meta(tmp_path) == []


def test_returns_empty_for_empty_dir(tmp_path: Path):
    assert _collect_pending_meta(tmp_path) == []


def test_order_is_deterministic(tmp_path: Path):
    # roundup-* sorts BEFORE short-* alphabetically — the uploader
    # relies on that order so a roundup ships before the day's Shorts.
    _touch(tmp_path / "short-2026-05-19-b.json")
    _touch(tmp_path / "short-2026-05-19-a.json")
    _touch(tmp_path / "roundup-2026-05-19-14.json")
    names = [p.name for p in _collect_pending_meta(tmp_path)]
    assert names == [
        "roundup-2026-05-19-14.json",
        "short-2026-05-19-a.json",
        "short-2026-05-19-b.json",
    ]


def test_runtime_scopes_match_existing_token_grant():
    """`upload_youtube.SCOPES` is passed to `Credentials.from_authorized_user_file`
    and ridden through to `refresh()`. If it claims a scope the live
    refresh_token wasn't actually granted, Google rejects the refresh
    with `invalid_scope: Bad Request` and the whole run fails before
    a single upload. This pinned in production on 2026-05-19 12:02 UTC
    after `youtube.force-ssl` was added optimistically — the secret in
    the workflow wasn't re-minted with that scope, so the refresh broke.

    `auth_youtube.py` is the right place to advertise new scopes (it
    runs locally and triggers a fresh consent flow). The runtime
    loader must stay narrow to what the existing token has.
    """
    from upload_youtube import SCOPES
    assert "https://www.googleapis.com/auth/youtube.force-ssl" not in SCOPES, (
        "Adding youtube.force-ssl here would invalidate existing tokens — "
        "advertise the broader scope in auth_youtube.py instead."
    )
