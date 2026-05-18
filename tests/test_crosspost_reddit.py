"""Tests for utils/crosspost_reddit.py — no live HTTP."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from utils import crosspost_reddit


@pytest.fixture
def reddit_env(monkeypatch):
    for var in ("REDDIT_USER_AGENT", "REDDIT_USERNAME", "REDDIT_PASSWORD",
                 "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"):
        monkeypatch.setenv(var, "x")
    yield


def test_skips_without_creds(monkeypatch):
    for var in ("REDDIT_USER_AGENT", "REDDIT_USERNAME", "REDDIT_PASSWORD",
                 "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    assert crosspost_reddit.crosspost_link("https://yt/x", "title") is None


def test_skips_on_auth_failure(reddit_env):
    bad_auth = MagicMock(status_code=401, text="forbidden")
    with patch("utils.crosspost_reddit.requests.post", return_value=bad_auth):
        assert crosspost_reddit.crosspost_link("https://yt/x", "title") is None


def test_happy_path_returns_url(reddit_env):
    auth_resp = MagicMock(status_code=200)
    auth_resp.json.return_value = {"access_token": "TOKEN"}
    submit_resp = MagicMock(status_code=200)
    submit_resp.json.return_value = {
        "json": {"errors": [], "data": {"url": "https://reddit.com/r/x/comments/abc"}}
    }

    def fake_post(url, *a, **kw):
        if "access_token" in url:
            return auth_resp
        if "submit" in url:
            return submit_resp
        raise AssertionError(url)

    with patch("utils.crosspost_reddit.requests.post", side_effect=fake_post):
        out = crosspost_reddit.crosspost_link(
            "https://yt/x", "Major event", category="world",
        )
    assert out and out.startswith("https://reddit.com")


def test_returns_none_on_submit_error(reddit_env):
    auth_resp = MagicMock(status_code=200)
    auth_resp.json.return_value = {"access_token": "T"}
    submit_resp = MagicMock(status_code=200)
    submit_resp.json.return_value = {
        "json": {"errors": [["ALREADY_SUB", "URL already submitted", "url"]],
                  "data": {}}
    }

    def fake_post(url, *a, **kw):
        return auth_resp if "access_token" in url else submit_resp

    with patch("utils.crosspost_reddit.requests.post", side_effect=fake_post):
        assert crosspost_reddit.crosspost_link("https://yt/x", "t") is None


def test_picks_subreddit_by_category():
    assert crosspost_reddit.SUBREDDIT_BY_CATEGORY["world"] == "worldnews"
    assert crosspost_reddit.SUBREDDIT_BY_CATEGORY["business"] == "Economics"
    assert crosspost_reddit.SUBREDDIT_BY_CATEGORY["ai"] == "MachineLearning"


def test_unknown_category_falls_back_to_worldnews(reddit_env):
    auth_resp = MagicMock(status_code=200)
    auth_resp.json.return_value = {"access_token": "T"}
    submit_resp = MagicMock(status_code=200)
    submit_resp.json.return_value = {
        "json": {"errors": [], "data": {"url": "https://reddit.com/r/worldnews/x"}}
    }
    seen_data: dict = {}

    def fake_post(url, *a, **kw):
        if "access_token" in url:
            return auth_resp
        seen_data.update(kw.get("data") or {})
        return submit_resp

    with patch("utils.crosspost_reddit.requests.post", side_effect=fake_post):
        crosspost_reddit.crosspost_link("https://yt/x", "title", category="unknown")
    assert seen_data["sr"] == "worldnews"


def test_override_subreddit_wins(reddit_env):
    auth_resp = MagicMock(status_code=200)
    auth_resp.json.return_value = {"access_token": "T"}
    submit_resp = MagicMock(status_code=200)
    submit_resp.json.return_value = {
        "json": {"errors": [], "data": {"url": "https://reddit.com/r/custom/x"}}
    }
    seen: dict = {}

    def fake_post(url, *a, **kw):
        if "access_token" in url:
            return auth_resp
        seen.update(kw.get("data") or {})
        return submit_resp

    with patch("utils.crosspost_reddit.requests.post", side_effect=fake_post):
        crosspost_reddit.crosspost_link("https://yt/x", "t", category="world",
                                          subreddit_override="custom")
    assert seen["sr"] == "custom"


def test_empty_title_skips(reddit_env):
    assert crosspost_reddit.crosspost_link("https://yt/x", "") is None
    assert crosspost_reddit.crosspost_link("https://yt/x", "   ") is None
