"""
utils/retry.py — Retry decorator with exponential backoff and jitter.
Used across all network calls in the GlobalBR News bot.
"""
import logging
import random
import time
from functools import wraps

log = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff: float = 2.0,
    jitter: float = 0.3,
    retry_on: tuple = (Exception,),
    skip_on: tuple = (),
):
    """
    Decorator: retry a function up to max_attempts times with exponential backoff + jitter.

    Args:
        max_attempts: Total attempts (including first try).
        base_delay:   Initial wait seconds before second attempt.
        max_delay:    Cap on wait time.
        backoff:      Multiplier applied to delay each retry.
        jitter:       Random fraction added to delay to avoid thundering herd.
        retry_on:     Exception types that trigger a retry.
        skip_on:      Exception types that skip retry and return default immediately.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except skip_on as exc:
                    log.debug("%s — skipping retry on %s: %s", fn.__name__, type(exc).__name__, exc)
                    raise
                except retry_on as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    wait = min(delay * (1 + random.uniform(0, jitter)), max_delay)
                    log.debug(
                        "%s — attempt %d/%d failed (%s: %s). Retrying in %.1fs…",
                        fn.__name__, attempt, max_attempts, type(exc).__name__, exc, wait,
                    )
                    time.sleep(wait)
                    delay = min(delay * backoff, max_delay)
            log.warning("%s — all %d attempts failed. Last error: %s", fn.__name__, max_attempts, last_exc)
            raise last_exc
        return wrapper
    return decorator


def retry_call(fn, *args, max_attempts=3, base_delay=1.0, default=None, **kwargs):
    """
    Inline retry without decorator — calls fn(*args, **kwargs) up to max_attempts times.
    Returns default if all attempts fail.
    """
    delay = base_delay
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if attempt == max_attempts:
                log.warning("retry_call(%s) — all %d attempts failed: %s", fn.__name__, max_attempts, exc)
                return default
            wait = min(delay * (1 + random.uniform(0, 0.3)), 30.0)
            log.debug("retry_call(%s) attempt %d/%d failed, retrying in %.1fs", fn.__name__, attempt, max_attempts, wait)
            time.sleep(wait)
            delay = min(delay * 2, 30.0)
    return default
