"""Tests for utils/comment_replies.py — classifier + pick + safety."""
from __future__ import annotations

from utils.comment_replies import (
    REPLY_PANEL,
    classify_comment,
    pick_reply,
)


def test_classify_positive():
    assert classify_comment("Great video, love it!") == "positive"
    assert classify_comment("Thanks for the breakdown") == "positive"


def test_classify_curious_question():
    assert classify_comment("Why did the Fed actually do this?") == "curious"
    assert classify_comment("How does that work in practice") == "curious"


def test_classify_agreement():
    assert classify_comment("Exactly! 💯") == "agreement"
    assert classify_comment("Nailed it on the analysis") == "agreement"


def test_classify_geo_signal():
    assert classify_comment("Watching from Brazil 🇧🇷") == "geo"
    assert classify_comment("Here in Germany, the local angle is different")


def test_classify_avoids_dangerous_comments():
    assert classify_comment("AI slop garbage stop posting bots") is None
    assert classify_comment("This is wrong and incorrect propaganda") is None
    assert classify_comment("First!") is None


def test_classify_avoids_neutral():
    assert classify_comment("Interesting") is None
    assert classify_comment("Hmm") is None


def test_classify_avoids_too_short():
    assert classify_comment("ok") is None
    assert classify_comment("") is None


def test_classify_avoids_too_long():
    long = "x" * 1000
    assert classify_comment(long) is None


def test_pick_reply_returns_from_panel():
    reply = pick_reply("comment-id-abc", "positive")
    assert reply in REPLY_PANEL["positive"]


def test_pick_reply_is_deterministic():
    a = pick_reply("comment-id-xyz", "geo")
    b = pick_reply("comment-id-xyz", "geo")
    assert a == b


def test_pick_reply_distributes_across_panel():
    seen = set()
    for i in range(200):
        seen.add(pick_reply(f"c-{i}", "positive"))
    assert seen == set(REPLY_PANEL["positive"])


def test_pick_reply_unknown_sentiment_returns_none():
    assert pick_reply("c", "unknown") is None


def test_avoid_sub_for_sub():
    assert classify_comment("sub for sub please") is None
    assert classify_comment("sub4sub anyone?") is None


def test_avoid_self_promo():
    assert classify_comment("check out my channel for similar content") is None
