"""Tests for utils/text.py."""

from utils.text import humanize_for_tts, sanitize_text, slugify


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_accents():
    assert slugify("Cafe au lait") == "cafe-au-lait"


def test_slugify_special_chars():
    assert slugify("Cat Facts: 2025!") == "cat-facts-2025"


def test_slugify_max_length():
    assert len(slugify("a" * 200)) <= 80


def test_slugify_multiple_dashes():
    assert "--" not in slugify("hello   world")


def test_slugify_empty():
    assert slugify("") == ""


def test_sanitize_removes_newlines():
    assert "\n" not in sanitize_text("hello\nworld")
    assert "\r" not in sanitize_text("hello\rworld")


def test_sanitize_replaces_double_quotes():
    assert '"' not in sanitize_text('He said "hello"')


def test_sanitize_strips():
    assert sanitize_text("  hello  ") == "hello"


def test_sanitize_empty():
    assert sanitize_text("") == ""
    assert sanitize_text(None) == ""  # type: ignore[arg-type]


def test_humanize_strips_markdown_emphasis():
    assert humanize_for_tts("***bold-italic***") == "bold-italic"
    assert humanize_for_tts("__bold__ and _italic_") == "bold and italic"


def test_humanize_keeps_link_text_and_drops_images():
    assert humanize_for_tts("See [the owl](https://example.com)") == "See the owl"
    assert humanize_for_tts("Caption ![owl](pic.jpg) here") == "Caption here"


def test_humanize_strips_markup():
    assert humanize_for_tts("# Owl Fact\n\n<p>Owls fly <strong>silently</strong></p>") == "Owl Fact Owls fly silently"


def test_humanize_decodes_entities():
    assert humanize_for_tts("Cats &amp; dogs") == "Cats and dogs"


def test_humanize_collapses_whitespace():
    assert humanize_for_tts("a\n\n\nb   c") == "a b c"


def test_humanize_real_world_asterisk_bug():
    src = "**Watch this:** The octopus is **very** adaptable."
    assert humanize_for_tts(src) == "Watch this: The octopus is very adaptable."


def test_humanize_empty_inputs():
    assert humanize_for_tts("") == ""
    assert humanize_for_tts(None) == ""  # type: ignore[arg-type]


def test_humanize_expands_abbreviations():
    assert humanize_for_tts("The U.S. and U.K. protect habitats") == "The U S and U K protect habitats"
    assert humanize_for_tts("Dr. Smith studied owls") == "Doctor Smith studied owls"


def test_humanize_expands_values():
    assert humanize_for_tts("The colony grew 3.5% last quarter") == "The colony grew 3.5 percent last quarter"
    assert (
        humanize_for_tts("The habitat project is worth $50 million")
        == "The habitat project is worth 50 million dollars"
    )


def test_humanize_expands_ampersand():
    assert humanize_for_tts("Cats & dogs") == "Cats and dogs"


def test_humanize_expands_corporation():
    assert (
        humanize_for_tts("Wild Brief Inc. partnered with Habitat Corp.")
        == "Wild Brief Incorporated partnered with Habitat Corporation"
    )
