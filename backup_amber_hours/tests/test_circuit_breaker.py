"""Tests for utils/circuit_breaker.py."""

from __future__ import annotations

from utils.circuit_breaker import CircuitBreaker


def test_starts_closed():
    breaker = CircuitBreaker(threshold=3)
    assert breaker.is_open is False
    assert breaker.streak == 0


def test_opens_after_threshold_consecutive_failures():
    breaker = CircuitBreaker(threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open is False
    breaker.record_failure()
    assert breaker.is_open is True
    assert breaker.streak == 3


def test_success_resets_the_streak_and_closes_the_breaker():
    breaker = CircuitBreaker(threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    assert breaker.streak == 0
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open is False  # would have opened at 3 without the reset


def test_reset_reopens_for_reuse():
    breaker = CircuitBreaker(threshold=1)
    breaker.record_failure()
    assert breaker.is_open is True
    breaker.reset()
    assert breaker.is_open is False
    assert breaker.streak == 0


def test_threshold_is_clamped_to_at_least_one():
    breaker = CircuitBreaker(threshold=0)
    breaker.record_failure()
    assert breaker.is_open is True
