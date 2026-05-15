"""Smoke tests for utils/public_sources.py — no live HTTP."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest


def _fake_response(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.text = ""
    return r


def test_reddit_filters_internal_links_and_low_score():
    from utils import public_sources

    def fake_get(url, timeout=None):
        return _fake_response({
            "data": {
                "children": [
                    # Pass: external link, decent score
                    {"data": {
                        "title": "Major event reported globally",
                        "url_overridden_by_dest": "https://example.com/a",
                        "score": 500, "created_utc": 1715000000,
                        "selftext": "context"
                    }},
                    # Reject: links back to reddit
                    {"data": {
                        "title": "self post",
                        "url_overridden_by_dest": "https://reddit.com/r/x/y",
                        "score": 500, "created_utc": 1715000000,
                    }},
                    # Reject: below min_score
                    {"data": {
                        "title": "obscure",
                        "url_overridden_by_dest": "https://example.com/b",
                        "score": 10, "created_utc": 1715000000,
                    }},
                ]
            }
        })

    with patch.object(public_sources, "_session") as fake_session_factory:
        fake_session = MagicMock()
        fake_session.get.side_effect = lambda *a, **k: fake_get(*a, **k)
        fake_session_factory.return_value = fake_session
        results = public_sources.fetch_reddit_trending(per_sub=5, min_score=200)

    # Exactly one passes (external + high score), per sub × 11 subs.
    assert len(results) == 11
    assert all(r["link"].startswith("https://example.com") for r in results)
    assert all(r["source"].startswith("Reddit r/") for r in results)


def test_hackernews_skips_dead_and_low_score():
    from utils import public_sources

    def fake_get(url, timeout=None):
        if "topstories" in url:
            return _fake_response([1, 2, 3])
        if "/item/1.json" in url:
            return _fake_response({"type": "story", "title": "A", "url": "https://e.test/1", "score": 300, "time": 1715000000})
        if "/item/2.json" in url:
            return _fake_response({"type": "story", "title": "B", "url": "https://e.test/2", "score": 50, "time": 1715000000})
        if "/item/3.json" in url:
            return _fake_response({"type": "story", "title": "C", "url": "https://e.test/3", "score": 300, "time": 1715000000, "dead": True})
        return _fake_response({}, status=404)

    with patch.object(public_sources, "_session") as fake_session_factory:
        fake_session = MagicMock()
        fake_session.get.side_effect = lambda *a, **k: fake_get(*a, **k)
        fake_session_factory.return_value = fake_session
        results = public_sources.fetch_hackernews_top(limit=10, min_score=100)

    titles = [r["title"] for r in results]
    assert titles == ["A"]  # B too low, C dead


def test_hackernews_classifies_ai_titles():
    from utils import public_sources

    def fake_get(url, timeout=None):
        if "topstories" in url:
            return _fake_response([10])
        return _fake_response({
            "type": "story", "title": "OpenAI launches new GPT model",
            "url": "https://e.test/x", "score": 300, "time": 1715000000,
        })

    with patch.object(public_sources, "_session") as fake_session_factory:
        fake_session = MagicMock()
        fake_session.get.side_effect = lambda *a, **k: fake_get(*a, **k)
        fake_session_factory.return_value = fake_session
        results = public_sources.fetch_hackernews_top(limit=1, min_score=100)

    assert results[0]["category"] == "ai"


def test_wikipedia_current_events_extracts_external_citations():
    from utils import public_sources

    html = """
    <html><body>
      <ul>
        <li>Some background <a href="/wiki/X">link</a>. Major election results announced. <a rel="nofollow" href="https://e.test/election">Reuters</a></li>
        <li>Internal-only event <a href="/wiki/Y">link</a> with no external citation.</li>
        <li>See main article: ignored. <a rel="nofollow" href="https://e.test/skip">x</a></li>
      </ul>
    </body></html>
    """

    fake_resp = MagicMock(status_code=200, text=html)
    with patch.object(public_sources, "_session") as fake_session_factory:
        fake_session = MagicMock()
        fake_session.get.return_value = fake_resp
        fake_session_factory.return_value = fake_session
        results = public_sources.fetch_wikipedia_current_events(days=1)

    assert any("election" in r["link"] for r in results)
    # The "see main article" line should be filtered out by the heuristic.
    assert not any("/skip" in r["link"] for r in results)


def test_fetch_all_dedupes_by_link():
    from utils import public_sources

    fake_item = lambda link: {
        "title": "t", "link": link, "description": "d", "image": "",
        "published": datetime.now(timezone.utc), "source": "x",
        "category": "world", "tags": [],
    }
    with patch.object(public_sources, "fetch_reddit_trending", return_value=[fake_item("https://e.test/a")]):
        with patch.object(public_sources, "fetch_hackernews_top", return_value=[fake_item("https://e.test/a/")]):
            with patch.object(public_sources, "fetch_wikipedia_current_events", return_value=[fake_item("https://e.test/b")]):
                merged = public_sources.fetch_all_public_sources()

    links = [m["link"] for m in merged]
    # /a and /a/ collapse to one; /b stays.
    assert sorted(links) == sorted(["https://e.test/a", "https://e.test/b"])
