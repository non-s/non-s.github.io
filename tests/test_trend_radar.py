"""Tests for public nature-science trend radar."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from utils import trend_radar

RSS = """<?xml version="1.0"?>
<rss><channel>
  <item><title>Rare orca behavior caught on camera</title><link>https://example.com/orca</link><description>Scientists study viral orca behavior near boats.</description></item>
  <item><title>Cat rescue video goes viral</title><link>https://example.com/cat</link><description>A kitten rescue is trending online.</description></item>
</channel></rss>
"""


def test_score_trends_extracts_animal_topics():
    payload = trend_radar.score_trends(
        [
            {
                "title": "Rare orca behavior caught on camera",
                "url": "u",
                "source": "s",
                "text": "Rare orca behavior caught on camera scientists study viral orca behavior",
            },
            {"title": "Cat rescue video goes viral", "url": "c", "source": "s", "text": "Cat rescue video goes viral"},
        ]
    )
    assert payload["summary"]["animal_topics"] == 2
    assert payload["topics"][0]["trend_score"] >= payload["topics"][1]["trend_score"]
    assert "trend_safety" in payload["topics"][0]
    assert payload["category_scores"]["ocean"] > 0


def test_score_trends_extracts_science_topics():
    payload = trend_radar.score_trends(
        [
            {
                "title": ("NA" + "SA" + " solar flare footage shows plasma loops"),
                "url": "u",
                "source": "s",
                "text": ("NA" + "SA" + " solar flare footage shows plasma loops in a new science video"),
            },
            {
                "title": "Chemistry reaction experiment caught on camera",
                "url": "c",
                "source": "s",
                "text": "Chemistry reaction experiment footage shows crystals forming in the lab",
            },
        ]
    )

    categories = {item["category"] for item in payload["topics"]}
    assert {"space", "chemistry"}.issubset(categories)
    assert all("science footage" in item["query"] for item in payload["topics"])


def test_fetch_public_items_reads_rss(monkeypatch):
    response = MagicMock(status_code=200, text=RSS)
    monkeypatch.setattr(trend_radar.requests.Session, "get", lambda self, url, timeout: response)
    items = trend_radar.fetch_public_items(["orca"], feeds=("https://example.test?q={query}",))
    assert len(items) == 2
    assert items[0]["title"].startswith("Rare orca")


def test_load_trends_and_category_helpers(tmp_path):
    path = tmp_path / "trend.json"
    path.write_text(
        json.dumps(
            {"topics": [{"category": "ocean", "animal": "orca", "trend_score": 82, "query": "orca animal behavior"}]}
        ),
        encoding="utf-8",
    )
    payload = trend_radar.load_trends(path)
    assert trend_radar.trend_queries_for_category("ocean", payload) == ["orca animal behavior"]
    assert trend_radar.trend_weight_for_category("ocean", payload) == 1.45
    assert trend_radar.trend_weight_for_category("cats", payload) == 1.0


def test_trend_context_picks_best_category_topic():
    payload = {
        "topics": [
            {
                "category": "dogs",
                "animal": "dog",
                "trend_score": 40,
                "mentions": 1,
                "terms": ["rescue"],
                "top_titles": ["Low dog item"],
                "top_urls": ["https://example.com/low"],
                "query": "dog animal rescue",
            },
            {
                "category": "dogs",
                "animal": "dog",
                "trend_score": 90,
                "mentions": 5,
                "terms": ["viral", "rescue"],
                "top_titles": ["Viral dog rescue"],
                "top_urls": ["https://example.com/high"],
                "query": "dog animal viral rescue",
            },
        ]
    }
    ctx = trend_radar.trend_context_for_category("dogs", payload)
    assert ctx["trend_score"] == 90
    assert ctx["mentions"] == 5
    assert ctx["headline"] == "Viral dog rescue"
    assert ctx["query"] == "dog animal viral rescue"


def test_animal_classifier_avoids_media_name_false_positives():
    payload = trend_radar.score_trends(
        [
            {
                "title": "Animal shelter trending in right direction - FOX 2",
                "text": "Animal shelter trending in right direction FOX 2 news",
            },
            {
                "title": "Rare mammal sighting - Outdoors with Bear Grylls",
                "text": "Rare mammal sighting Outdoors with Bear Grylls",
            },
            {"title": "Sea lion surprises beach visitors", "text": "Viral sea lion video surprises beach visitors"},
        ]
    )
    assert payload["summary"]["animal_topics"] == 1
    assert payload["topics"][0]["animal"] == "sea lion"
