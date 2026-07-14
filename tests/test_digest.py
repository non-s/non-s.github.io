"""Tests for utils/digest.py — pure formatting + HTTP via mocks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import digest

# ── collect_recent_shorts ────────────────────────────────────────


def _write_done(dirpath: Path, slug: str, payload: dict) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / f"{slug}.done"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_collect_recent_shorts_includes_fresh(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(digest, "VIDEOS_DIRS", (Path("_videos"), Path("_videos_pt-BR")))
    from datetime import datetime, timezone, timedelta

    fresh = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _write_done(Path("_videos"), "fresh-en", {"title": "Fresh EN", "uploaded_at": fresh, "url": "https://yt/x"})
    out = digest.collect_recent_shorts(lookback_hours=24)
    assert len(out) == 1
    assert out[0]["title"] == "Fresh EN"


def test_collect_recent_shorts_excludes_old(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(digest, "VIDEOS_DIRS", (Path("_videos"),))
    from datetime import datetime, timezone, timedelta

    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    _write_done(Path("_videos"), "old-en", {"title": "Old", "uploaded_at": old, "url": "x"})
    assert digest.collect_recent_shorts(lookback_hours=24) == []


def test_collect_recent_shorts_includes_ptbr(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(digest, "VIDEOS_DIRS", (Path("_videos"), Path("_videos_pt-BR")))
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    _write_done(Path("_videos"), "en-short", {"title": "EN", "uploaded_at": now})
    _write_done(Path("_videos_pt-BR"), "ptbr-short", {"title": "PTBR", "uploaded_at": now})
    out = digest.collect_recent_shorts(lookback_hours=24)
    dirs = {d["_dir"] for d in out}
    assert dirs == {"_videos", "_videos_pt-BR"}


def test_collect_recent_shorts_skips_unparseable(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(digest, "VIDEOS_DIRS", (Path("_videos"),))
    Path("_videos").mkdir(parents=True)
    Path("_videos/garbage.done").write_text("not json", encoding="utf-8")
    assert digest.collect_recent_shorts(lookback_hours=24) == []


# ── render_digest ────────────────────────────────────────────────


def test_render_digest_lists_each_short():
    shorts = [
        {
            "title": "Story A",
            "url": "https://yt/a",
            "_slug": "slug-a",
            "_dir": "_videos",
            "uploaded_at": "2026-05-18T12:00:00+00:00",
            "description": "Lead sentence.\n#Shorts",
            "tags": ["fed", "powell"],
        },
        {
            "title": "Story B",
            "url": "https://yt/b",
            "_slug": "slug-b",
            "_dir": "_videos_pt-BR",
            "uploaded_at": "2026-05-18T13:00:00+00:00",
            "description": "Frase principal.\n#Shorts",
            "tags": ["bovespa"],
        },
    ]
    out = digest.render_digest(shorts)
    assert "Story A" in out
    assert "Story B" in out
    assert "[EN]" in out
    assert "[PT-BR]" in out
    assert "https://yt/a" in out
    assert "slug-a" in out


def test_render_digest_empty_explains_why():
    out = digest.render_digest([])
    assert "No Shorts shipped" in out


def test_render_digest_includes_analytics():
    out = digest.render_digest(
        [],
        analytics_summary={
            "avg_view_pct": 67.5,
            "total_views_14d": 12345,
            "below_60_pct": ["v1", "v2"],
            "category_avg_view_pct": {"cats": 72.0, "ocean": 55.0},
            "production_recommendations": {"hot_categories": ["cats"]},
        },
    )
    assert "67.5" in out
    assert "12345" in out
    assert "cats" in out.lower()
    assert "Mission control" in out


def test_render_digest_includes_production_quality_signals():
    out = digest.render_digest(
        [
            {
                "title": "Octopus",
                "_slug": "octopus-123",
                "_dir": "_videos",
                "uploaded_at": "2026-06-02T10:00:00+00:00",
                "has_broll": True,
                "has_captions": True,
                "script_quality_grade": 9,
                "monetization_audit": {"state": "monetization_ready", "score": 94},
                "visual_qa": {"checked": True, "approved": True, "thumbnail_quality": 8},
            }
        ]
    )
    assert "b-roll=yes" in out
    assert "captions=yes" in out
    assert "script grade=9" in out
    assert "monetization_ready" in out
    assert "visual QA: 8/10" in out


def test_render_digest_includes_audience_requests(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    comments = tmp_path / "_data" / "analytics" / "comments.json"
    comments.parent.mkdir(parents=True)
    comments.write_text(
        json.dumps(
            {
                "requested_animals": ["shark"],
                "content_prompts": ["Answer this viewer question: Can you do sharks?"],
            }
        ),
        encoding="utf-8",
    )
    out = digest.render_digest([])
    assert "Audience requests" in out
    assert "Can you do sharks" in out


# ── post_digest_issue ────────────────────────────────────────────


def test_post_issue_skips_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert digest.post_digest_issue("body") is None


def test_post_issue_returns_url_on_201(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    resp = MagicMock(status_code=201)
    resp.json.return_value = {"html_url": "https://github.com/owner/repo/issues/1"}
    with patch("utils.digest.requests.post", return_value=resp):
        url = digest.post_digest_issue("body")
    assert url == "https://github.com/owner/repo/issues/1"


def test_post_issue_returns_none_on_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    resp = MagicMock(status_code=403, text="forbidden")
    with patch("utils.digest.requests.post", return_value=resp):
        assert digest.post_digest_issue("body") is None


# ── blocked-slug load/save ───────────────────────────────────────


def test_load_blocked_slugs_handles_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(digest, "BLOCKED_FILE", tmp_path / "blocked.json")
    assert digest.load_blocked_slugs() == set()


def test_blocked_slugs_round_trip(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(digest, "BLOCKED_FILE", tmp_path / "blocked.json")
    digest.save_blocked_slugs({"abc-123", "xyz-789"})
    assert digest.load_blocked_slugs() == {"abc-123", "xyz-789"}


def test_load_blocked_slugs_handles_malformed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "blocked.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(digest, "BLOCKED_FILE", p)
    assert digest.load_blocked_slugs() == set()


# ── harvest_block_commands ──────────────────────────────────────


def test_harvest_block_commands_parses_comments(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

    issues_resp = MagicMock(status_code=200)
    issues_resp.json.return_value = [
        {"comments_url": "https://api/comments/1"},
    ]
    comments_resp = MagicMock(status_code=200)
    comments_resp.json.return_value = [
        {"body": "Looks good but /block abc-123-foo please"},
        {"body": "/block xyz-789-bar\n/block another-slug-yes"},
        {"body": "just a comment, no commands"},
    ]

    def fake_get(url, **kw):
        if "comments_url" in str(kw) or "/comments/" in url:
            return comments_resp
        return issues_resp

    with patch("utils.digest.requests.get", side_effect=fake_get):
        out = digest.harvest_block_commands()
    assert "abc-123-foo" in out
    assert "xyz-789-bar" in out
    assert "another-slug-yes" in out


def test_harvest_block_commands_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert digest.harvest_block_commands() == set()
