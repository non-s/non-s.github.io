"""Shared pytest fixtures.

Keeps test files lean: every test that needs a fake Mistral, a temp
`_posts/` directory, or a sample feedparser entry pulls them from here.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

# Make the repo root importable so tests can `import fetch_news` etc.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def tmp_posts_dir(tmp_path):
    """Empty `_posts/` directory under a tmp root. Returns the path."""
    d = tmp_path / "_posts"
    d.mkdir()
    return d


@pytest.fixture
def sample_post(tmp_posts_dir):
    """Write one minimal post + return its path."""
    p = tmp_posts_dir / "2026-05-15-sample-headline.md"
    p.write_text(
        "---\n"
        'title: "Sample headline"\n'
        "date: 2026-05-15 10:00:00 +0000\n"
        "categories: [world]\n"
        "tags: [sample, fixture]\n"
        'description: "A short description."\n'
        'source_url: "https://example.com/article"\n'
        'source_name: "Example"\n'
        "---\n\nBody.\n",
        encoding="utf-8",
    )
    return p


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
