"""Tests for utils/retry.py"""
import pytest
from utils.retry import retry_call, with_retry


def test_retry_call_success_first_try():
    calls = []
    def fn():
        calls.append(1)
        return "ok"
    assert retry_call(fn, max_attempts=3) == "ok"
    assert len(calls) == 1


def test_retry_call_success_second_try():
    calls = []
    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("not yet")
        return "ok"
    result = retry_call(fn, max_attempts=3, base_delay=0.01)
    assert result == "ok"
    assert len(calls) == 2


def test_retry_call_all_fail_returns_default():
    def fn():
        raise RuntimeError("always fails")
    result = retry_call(fn, max_attempts=3, base_delay=0.01, default="fallback")
    assert result == "fallback"


def test_retry_call_default_none():
    def fn():
        raise Exception("fail")
    result = retry_call(fn, max_attempts=2, base_delay=0.01)
    assert result is None


def test_with_retry_decorator_success():
    calls = []

    @with_retry(max_attempts=3, base_delay=0.01)
    def fn():
        calls.append(1)
        return 42

    assert fn() == 42
    assert len(calls) == 1


def test_with_retry_decorator_retries_then_raises():
    calls = []

    @with_retry(max_attempts=3, base_delay=0.01)
    def fn():
        calls.append(1)
        raise ValueError("always fail")

    with pytest.raises(ValueError):
        fn()
    assert len(calls) == 3


def test_with_retry_skip_on():
    calls = []

    @with_retry(max_attempts=3, base_delay=0.01, skip_on=(KeyError,))
    def fn():
        calls.append(1)
        raise KeyError("skip me")

    with pytest.raises(KeyError):
        fn()
    assert len(calls) == 1  # no retries on skip_on
