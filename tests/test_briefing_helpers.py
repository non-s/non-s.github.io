"""Tests for create_daily_briefing.py pure helpers (no AI call)."""
from pathlib import Path

import create_daily_briefing as cdb


def test_score_breaking_beats_normal():
    breaking = {"breaking": "true"}
    normal   = {}
    assert cdb._score(breaking) > cdb._score(normal)


def test_score_featured_and_fact_check():
    plain = {}
    enriched = {"featured": "true", "fact_check": "verified", "tl_dr": "x", "description": "y" * 90, "image": "img"}
    assert cdb._score(enriched) > cdb._score(plain) + 40


def test_build_post_url_basic():
    p = Path("_posts/2026-05-15-some-slug.md")
    fm = {"categories": ["world"]}
    assert cdb._build_post_url(p, fm) == "/world/2026/05/15/some-slug/"


def test_build_post_url_no_category():
    p = Path("_posts/2026-05-15-some-slug.md")
    fm = {}
    assert cdb._build_post_url(p, fm) == "/news/2026/05/15/some-slug/"


def test_build_post_url_bad_stem():
    p = Path("_posts/random-name.md")
    assert cdb._build_post_url(p, {}) == ""
