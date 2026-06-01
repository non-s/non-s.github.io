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
    assert titles_too_similar("Octopus fact from reef", "Octopus fact from reef")


def test_titles_too_similar_very_different():
    assert not titles_too_similar("Octopus vanishes near coral", "Owls fly without noise")


def test_titles_too_similar_near_duplicate():
    assert titles_too_similar(
        "Octopus changes colour near the coral reef",
        "Octopus changes colour close to the coral reef",
    )


def test_titles_not_similar():
    assert not titles_too_similar("Cats purr during rest", "Owls hunt silently at night")


def test_title_similarity_identical():
    assert title_similarity("Octopus colour shift", "Octopus colour shift") == pytest.approx(1.0)


def test_title_similarity_empty():
    assert title_similarity("", "hello") == 0.0
    assert title_similarity("hello", "") == 0.0


def test_title_similarity_partial():
    score = title_similarity("Octopus changes colour", "Octopus shifts colour near reef")
    assert 0.3 < score < 1.0


def test_title_similarity_stopwords_ignored():
    # "the" and "a" are stopwords — shouldn't inflate score
    score = title_similarity("the cat", "a dog")
    assert score == 0.0
