"""Tests for utils.ranking.entry_relevance_score — pre-AI headline ranker."""
import time
import types

from utils.ranking import entry_relevance_score


class _Entry(types.SimpleNamespace):
    """Lightweight stand-in for a feedparser entry."""


def test_substantive_headline_with_image_scores_high():
    score = entry_relevance_score(_Entry(
        title="Senate confirms Supreme Court nominee after marathon hearing",
        summary="A long, multi-paragraph description that runs well past 120 characters and provides real context for the headline above this one.",
        media_content=[{"url": "https://e.test/img.jpg"}],
        published_parsed=time.gmtime(),
    ))
    assert score >= 6


def test_clickbait_is_penalised():
    score = entry_relevance_score(_Entry(
        title="You won't believe what this celebrity did next — shocking!",
        summary="x" * 200,
    ))
    # Title 50-100 chars (3pt) + description ≥120 (2pt) − spam (3pt) ≈ 2.
    assert score < 4


def test_breaking_keyword_boosts_score():
    now_t = time.gmtime()
    fresh = _Entry(
        title="BREAKING: major bank failure reported by regulators",
        summary="x" * 150,
        published_parsed=now_t,
    )
    plain = _Entry(
        title="Major bank failure reported by regulators today now",
        summary="x" * 150,
        published_parsed=now_t,
    )
    assert entry_relevance_score(fresh) > entry_relevance_score(plain)


def test_short_headline_scores_low():
    score = entry_relevance_score(_Entry(title="news", summary=""))
    assert score <= 1


def test_recency_breaks_ties():
    now_t = time.gmtime()
    old_t = time.gmtime(time.time() - 48 * 3600)
    f_new = _Entry(
        title="A reasonably long substantive headline about a topic",
        summary="x" * 150,
        published_parsed=now_t,
    )
    f_old = _Entry(
        title="A reasonably long substantive headline about a topic",
        summary="x" * 150,
        published_parsed=old_t,
    )
    assert entry_relevance_score(f_new) > entry_relevance_score(f_old)
