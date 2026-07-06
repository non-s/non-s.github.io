"""Tests for fetch-time subject supply diversity."""

from __future__ import annotations

import json

import fetch_animals
from utils import channel_memory


def test_supply_blocks_subject_in_publish_cooldown():
    terms = fetch_animals._animal_terms("lion resting in the savanna")
    assert terms, "lion should resolve to a canonical animal subject"
    reason = fetch_animals._subject_supply_block_reason(terms, {"lion"}, [], 2)
    assert reason == "publish_cooldown"


def test_supply_blocks_subject_saturating_the_queue():
    terms = fetch_animals._animal_terms("octopus hiding in the reef")
    assert terms, "octopus should resolve to a canonical animal subject"
    pending = [{"octopus"}, {"octopus"}]
    reason = fetch_animals._subject_supply_block_reason(terms, set(), pending, 2)
    assert reason == "queue_saturated"


def test_supply_allows_fresh_subject():
    terms = fetch_animals._animal_terms("octopus hiding in the reef")
    reason = fetch_animals._subject_supply_block_reason(terms, {"lion"}, [{"lion"}], 2)
    assert reason == ""


def test_supply_never_blocks_subject_without_animal_terms():
    reason = fetch_animals._subject_supply_block_reason(set(), {"lion"}, [{"lion"}], 0)
    assert reason == ""


def test_recent_publish_animal_terms_uses_channel_memory(monkeypatch):
    monkeypatch.setattr(fetch_animals, "recent_publish_texts", lambda days: ["lion savanna chase"])
    assert "lion" in fetch_animals._recent_publish_animal_terms()


def test_recent_publish_texts_reads_memory_log(tmp_path):
    import time

    log = tmp_path / "memory.jsonl"
    log.write_text(
        json.dumps({"ts": time.time(), "subject": "lion", "entities": ["savanna"]}) + "\n",
        encoding="utf-8",
    )
    texts = channel_memory.recent_publish_texts(days=3, path=log)
    assert texts == ["lion savanna"]


def test_pending_subject_term_sets_skip_consumed_stories():
    stories = [
        {"title": "lion in savanna", "script": "the lion waits", "consumed": False},
        {"title": "octopus in reef", "script": "the octopus hides", "consumed": True},
    ]
    sets = fetch_animals._pending_subject_term_sets(stories)
    assert sets == [{"lion"}]
