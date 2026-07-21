"""Tests for utils/community_posts.py."""

from __future__ import annotations

from utils.community_posts import POST_TEMPLATES, draft_for_week


def test_draft_for_week_is_deterministic():
    assert draft_for_week("2026-W30") == draft_for_week("2026-W30")


def test_draft_for_week_changes_across_weeks():
    drafts = {draft_for_week(f"2026-W{i:02d}")["text"] for i in range(1, 20)}
    assert len(drafts) > 1


def test_draft_for_week_never_leaves_the_options_placeholder_unfilled():
    for i in range(1, 30):
        draft = draft_for_week(f"2026-W{i:02d}")
        assert "{options}" not in draft["text"]
    # sanity: the pool actually contains a template that uses {options}, so
    # the substitution above is exercised and not just vacuously true.
    assert any("{options}" in template for template in POST_TEMPLATES)


def test_draft_for_week_returns_week_key():
    assert draft_for_week("2026-W30")["week"] == "2026-W30"
