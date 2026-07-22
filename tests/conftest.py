"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _isolate_state_files(tmp_path_factory, monkeypatch):
    """Redirect every module that writes to `_data/...` at runtime
    into a per-test-session tmp dir, so tests can't leak cache/ledger
    files into the repo's `_data/`.

    Individual tests that explicitly monkeypatch these constants are
    NOT affected — their specific overrides happen AFTER this fixture
    and win.
    """
    cache_root = tmp_path_factory.mktemp("isolated_data")

    overrides = [
        ("utils.broll", "_CACHE_DIR", "broll_cache"),
        ("utils.host_persona", "PERSONA_FILE", "host_persona.json"),
        ("utils.provider_stats", "STATS_LOG", "provider_stats.jsonl"),
        ("utils.jamendo_cache", "_DEFAULT_PATH", "jamendo_search_cache.jsonl"),
    ]
    for module_name, attr, frag in overrides:
        try:
            mod = __import__(module_name, fromlist=[attr])
        except Exception:
            continue
        if hasattr(mod, attr):
            monkeypatch.setattr(mod, attr, cache_root / frag, raising=False)

    # The Gemini circuit breaker in utils.ai_helper holds module-level
    # state (`_gemini_429_streak`, `_gemini_circuit_open`). Without an
    # explicit reset, a failure-heavy test that trips the breaker leaks
    # "Gemini disabled" mode into every following test in the same pytest
    # process. Reset it once per test up front.
    try:
        from utils import ai_helper as _ah

        _ah._reset_gemini_circuit_breaker()
    except Exception:
        pass


@pytest.fixture
def mock_mistral(monkeypatch):
    """Patch utils.ai_helper.ai_text to return a canned dict-as-string.

    Yields a list — append `(prompt, response)` tuples to it inside the
    test to script consecutive AI calls; falls back to the first entry
    if exhausted.
    """
    from utils import ai_helper

    canned: list[tuple[str, str]] = []

    def _fake(prompt: str, *args, **kwargs) -> str:
        if not canned:
            return ""
        # Return the response from the first matching prompt substring,
        # otherwise pop the front.
        for trigger, resp in canned:
            if trigger and trigger in prompt:
                return resp
        return canned[0][1] if canned else ""

    monkeypatch.setattr(ai_helper, "ai_text", _fake, raising=True)
    return canned


@pytest.fixture
def no_network(monkeypatch):
    """Refuse outbound HTTP. Catch tests that accidentally hit the network."""
    import requests

    def _refuse(*args, **kwargs):
        raise RuntimeError("Outbound HTTP not allowed in tests — use a fixture or mock.")

    monkeypatch.setattr(requests, "get", _refuse)
    monkeypatch.setattr(requests, "post", _refuse)
    monkeypatch.setattr(requests, "head", _refuse)
    monkeypatch.setattr(requests.Session, "get", _refuse)
    monkeypatch.setattr(requests.Session, "post", _refuse)
    monkeypatch.setattr(requests.Session, "head", _refuse)
