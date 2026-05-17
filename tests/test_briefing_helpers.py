"""Tests for the shared utils/digest.py helpers.

These were previously inline in create_daily_briefing.py; the test still
exercises the same behaviour now that they live in utils/digest.
"""
from pathlib import Path

from utils.digest import base_score, build_post_url


def test_score_breaking_beats_normal():
    breaking = {"breaking": "true"}
    normal   = {}
    assert base_score(breaking) > base_score(normal)


def test_score_featured_and_fact_check():
    plain = {}
    enriched = {"featured": "true", "fact_check": "verified", "tl_dr": "x", "description": "y" * 90, "image": "img"}
    assert base_score(enriched) > base_score(plain) + 40


def test_build_post_url_basic():
    p = Path("_posts/2026-05-15-some-slug.md")
    fm = {"categories": ["world"]}
    assert build_post_url(p, fm) == "/world/2026/05/15/some-slug/"


def test_build_post_url_no_category():
    p = Path("_posts/2026-05-15-some-slug.md")
    fm = {}
    assert build_post_url(p, fm) == "/news/2026/05/15/some-slug/"


def test_build_post_url_bad_stem():
    p = Path("_posts/random-name.md")
    assert build_post_url(p, {}) == ""
