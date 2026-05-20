"""Tests for upload_tiktok._collect_pending_meta.

Regression coverage for the bug that froze the daily Shorts cadence
back when the channel was on YouTube: the uploader globbed `*.json`
inside `_videos/`, which also matched `shorts_done.json` (a list of
slugs the generator writes for idempotency). The TikTok uploader keeps
the same `short-…` / `roundup-…` prefix filter to avoid the same trap.
"""
from __future__ import annotations

from pathlib import Path

from upload_tiktok import _collect_pending_meta


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
