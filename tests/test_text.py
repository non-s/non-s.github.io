"""Tests for utils/text.py"""
import pytest
from utils.text import slugify, sanitize_text


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_accents():
    assert slugify("Café au lait") == "cafe-au-lait"


def test_slugify_special_chars():
    assert slugify("AI & Tech: 2025!") == "ai-tech-2025"


def test_slugify_max_length():
    long = "a" * 200
    assert len(slugify(long)) <= 80


def test_slugify_multiple_dashes():
    assert "--" not in slugify("hello   world")


def test_slugify_empty():
    assert slugify("") == ""


def test_sanitize_removes_newlines():
    assert "\n" not in sanitize_text("hello\nworld")
    assert "\r" not in sanitize_text("hello\rworld")


def test_sanitize_replaces_double_quotes():
    result = sanitize_text('He said "hello"')
    assert '"' not in result


def test_sanitize_strips():
    assert sanitize_text("  hello  ") == "hello"


def test_sanitize_empty():
    assert sanitize_text("") == ""
    assert sanitize_text(None) == ""  # type: ignore[arg-type]
