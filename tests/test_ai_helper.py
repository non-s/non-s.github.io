"""Tests for utils/ai_helper.py — pure functions only (no live API calls)."""
import pytest

from utils.ai_helper import quality_check


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
        "WHY CATS PURR SO LOUD ALL THE TIME EVERY NIGHT",
        "A description that is otherwise long enough to clear the limit",
    )
    assert ok is False
    assert "ALL CAPS" in reason
