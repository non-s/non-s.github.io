"""Test the word-boundary truncation helper for search-index.json."""
from generate_search_index import _truncate, parse_post


def test_truncate_short_passthrough():
    assert _truncate("short text", 100) == "short text"


def test_truncate_long_breaks_at_word():
    text = "The quick brown fox jumps over the lazy dog"
    out = _truncate(text, 20)
    assert out.endswith("…")
    # Should not break mid-word — last char before … must be a letter
    # not a space.
    assert not out[-2].isspace()
    assert len(out) <= 21


def test_truncate_handles_no_space_before_limit():
    # Long word with no space — fall back to hard cut + ellipsis.
    text = "a" * 100
    out = _truncate(text, 50)
    assert out.endswith("…")
    assert len(out) <= 51


def test_parse_post_returns_compact_payload(tmp_path):
    p = tmp_path / "2026-05-15-hello-world.md"
    p.write_text(
        "---\n"
        'title: "Hello World"\n'
        "date: 2026-05-15 10:00:00 +0000\n"
        "categories: [world]\n"
        'description: "Short description here."\n'
        'image: "/x.webp"\n'
        "tags: [hello, world, news, breaking, abc, def, ghi, jkl, mno, pqr]\n"
        "---\n\n"
        "Body paragraph one. Body paragraph two.\n",
        encoding="utf-8",
    )
    item = parse_post(p)
    assert item is not None
    assert item["title"] == "Hello World"
    assert item["category"] == "world"
    assert item["url"] == "/world/2026/05/15/hello-world/"
    # Tags capped at 8.
    assert len(item["tags"]) == 8
    # excerpt and description are length-bounded.
    assert len(item["description"]) <= 161
    assert len(item["excerpt"]) <= 241
    # author field is gone (removed in the slim payload).
    assert "author" not in item
