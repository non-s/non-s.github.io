"""Unit tests for utils/digest.py — the shared editorial-digest helpers."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from utils.digest import (
    AUTO_POST_SLUG_MARKERS,
    base_score,
    build_post_url,
    cited_posts_yaml,
    first_image,
    load_posts_in_window,
    parse_post_date,
)


def _write_post(d: Path, name: str, fm_extra: dict | None = None) -> Path:
    """Write a minimal post; `name` is the filename without `.md`."""
    fm_extra = fm_extra or {}
    lines = ["---", 'title: "T"']
    for k, v in fm_extra.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            lines.append(f'{k}: "{v}"')
    lines.append("---\n\nBody.\n")
    p = d / f"{name}.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def test_build_post_url_round_trip():
    p = Path("_posts/2026-05-15-some-slug.md")
    fm = {"categories": ["world"]}
    assert build_post_url(p, fm) == "/world/2026/05/15/some-slug/"


def test_build_post_url_defaults_to_news():
    p = Path("_posts/2026-05-15-some-slug.md")
    assert build_post_url(p, {}) == "/news/2026/05/15/some-slug/"


def test_parse_post_date():
    assert parse_post_date(Path("_posts/2026-05-15-foo.md")) == date(2026, 5, 15)
    assert parse_post_date(Path("_posts/not-a-date.md")) is None
    assert parse_post_date(Path("_posts/2026-13-99-foo.md")) is None


def test_base_score_components_add_up():
    plain = base_score({})
    breaking = base_score({"breaking": "true"})
    featured = base_score({"featured": "true"})
    verified = base_score({"fact_check": "verified"})
    full = base_score({
        "breaking": "true", "featured": "true", "fact_check": "verified",
        "tl_dr": "x", "description": "y" * 81, "image": "img"
    })

    assert plain == 0
    assert breaking == 50
    assert featured == 30
    assert verified == 10
    assert full == 50 + 30 + 10 + 5 + 5 + 3


def test_load_posts_filters_window_and_skip(tmp_path):
    d = tmp_path / "_posts"
    d.mkdir()
    _write_post(d, "2026-05-15-real-news", {"categories": ["world"]})
    _write_post(d, "2026-05-15-daily-briefing", {"categories": ["briefing"]})
    _write_post(d, "2026-05-15-monthly-roundup", {"categories": ["roundup"]})
    _write_post(d, "2026-04-30-too-old", {"categories": ["world"]})
    _write_post(d, "2026-05-15-fine", {"categories": ["technology"]})

    items = load_posts_in_window(
        d, date(2026, 5, 1), date(2026, 5, 15), AUTO_POST_SLUG_MARKERS
    )
    names = sorted(p.name for p, _, _ in items)
    assert names == ["2026-05-15-fine.md", "2026-05-15-real-news.md"]


def test_first_image_returns_first_non_empty(tmp_path):
    d = tmp_path / "_posts"
    d.mkdir()
    p1 = _write_post(d, "2026-05-15-noimg", {})
    p2 = _write_post(d, "2026-05-14-yes", {"image": "/x.jpg"})
    p3 = _write_post(d, "2026-05-13-also-yes", {"image": "/y.jpg"})
    items = [(p1, {"image": ""}), (p2, {"image": "/x.jpg"}), (p3, {"image": "/y.jpg"})]
    assert first_image(items) == "/x.jpg"


def test_first_image_handles_empty_list():
    assert first_image([]) == ""


def test_cited_posts_yaml_filters_invalid():
    items = [
        (Path("_posts/2026-05-15-good.md"), {"categories": ["world"]}),
        (Path("_posts/broken-name.md"), {"categories": ["world"]}),
    ]
    out = cited_posts_yaml(items)
    assert "/world/2026/05/15/good/" in out
    assert "broken-name" not in out


def test_cited_posts_yaml_empty():
    # All entries have bad slugs → no cited_posts: block at all.
    items = [(Path("_posts/bad.md"), {})]
    assert cited_posts_yaml(items) == ""
