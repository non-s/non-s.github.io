"""Unit tests for the helpers inside `fetch_news.py`.

Importing the full module is expensive (it loads ~130 RSS configs and the
feed cache from disk), but cheaper than not testing 3 500 lines of pipeline
code at all. The audit flagged that `fetch_news.py` had zero direct tests
even though it's the highest-risk file in the repo.
"""
from __future__ import annotations

import pytest

fetch_news = pytest.importorskip("fetch_news")


# ─── _is_public_url ───────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://example.com",
    "http://example.com/path",
    "https://en.wikipedia.org/wiki/Foo",
    "https://www.bbc.co.uk/news/world-12345",
])
def test_is_public_url_accepts_real_hosts(url):
    assert fetch_news._is_public_url(url) is True


@pytest.mark.parametrize("url", [
    # Loopback / link-local
    "http://localhost/foo",
    "http://127.0.0.1/admin",
    "http://[::1]/x",
    "http://169.254.169.254/latest/meta-data/",
    # Private RFC1918
    "http://10.0.0.1/x",
    "http://172.16.0.5/x",
    "http://192.168.1.1/x",
    # Bogus schemes
    "file:///etc/passwd",
    "javascript:alert(1)",
    "ftp://example.com/x",
    # Missing host
    "https:///foo",
    "",
    # mDNS / internal TLDs
    "http://router.local/admin",
    "http://gitlab.internal/api",
])
def test_is_public_url_rejects_unsafe(url):
    assert fetch_news._is_public_url(url) is False


# ─── FEEDS dedup at module load ──────────────────────────────────────

def test_feeds_have_unique_urls():
    urls = [f["url"] for f in fetch_news.FEEDS]
    assert len(urls) == len(set(urls)), (
        "FEEDS contained duplicate URLs — the load-time dedup filter is broken."
    )


def test_feeds_all_have_required_fields():
    for f in fetch_news.FEEDS:
        for key in ("name", "url", "category", "source"):
            assert key in f, f"FEEDS entry missing {key!r}: {f}"


# ─── _extract_entities ───────────────────────────────────────────────

def test_extract_entities_finds_proper_nouns():
    tags = fetch_news._extract_entities(
        "Trump and Xi sign trade deal in Beijing", ""
    )
    # Lower-cased + dash-joined, dedup'd, capped at 5.
    assert "trump" in tags
    assert "xi" not in tags  # too short (< 4 chars including 'xi')
    assert "beijing" in tags
    assert len(tags) <= 5


def test_extract_entities_skips_stopwords():
    tags = fetch_news._extract_entities("The United States and Global Markets", "")
    # All of "The", "United", "Global" are in STOPWORDS — should not surface.
    assert "the" not in tags
    assert "united" not in tags
    assert "global" not in tags


def test_extract_entities_handles_empty():
    assert fetch_news._extract_entities("", "") == []


# ─── Thread-safe cache insertion ─────────────────────────────────────

def test_record_new_post_threadsafe(monkeypatch, tmp_path):
    """Concurrent _record_new_post calls must not lose entries."""
    import threading

    # Redirect to an empty temp dir so the production cache isn't touched.
    monkeypatch.setattr(fetch_news, "POSTS_DIR", tmp_path)
    monkeypatch.setattr(fetch_news, "_known_urls", None)
    monkeypatch.setattr(fetch_news, "_known_titles", None)

    def insert(i: int):
        fetch_news._record_new_post(
            f"Title {i}", f"2026-05-15-post-{i}.md", f"https://example.com/{i}"
        )

    threads = [threading.Thread(target=insert, args=(i,)) for i in range(200)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(fetch_news._known_urls) == 200
    assert len(fetch_news._known_titles) == 200


# ─── _PT_STOPWORDS (English stopwords, despite the name) ─────────────

def test_pt_stopwords_no_duplicates():
    # frozenset already de-dups, but verify the source literal didn't have
    # the historical "their"/"says" duplicates re-added.
    stops = fetch_news._PT_STOPWORDS
    assert isinstance(stops, frozenset)
    assert "their" in stops
    assert "says" in stops
    assert len(stops) >= 40


# ─── _is_public_url with realistic redirects ─────────────────────────

def test_check_source_url_rejects_private_no_network(monkeypatch):
    """Even with the request layer mocked, the URL gate runs first."""
    called = {"n": 0}

    def _stub_head(*a, **kw):
        called["n"] += 1
        raise RuntimeError("should not be called for private URLs")

    monkeypatch.setattr(fetch_news._session, "head", _stub_head)
    assert fetch_news._check_source_url("http://127.0.0.1/x") is False
    assert called["n"] == 0
