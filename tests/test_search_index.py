"""Tests for generate_search_index.py — pure helpers."""
from generate_search_index import strip_markdown


def test_strip_code_fence():
    assert "print" not in strip_markdown("```python\nprint('x')\n```\nrest")
    assert "rest" in strip_markdown("```python\nprint('x')\n```\nrest")


def test_strip_inline_code():
    assert "code" not in strip_markdown("Here is `code` and more text")


def test_strip_images():
    assert "alt" not in strip_markdown("![alt text](https://x.test/a.jpg)")


def test_keep_link_text():
    out = strip_markdown("See [this article](https://x.test) for more")
    assert "this article" in out
    assert "https://x.test" not in out


def test_strip_headings():
    assert strip_markdown("# Heading\n\nbody").startswith("Heading")


def test_strip_bold():
    assert "important" in strip_markdown("**important**")
    assert "*" not in strip_markdown("**important**")


def test_strip_html_tag():
    assert "<" not in strip_markdown("<p>hello</p>")


def test_collapses_whitespace():
    assert "  " not in strip_markdown("a\n\n\n  b\t\tc")
