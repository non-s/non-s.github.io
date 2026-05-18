"""Tests for the category-inference helper used by youtube_analytics.py.

Lives in `utils/categorise.py` so the unit tests don't need to import
the google-api client stack.
"""
from __future__ import annotations

from utils.categorise import infer_category_from_title


def test_infer_category_picks_ai_for_llm_titles():
    assert infer_category_from_title("OpenAI launches GPT-5 — what changed?") == "ai"
    assert infer_category_from_title("Why machine learning broke this benchmark") == "ai"


def test_infer_category_picks_world_for_geopolitics():
    assert infer_category_from_title("Ukraine launches new drone offensive") == "world"
    assert infer_category_from_title("China shifts trade policy with Europe") == "world"


def test_infer_category_handles_unknown():
    assert infer_category_from_title("Mysterious headline about nothing specific") is None


def test_infer_category_handles_empty():
    assert infer_category_from_title("") is None
    assert infer_category_from_title(None) is None


def test_infer_category_picks_business():
    assert infer_category_from_title("Fed cuts rates — market reacts") == "business"
    assert infer_category_from_title("Major IPO debuts on NYSE") == "business"


def test_infer_category_picks_health():
    assert infer_category_from_title("New COVID variant detected") == "health"


def test_infer_category_picks_environment():
    assert infer_category_from_title("Climate emissions hit new high") == "environment"


def test_infer_category_picks_security():
    assert infer_category_from_title("Massive ransomware attack on hospital") == "security"


def test_infer_category_picks_sports():
    assert infer_category_from_title("NFL playoff bracket finalised") == "sports"


def test_infer_category_picks_entertainment():
    assert infer_category_from_title("Netflix announces new film slate") == "entertainment"
