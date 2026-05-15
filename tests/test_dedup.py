"""Tests for utils/dedup.py"""
import pytest
from utils.dedup import levenshtein, titles_too_similar, title_similarity


def test_levenshtein_identical():
    assert levenshtein("hello", "hello") == 0


def test_levenshtein_empty():
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3


def test_levenshtein_one_char():
    assert levenshtein("a", "b") == 1


def test_levenshtein_substitution():
    assert levenshtein("cat", "bat") == 1


def test_levenshtein_symmetric():
    assert levenshtein("abc", "xyz") == levenshtein("xyz", "abc")


def test_titles_too_similar_identical():
    assert titles_too_similar("Breaking news from Paris", "Breaking news from Paris")


def test_titles_too_similar_very_different():
    assert not titles_too_similar("Space rocket launches today", "Local bakery wins award")


def test_titles_too_similar_near_duplicate():
    assert titles_too_similar(
        "Scientists discover new planet near Earth",
        "Scientists discover new planet close to Earth",
    )


def test_titles_not_similar():
    assert not titles_too_similar("Climate summit in Geneva", "Stock market hits record high")


def test_title_similarity_identical():
    assert title_similarity("Climate change summit", "Climate change summit") == pytest.approx(1.0)


def test_title_similarity_empty():
    assert title_similarity("", "hello") == 0.0
    assert title_similarity("hello", "") == 0.0


def test_title_similarity_partial():
    score = title_similarity("Apple announces new iPhone", "Apple releases new iPhone model")
    assert 0.3 < score < 1.0


def test_title_similarity_stopwords_ignored():
    # "the" and "a" are stopwords — shouldn't inflate score
    score = title_similarity("the cat", "a dog")
    assert score == 0.0
