"""Tests for utils/text.py"""
import time
import types
from datetime import datetime, timezone, timedelta

import pytest

from utils.text import slugify, sanitize_text, humanize_for_tts, parse_date, extract_image


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


# ── humanize_for_tts ───────────────────────────────────────────────

def test_humanize_strips_bold():
    assert humanize_for_tts("This is **important** news") == "This is important news"


def test_humanize_strips_italic():
    assert humanize_for_tts("This is *very* exciting") == "This is very exciting"


def test_humanize_strips_underscore_emphasis():
    assert humanize_for_tts("__bold__ and _italic_") == "bold and italic"


def test_humanize_strips_triple_asterisk():
    # Used to be the unreachable case for the old regex.
    assert humanize_for_tts("***bold-italic***") == "bold-italic"


def test_humanize_keeps_link_text():
    assert humanize_for_tts("See [the report](https://example.com)") == "See the report"


def test_humanize_drops_image():
    assert humanize_for_tts("Caption ![alt](pic.jpg) here") == "Caption here"


def test_humanize_strips_heading():
    assert humanize_for_tts("# Big Heading\n\nbody text") == "Big Heading body text"


def test_humanize_strips_html_tags():
    assert humanize_for_tts("<p>Hello <strong>world</strong></p>") == "Hello world"


def test_humanize_decodes_entities():
    assert humanize_for_tts("R&amp;D is &quot;ongoing&quot;") == 'R and D is "ongoing"'


def test_humanize_strips_code():
    assert humanize_for_tts("Run `git push` now") == "Run git push now"


def test_humanize_collapses_whitespace():
    assert humanize_for_tts("a\n\n\nb   c") == "a b c"


def test_humanize_real_world_asterisk_bug():
    # The actual symptom the user reported: TTS reading "asterisk asterisk".
    src = "**Breaking:** The president said this is **very** important."
    assert humanize_for_tts(src) == "Breaking: The president said this is very important."


def test_humanize_empty_inputs():
    assert humanize_for_tts("") == ""
    assert humanize_for_tts(None) == ""  # type: ignore[arg-type]


def test_humanize_expands_country_abbreviations():
    assert humanize_for_tts("The U.S. and U.K. agreed") == "The U S and U K agreed"


def test_humanize_expands_titles():
    assert humanize_for_tts("Dr. Smith said Mr. Jones agreed") == "Doctor Smith said Mister Jones agreed"


def test_humanize_expands_percent():
    assert humanize_for_tts("Inflation rose 3.5% last quarter") == "Inflation rose 3.5 percent last quarter"


def test_humanize_expands_dollars():
    assert humanize_for_tts("The deal is worth $50 million") == "The deal is worth 50 million dollars"
    assert humanize_for_tts("Stock fell to $42 today") == "Stock fell to 42 dollars today"


def test_humanize_expands_ampersand():
    assert humanize_for_tts("R & D is up at AT&T") == "R and D is up at AT&T"  # bare & between letters stays


def test_humanize_expands_corporation():
    assert humanize_for_tts("Apple Inc. acquired Foo Corp.") == "Apple Incorporated acquired Foo Corporation"


# ── parse_date with recency cap ─────────────────────────────────────

def _make_entry(date_tuple):
    e = types.SimpleNamespace()
    e.published_parsed = time.struct_time(date_tuple + (0, 0, 0))
    return e


def test_parse_date_recent_passes_through():
    e = _make_entry((2026, 5, 14, 12, 0, 0))
    # Caller can set max_age very high to verify behaviour deterministically.
    out = parse_date(e, max_age_days=100000)
    assert out.year == 2026 and out.month == 5 and out.day == 14


def test_parse_date_caps_ancient_to_now():
    """Posts re-broadcast from years ago should get TODAY's date, not 2014."""
    e = _make_entry((2014, 8, 14, 0, 0, 0))
    out = parse_date(e, max_age_days=30)
    now = datetime.now(timezone.utc)
    assert (now - out).total_seconds() < 5


def test_parse_date_caps_future_to_now():
    """Some feeds set tomorrow's date — clamp to now."""
    future = datetime.now(timezone.utc) + timedelta(days=2)
    e = _make_entry((future.year, future.month, future.day, 0, 0, 0))
    out = parse_date(e)
    assert out <= datetime.now(timezone.utc) + timedelta(seconds=2)


def test_parse_date_no_date_returns_now():
    e = types.SimpleNamespace()  # no published_parsed / updated_parsed
    out = parse_date(e)
    assert (datetime.now(timezone.utc) - out).total_seconds() < 5


# ── extract_image robustness ────────────────────────────────────────

def test_extract_image_handles_string_media_thumbnail():
    """Some Atom feeds put media_thumbnail as a list of strings, not dicts."""
    e = types.SimpleNamespace()
    e.media_thumbnail = ["https://example.com/img.jpg"]
    assert extract_image(e) == "https://example.com/img.jpg"


def test_extract_image_handles_dict_media_thumbnail():
    e = types.SimpleNamespace()
    e.media_thumbnail = [{"url": "https://example.com/y.jpg"}]
    assert extract_image(e) == "https://example.com/y.jpg"


def test_extract_image_returns_empty_when_nothing_found():
    e = types.SimpleNamespace()
    assert extract_image(e) == ""
