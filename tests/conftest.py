"""Shared pytest fixtures.

Keeps test files lean: every test that needs a fake Mistral or a
sample feedparser entry pulls them from here. The blog post fixtures
were removed when the Jekyll site was deleted (May 2026 pivot).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

# Make the repo root importable so tests can `import fetch_animals` etc.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _isolate_state_files(tmp_path_factory, monkeypatch):
    """Redirect every module that writes to `_data/...` at runtime
    into a per-test-session tmp dir.

    Tests have repeatedly leaked state files (music cache, brand cards,
    intro/outro audio, quota log, provider stats, channel memory,
    velocity ledger) into the repo's `_data/` because each module
    declares its path at import time. We can't catch every leak
    one-by-one without losing time — this fixture autouses across
    every test and forces all cache/ledger paths through a tmp dir.

    Individual tests that explicitly monkeypatch these constants are
    NOT affected — their specific overrides happen AFTER this fixture
    and win.
    """
    cache_root = tmp_path_factory.mktemp("isolated_data")

    # Each (module, attribute, path-fragment) tuple gets isolated.
    overrides = [
        ("utils.tiktok_quota",    "QUOTA_LOG",         "tiktok_quota_log.jsonl"),
        ("utils.provider_stats",  "STATS_LOG",         "provider_stats.jsonl"),
        ("utils.channel_memory",  "MEMORY_LOG",        "channel_memory.jsonl"),
        ("utils.velocity",        "VELOCITY_LOG",      "velocity.jsonl"),
        ("utils.music_bed",       "MUSIC_CACHE_DIR",   "music_cache"),
        ("utils.broll",           "_CACHE_DIR",        "broll_cache"),
        ("utils.brand_card",      "BRAND_CARD_CACHE",  "brand_card_cache"),
        ("utils.intro_outro",     "INTRO_OUTRO_CACHE", "intro_outro_cache"),
        ("utils.host_persona",    "PERSONA_FILE",      "host_persona.json"),
        ("fetch_animals",         "PUBLISHED_CLIPS_FILE", "published_clips.json"),
    ]
    for module_name, attr, frag in overrides:
        try:
            mod = __import__(module_name, fromlist=[attr])
        except Exception:
            continue
        if hasattr(mod, attr):
            monkeypatch.setattr(mod, attr, cache_root / frag, raising=False)

    # The Mistral-429 circuit breaker in utils.ai_helper holds module-
    # level state (`_mistral_429_streak`, `_mistral_circuit_open`).
    # Without an explicit reset, a 429-heavy test that trips the breaker
    # leaks "Mistral disabled" mode into every following test in the
    # same pytest process. Reset it once per test up front.
    try:
        from utils import ai_helper as _ah
        _ah._reset_mistral_circuit_breaker()
    except Exception:
        pass

    # No comment latch on TikTok (comment management isn't supported
    # by the Open API), but keep the hook for backwards compat with
    # tests that monkeypatch the upload module.


@pytest.fixture
def sample_feedparser_entry():
    """A dict that quacks like a feedparser entry."""
    e = types.SimpleNamespace()
    e.title = "Sample headline"
    e.link = "https://example.com/article"
    e.summary = "A short description."
    e.published = "Thu, 15 May 2026 10:00:00 +0000"
    e.tags = []
    return e


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
        raise RuntimeError(
            "Outbound HTTP not allowed in tests — use a fixture or mock."
        )

    monkeypatch.setattr(requests, "get", _refuse)
    monkeypatch.setattr(requests, "post", _refuse)
    monkeypatch.setattr(requests, "head", _refuse)
    monkeypatch.setattr(requests.Session, "get", _refuse)
    monkeypatch.setattr(requests.Session, "post", _refuse)
    monkeypatch.setattr(requests.Session, "head", _refuse)
