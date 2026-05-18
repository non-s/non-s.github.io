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
                with patch.object(public_sources, "fetch_google_trends", return_value=[]):
                    with patch.object(public_sources, "fetch_gdelt_recent", return_value=[]):
                        merged = public_sources.fetch_all_public_sources()

    links = [m["link"] for m in merged]
    # /a and /a/ collapse to one; /b stays.
    assert sorted(links) == sorted(["https://e.test/a", "https://e.test/b"])


# ── Google Trends ────────────────────────────────────────────────

_TRENDS_XML_SAMPLE = """
<?xml version="1.0" encoding="UTF-8"?>
<rss>
  <channel>
    <item>
      <title>Federal Reserve</title>
      <ht:approx_traffic>500,000+</ht:approx_traffic>
      <ht:news_item>
        <ht:news_item_title><![CDATA[Fed cuts rates after key meeting]]></ht:news_item_title>
        <ht:news_item_snippet><![CDATA[Powell says inflation is cooling.]]></ht:news_item_snippet>
        <ht:news_item_url>https://news.example.com/fed-cuts</ht:news_item_url>
        <ht:news_item_picture>https://img.example.com/fed.jpg</ht:news_item_picture>
      </ht:news_item>
    </item>
    <item>
      <title>x</title>
      <ht:news_item>
        <ht:news_item_title><![CDATA[Short title]]></ht:news_item_title>
        <ht:news_item_url>https://news.example.com/short</ht:news_item_url>
      </ht:news_item>
    </item>
  </channel>
</rss>
""".strip()


def test_google_trends_parses_rss_and_extracts_news_links():
    from utils import public_sources

    fake_resp = MagicMock(status_code=200, text=_TRENDS_XML_SAMPLE)
    with patch.object(public_sources, "_session") as factory:
        s = MagicMock()
        s.get.return_value = fake_resp
        factory.return_value = s
        items = public_sources.fetch_google_trends(per_region=5)

    # Five regions × ~1 valid item each. We require trending_term presence.
    assert items, "expected at least one trending news item"
    assert any("Powell" in (i.get("description") or "") for i in items)
    assert all(i.get("trending_term") for i in items)
    assert all(i["link"].startswith("https://news.example.com") for i in items)


def test_google_trends_skips_when_news_url_missing():
    from utils import public_sources

    no_url = "<rss><channel><item><title>Term</title></item></channel></rss>"
    fake_resp = MagicMock(status_code=200, text=no_url)
    with patch.object(public_sources, "_session") as factory:
        s = MagicMock()
        s.get.return_value = fake_resp
        factory.return_value = s
        items = public_sources.fetch_google_trends(per_region=5)
    assert items == []


def test_trending_keywords_dedupes_and_tokenises():
    from utils import public_sources

    items = [
        {"trending_term": "Jerome Powell"},
        {"trending_term": "Federal Reserve rates"},
        {"trending_term": "x"},  # too short, skipped
    ]
    out = public_sources.trending_keywords(items)
    # "jerome", "powell", "federal", "reserve", "rates" all retained.
    assert "powell" in out
    assert "federal" in out
    assert "jerome powell" in out
    # The 1-char term is dropped.
    assert "x" not in out


# ── GDELT ────────────────────────────────────────────────────────

def test_gdelt_filters_short_titles_and_bad_urls():
    from utils import public_sources

    payload = {
        "articles": [
            {"url": "https://news.example.com/a", "title": "A reasonably long substantive headline",
             "domain": "news.example.com", "seendate": "20260518T120000Z"},
            {"url": "ftp://nope/", "title": "Plenty long but wrong scheme entirely"},
            {"url": "https://news.example.com/short", "title": "tiny"},
            {"url": "https://news.example.com/c", "title": "Another fully-formed headline about something significant",
             "domain": "news.example.com", "seendate": "20260518T120000Z"},
        ],
    }
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = payload

    with patch.object(public_sources, "_session") as factory:
        s = MagicMock()
        s.get.return_value = fake_resp
        factory.return_value = s
        items = public_sources.fetch_gdelt_recent(themes=("FAKE_THEME",), limit=10)

    titles = [i["title"] for i in items]
    assert any("reasonably long" in t for t in titles)
    assert not any(t == "tiny" for t in titles)
    assert not any(i["link"].startswith("ftp://") for i in items)
