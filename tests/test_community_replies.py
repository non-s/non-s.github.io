"""Tests for utils/community_replies.py."""

from __future__ import annotations

from utils.community_replies import REPLY_TEMPLATES, looks_like_spam, pick_reply


def test_pick_reply_is_deterministic_for_the_same_comment_id():
    assert pick_reply("abc123") == pick_reply("abc123")


def test_pick_reply_always_returns_a_known_template():
    for comment_id in ("a", "bb", "ccc", "1234567890"):
        assert pick_reply(comment_id) in REPLY_TEMPLATES


def test_pick_reply_spreads_across_templates():
    picks = {pick_reply(str(i)) for i in range(50)}
    assert len(picks) > 1


def test_looks_like_spam_flags_links():
    assert looks_like_spam("check out my channel at https://example.com")
    assert looks_like_spam("www.spam-site.com free followers")
    assert looks_like_spam("HTTP://UPPERCASE-LINK.TEST")


def test_looks_like_spam_leaves_ordinary_comments_alone():
    assert not looks_like_spam("this is so relaxing, thank you")
    assert not looks_like_spam("")
    assert not looks_like_spam(None)
