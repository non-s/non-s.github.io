"""Testes para utils/comment_responder.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import utils.comment_responder as cr


@pytest.fixture(autouse=True)
def _isolate_state_file(tmp_path: Path, monkeypatch):
    """Isola comments_responded.json em tmp_path para nao poluir o repo."""
    monkeypatch.setattr(cr, "_state_file", lambda: tmp_path / "comments_responded.json")


def _comment(
    comment_id: str,
    text: str,
    author: str = "Viewer",
    published_at: str = "2026-08-01T12:00:00.000Z",
    channel_id: str = "",
) -> dict:
    """Monta um item de commentThreads.list no formato da API."""
    snippet = {
        "authorDisplayName": author,
        "textDisplay": text,
        "publishedAt": published_at,
        "topLevelComment": {"id": comment_id},
    }
    if channel_id:
        snippet["authorChannelId"] = {"value": channel_id}
    return {"id": f"thread_{comment_id}", "snippet": snippet}


class TestIsSpam:
    def test_plain_text_is_not_spam(self):
        assert cr.is_spam("this cat is so cute") is False

    def test_url_is_spam(self):
        assert cr.is_spam("check https://example.com please") is True

    def test_www_is_spam(self):
        assert cr.is_spam("visit www.mysite.com") is True

    def test_promo_word_is_spam(self):
        assert cr.is_spam("subscribe to my channel") is True

    def test_empty_is_spam(self):
        assert cr.is_spam("") is True


class TestSelectCommentsToReply:
    def test_selects_in_published_order_and_respects_limit(self):
        comments = [
            _comment("1", "so cute!", published_at="2026-08-01T09:00:00Z"),
            _comment("2", "love the jazz", published_at="2026-08-01T10:00:00Z"),
            _comment("3", "my dog vibes", published_at="2026-08-01T11:00:00Z"),
        ]
        state = {"replied": {}, "author_last_reply": {}}
        selected = cr.select_comments_to_reply(comments, state, max_replies=2)
        assert [(cid, text) for _t, cid, _a, text in selected] == [
            ("1", "so cute!"),
            ("2", "love the jazz"),
        ]

    def test_skips_already_replied(self):
        comments = [_comment("1", "so cute!")]
        state = {"replied": {"1": {"at": "x"}}, "author_last_reply": {}}
        assert cr.select_comments_to_reply(comments, state) == []

    def test_skips_own_comment(self):
        channel = "UC123"
        comments = [_comment("1", "my own comment", channel_id=channel)]
        state = {"replied": {}, "author_last_reply": {}}
        assert cr.select_comments_to_reply(comments, state, channel_id=channel) == []

    def test_skips_spam(self):
        comments = [_comment("1", "visit www.spam.com")]
        state = {"replied": {}, "author_last_reply": {}}
        assert cr.select_comments_to_reply(comments, state) == []

    def test_skips_out_of_range_length(self):
        comments = [_comment("1", "x"), _comment("2", "y" * 500)]
        state = {"replied": {}, "author_last_reply": {}}
        assert cr.select_comments_to_reply(comments, state) == []

    def test_skips_author_replied_today(self):
        comments = [_comment("1", "so cute!", author="Bob")]
        state = {"replied": {}, "author_last_reply": {"Bob": cr._today_iso()}}
        assert cr.select_comments_to_reply(comments, state) == []

    def test_empty_comments(self):
        assert cr.select_comments_to_reply([], {"replied": {}, "author_last_reply": {}}) == []


class TestGenerateReply:
    @patch("utils.comment_responder.ai_text", return_value="That's my favorite part too!")
    def test_uses_ai_reply(self, _ai):
        reply = cr.generate_reply("cute", author="Bob")
        assert reply == "That's my favorite part too!"

    @patch("utils.comment_responder.ai_text", return_value="")
    def test_falls_back_to_local(self, _ai):
        reply = cr.generate_reply("cute", author="Bob")
        assert reply in cr._FALLBACK_REPLIES

    @patch("utils.comment_responder.ai_text", return_value="https://evil.com check this")
    def test_rejects_suspicious_ai_reply(self, _ai):
        reply = cr.generate_reply("cute", author="Bob")
        assert reply in cr._FALLBACK_REPLIES

    @patch("utils.comment_responder.ai_text", return_value="ok " + "long " * 200)
    def test_caps_reply_length(self, _ai):
        reply = cr.generate_reply("cute", author="Bob")
        assert len(reply) <= cr._MAX_REPLY_LEN


class TestPostReply:
    def test_post_success(self):
        service = MagicMock()
        service.comments().insert().execute.return_value = {"id": "reply_1"}
        result = cr.post_reply(service, "parent_1", "hi", retry_call=lambda f: f())
        assert result == "reply_1"

    def test_post_failure_returns_none(self):
        service = MagicMock()
        service.comments().insert().execute.side_effect = RuntimeError("403")

        def retry(func):
            raise RuntimeError("403")

        assert cr.post_reply(service, "parent_1", "hi", retry_call=retry) is None


class TestFetchTopLevelComments:
    def test_returns_items(self):
        service = MagicMock()
        service.commentThreads().list().execute.return_value = {"items": [{"id": "t1"}]}
        result = cr.fetch_top_level_comments(service, "UC123")
        assert result == [{"id": "t1"}]

    def test_returns_empty_on_error(self):
        service = MagicMock()
        service.commentThreads().list().execute.side_effect = RuntimeError("boom")
        assert cr.fetch_top_level_comments(service, "UC123") == []


class TestRunCommentEngagement:
    def test_full_flow_persists_state(self, tmp_path):
        service = MagicMock()
        comments = [
            _comment("1", "so cute!", author="Bob", published_at="2026-08-01T09:00:00Z"),
            _comment("2", "love it", author="Ana", published_at="2026-08-01T10:00:00Z"),
        ]
        with (
            patch("utils.comment_responder.fetch_top_level_comments", return_value=comments),
            patch("utils.comment_responder.generate_reply", return_value="thank you!"),
            patch("utils.comment_responder.post_reply", side_effect=["r1", "r2"]),
        ):
            report = cr.run_comment_engagement(service, "UC123")

        assert report["fetched"] == 2
        assert report["replied"] == 2
        assert report["failed"] == 0
        state = cr._load_state()
        assert set(state["replied"].keys()) == {"1", "2"}
        assert state["author_last_reply"]["Bob"] == cr._today_iso()

    def test_dry_run_does_not_post(self):
        service = MagicMock()
        comments = [_comment("1", "so cute!", author="Bob")]
        with (
            patch("utils.comment_responder.fetch_top_level_comments", return_value=comments),
            patch("utils.comment_responder.generate_reply") as mock_reply,
        ):
            report = cr.run_comment_engagement(service, "UC123", dry_run=True)

        assert report["candidates"] == 1
        assert report["replied"] == 0
        mock_reply.assert_not_called()
        assert cr._load_state() == {"replied": {}, "author_last_reply": {}}

    def test_failed_post_is_counted_and_not_recorded(self):
        service = MagicMock()
        comments = [_comment("1", "so cute!", author="Bob")]

        def failing_reply(*_a, **_k):
            return None

        with (
            patch("utils.comment_responder.fetch_top_level_comments", return_value=comments),
            patch("utils.comment_responder.generate_reply", return_value="hi"),
            patch("utils.comment_responder.post_reply", side_effect=failing_reply),
        ):
            report = cr.run_comment_engagement(service, "UC123")

        assert report["failed"] == 1
        assert cr._load_state()["replied"] == {}
