"""Testes para scripts/generate_site.py — site estatico SEO (schema.org)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import scripts.generate_site as site


def _seed(tmp_path, monkeypatch, video_tags, analytics):
    monkeypatch.setattr(site, "data_dir", lambda: tmp_path)
    (tmp_path / "video_tags.json").write_text(json.dumps(video_tags), encoding="utf-8")
    (tmp_path / "analytics.json").write_text(json.dumps(analytics), encoding="utf-8")


def _load_both(tmp_path):
    tags = json.loads((tmp_path / "video_tags.json").read_text(encoding="utf-8"))
    analytics = json.loads((tmp_path / "analytics.json").read_text(encoding="utf-8"))
    return tags, analytics


def _entry(**overrides):
    base = {
        "video_id": "v1",
        "title": "T",
        "description": "D",
        "published_at": "2026-07-01",
        "views": 10,
        "likes": 1,
        "thumbnail": "https://t",
        "watch_url": "https://w",
    }
    base.update(overrides)
    return base


class TestBuildVideoEntries:
    def test_merges_tags_and_analytics(self, tmp_path, monkeypatch):
        video_tags = {"v1": {"scene": "cat", "description": "Cute cat napping."}}
        analytics = {
            "all_videos": [
                {
                    "video_id": "v1",
                    "title": "Cute Cat & Jazz",
                    "views": 100,
                    "likes": 5,
                    "published_at": "2026-07-01T00:00:00Z",
                }
            ]
        }
        _seed(tmp_path, monkeypatch, video_tags, analytics)

        tags, an = _load_both(tmp_path)
        entries = site._build_video_entries(tags, an)
        assert len(entries) == 1
        e = entries[0]
        assert e["video_id"] == "v1"
        assert e["title"] == "Cute Cat & Jazz"
        assert e["views"] == 100
        assert e["scene"] == "cat"
        assert "img.youtube.com" in e["thumbnail"]
        assert "youtu.be/v1" in e["watch_url"]

    def test_video_only_in_analytics_still_listed(self, tmp_path, monkeypatch):
        video_tags = {"v1": {"scene": "cat"}}
        analytics = {
            "all_videos": [
                {"video_id": "v1", "title": "t1", "views": 1},
                {"video_id": "v2", "title": "t2", "views": 999},
            ]
        }
        _seed(tmp_path, monkeypatch, video_tags, analytics)
        tags, an = _load_both(tmp_path)
        entries = site._build_video_entries(tags, an)
        ids = {e["video_id"] for e in entries}
        assert ids == {"v1", "v2"}

    def test_entries_sorted_by_views_desc(self, tmp_path, monkeypatch):
        video_tags = {"a": {"scene": "cat"}, "b": {"scene": "dog"}}
        analytics = {
            "all_videos": [
                {"video_id": "a", "title": "a", "views": 10},
                {"video_id": "b", "title": "b", "views": 500},
            ]
        }
        _seed(tmp_path, monkeypatch, video_tags, analytics)
        tags, an = _load_both(tmp_path)
        entries = site._build_video_entries(tags, an)
        assert [e["video_id"] for e in entries] == ["b", "a"]

    def test_empty_inputs_returns_empty_list(self):
        assert site._build_video_entries({}, {"all_videos": []}) == []
        assert site._build_video_entries({}, {}) == []


class TestVideoObjectLd:
    def test_contains_required_fields(self):
        ld = site._video_object_ld(_entry())
        assert "VideoObject" in ld
        assert "schema.org" in ld
        assert "T" in ld
        assert "2026-07-01" in ld
        assert "InteractionCounter" in ld
        assert "WatchAction" in ld

    def test_without_views_omits_interaction_statistic(self):
        ld = site._video_object_ld(_entry(views=0, likes=0))
        assert "InteractionCounter" not in ld


class TestYoutubeFeedFallback:
    def test_parses_public_feed_entry(self, monkeypatch):
        monkeypatch.setattr(site, "_FEED_URL", "https://www.youtube.com/feeds/videos.xml?channel_id=UC123")
        xml = b'''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015"
              xmlns:media="http://search.yahoo.com/mrss/">
          <entry>
            <yt:videoId>abc123</yt:videoId><title>Cozy Cat Jazz</title>
            <published>2026-08-11T00:00:00+00:00</published>
            <link rel="alternate" href="https://www.youtube.com/shorts/abc123"/>
            <media:group><media:thumbnail url="https://img.example/abc.jpg"/></media:group>
          </entry>
        </feed>'''
        response = MagicMock()
        response.read.return_value = xml
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with patch("scripts.generate_site.urlopen", return_value=response):
            entries = site._youtube_feed_entries()

        assert entries == [
            {
                "video_id": "abc123",
                "title": "Cozy Cat Jazz",
                "description": "A Liquid Wire generative art moment with original procedural music.",
                "published_at": "2026-08-11T00:00:00+00:00",
                "views": 0,
                "likes": 0,
                "thumbnail": "https://img.example/abc.jpg",
                "watch_url": "https://www.youtube.com/shorts/abc123",
                "scene": "",
            }
        ]

    def test_feed_failure_returns_empty_list(self, monkeypatch):
        monkeypatch.setattr(site, "_FEED_URL", "https://www.youtube.com/feeds/videos.xml?channel_id=UC123")
        with patch("scripts.generate_site.urlopen", side_effect=OSError("offline")):
            assert site._youtube_feed_entries() == []


class TestRenderVideoPage:
    def test_includes_ld_json_script(self):
        html = site._render_video_page(_entry(title="Cute Cat", views=100))
        assert '<script type="application/ld+json">' in html
        assert "VideoObject" in html
        assert "Cute Cat" in html
        assert "https://w" in html

    def test_escapes_title(self):
        html = site._render_video_page(_entry(title="<script>alert(1)</script>", views=0, likes=0))
        assert "<script>alert(1)</script>" not in html.split("application/ld+json")[0]

    def test_includes_canonical_and_social_metadata(self):
        html = site._render_video_page(_entry(video_id="abc", title="Cute Cat"))
        assert 'rel="canonical" href="https://non-s.github.io/video_abc.html"' in html
        assert 'property="og:type" content="video.other"' in html
        assert 'name="twitter:card" content="summary_large_image"' in html


class TestRenderIndex:
    def test_includes_video_cards(self):
        entries = [
            _entry(video_id="v1", title="T1", views=100, thumbnail="https://t1", watch_url="https://w1"),
            _entry(video_id="v2", title="T2", views=50, likes=0, thumbnail="https://t2", watch_url="https://w2"),
        ]
        html = site._render_index(entries)
        assert "video_v1.html" in html
        assert "video_v2.html" in html
        assert "T1" in html
        assert "T2" in html

    def test_includes_item_list_ld_json(self):
        html = site._render_index([])
        assert '<script type="application/ld+json">' in html
        assert "ItemList" in html

    def test_empty_index_still_valid(self):
        html = site._render_index([])
        assert html.startswith("<!doctype html>")
        assert "</html>" in html
        assert "https://www.youtube.com/@LiquidWireStudio" in html
        assert "Fresh Liquid Wire videos are being indexed" in html

    def test_includes_canonical_and_social_metadata(self):
        html = site._render_index([])
        assert 'rel="canonical" href="https://non-s.github.io/"' in html
        assert 'property="og:type" content="website"' in html


class TestGenerateSite:
    def test_generates_index_and_video_pages(self, tmp_path, monkeypatch):
        video_tags = {"v1": {"scene": "cat", "description": "Cute cat."}}
        analytics = {
            "all_videos": [
                {
                    "video_id": "v1",
                    "title": "Cat Jazz",
                    "views": 10,
                    "likes": 1,
                    "published_at": "2026-07-01T00:00:00Z",
                }
            ]
        }
        _seed(tmp_path, monkeypatch, video_tags, analytics)

        index_path = site.generate_site()
        assert index_path.exists()
        index_html = index_path.read_text(encoding="utf-8")
        assert "Cat Jazz" in index_html

        video_page = index_path.parent / "video_v1.html"
        assert video_page.exists()
        page_html = video_page.read_text(encoding="utf-8")
        assert "VideoObject" in page_html
        assert "Cat Jazz" in page_html
        assert (index_path.parent / "sitemap.xml").read_text(encoding="utf-8").count("<loc>") == 2
        assert "Sitemap: https://non-s.github.io/sitemap.xml" in (index_path.parent / "robots.txt").read_text(
            encoding="utf-8"
        )

    def test_empty_data_generates_minimal_site(self, tmp_path, monkeypatch):
        _seed(tmp_path, monkeypatch, {}, {"all_videos": []})
        index_path = site.generate_site()
        assert index_path.exists()
        html = index_path.read_text(encoding="utf-8")
        assert html.startswith("<!doctype html>")

    def test_missing_files_generates_minimal_site(self, tmp_path, monkeypatch):
        monkeypatch.setattr(site, "data_dir", lambda: tmp_path)
        index_path = site.generate_site(tmp_path / "_site")
        assert index_path.exists()


class TestMain:
    def test_main_writes_site(self, tmp_path, monkeypatch):
        _seed(
            tmp_path,
            monkeypatch,
            {"v1": {"scene": "cat"}},
            {"all_videos": [{"video_id": "v1", "title": "t", "views": 1}]},
        )
        monkeypatch.setattr(site, "ROOT", tmp_path)
        assert site.main() == 0
        assert (tmp_path / "_site" / "index.html").exists()
