"""Tests for utils/ai_helper.py — pure functions only (no live API calls)."""
import pytest

from utils.ai_helper import (
    sentiment_score,
    fact_check_score,
    is_breaking_news,
    quality_check,
)


def test_sentiment_positive():
    assert sentiment_score("Scientists discover breakthrough cure for rare disease") == "positive"


def test_sentiment_negative():
    assert sentiment_score("War, attack, deaths and disaster strike region") == "negative"


def test_sentiment_neutral():
    assert sentiment_score("The committee met to discuss the agenda") == "neutral"


def test_sentiment_empty():
    assert sentiment_score("") == "neutral"


def test_fact_check_verified():
    assert fact_check_score("Officials confirmed", "Data shows record growth") == "verified"


def test_fact_check_developing():
    assert fact_check_score("Sources say", "Reportedly an investigation is underway") == "developing"


def test_fact_check_opinion():
    assert fact_check_score("Why we believe", "It is time to act, in this opinion column") == "opinion"


def test_fact_check_satire():
    assert fact_check_score("Onion satire", "A spoof of the day's news") == "satire"


def test_fact_check_none():
    assert fact_check_score("Plain headline", "Plain description") is None


def test_fact_check_satire_beats_others():
    # Satire should win even when other phrases are present.
    assert fact_check_score(
        "Satirical opinion piece",
        "Reportedly an opinion-flavored editorial",
    ) == "satire"


def test_is_breaking_keyword_match():
    assert is_breaking_news("BREAKING: market crash hits investors")


def test_is_breaking_in_description():
    assert is_breaking_news("Some title", "Urgent alert from authorities")


def test_is_breaking_no_match():
    assert not is_breaking_news("Tomorrow's weather forecast", "Mild and sunny")


def test_quality_check_ok():
    ok, reason = quality_check(
        "A reasonably-detailed headline about something",
        "A short description that has enough characters to clear the limit.",
    )
    assert ok is True
    assert reason == ""


def test_quality_check_short_title():
    ok, reason = quality_check("Tiny", "x" * 100)
    assert ok is False
    assert "title too short" in reason


def test_quality_check_short_desc():
    ok, reason = quality_check("A reasonable headline length here", "short")
    assert ok is False
    assert "description too short" in reason


def test_quality_check_spam():
    ok, reason = quality_check(
        "Click here for amazing results you won't believe",
        "A description that is otherwise long enough but spam word in title",
    )
    assert ok is False
    assert "spam" in reason


def test_quality_check_all_caps():
    ok, reason = quality_check(
        "BREAKING NEWS WORLD EVENT MAJOR ALERT NOW",
        "A description that is otherwise long enough to clear the limit",
    )
    assert ok is False
    assert "ALL CAPS" in reason
