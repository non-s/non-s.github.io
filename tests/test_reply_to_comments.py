"""Tests for scripts/reply_to_comments.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import scripts.reply_to_comments as reply_to_comments


def _thread(comment_id, *, text="great video", author_channel_id="UCviewer", video_id="vid1", replies=None):
    return {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {
                "id": comment_id,
                "snippet": {
                    "textDisplay": text,
                    "authorDisplayName": "Someone",
                    "authorChannelId": {"value": author_channel_id},
                },
            },
        },
        "replies": {"comments": replies or []},
    }


def _youtube_with_threads(threads, channel_id="UCchannel"):
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {"items": [{"id": channel_id}]}
    youtube.commentThreads.return_value.list.return_value.execute.return_value = {
        "items": threads,
        "nextPageToken": None,
    }
    youtube.comments.return_value.insert.return_value.execute.return_value = {"id": "reply-1"}
    return youtube


def test_run_posts_a_reply_and_records_it_in_the_ledger(monkeypatch, tmp_path):
    ledger = tmp_path / "replied_comments.jsonl"
    monkeypatch.setattr(reply_to_comments, "LEDGER_PATH", ledger)
    youtube = _youtube_with_threads([_thread("c1")])
    monkeypatch.setattr(reply_to_comments, "get_youtube_service", lambda: youtube)

    summary = reply_to_comments.run(dry_run=False, max_replies=10)

    assert summary["replies_posted"] == 1
    youtube.comments.return_value.insert.assert_called_once()
    body = youtube.comments.return_value.insert.call_args.kwargs["body"]
    assert body["snippet"]["parentId"] == "c1"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["comment_id"] == "c1"


def test_run_skips_comments_authored_by_the_channel_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(reply_to_comments, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    youtube = _youtube_with_threads([_thread("c1", author_channel_id="UCchannel")])
    monkeypatch.setattr(reply_to_comments, "get_youtube_service", lambda: youtube)

    summary = reply_to_comments.run(dry_run=False, max_replies=10)

    assert summary["replies_posted"] == 0
    assert summary["skipped_own_comment"] == 1
    youtube.comments.return_value.insert.assert_not_called()


def test_run_skips_threads_the_channel_already_replied_to(monkeypatch, tmp_path):
    monkeypatch.setattr(reply_to_comments, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    already_replied = [{"snippet": {"authorChannelId": {"value": "UCchannel"}}}]
    youtube = _youtube_with_threads([_thread("c1", replies=already_replied)])
    monkeypatch.setattr(reply_to_comments, "get_youtube_service", lambda: youtube)

    summary = reply_to_comments.run(dry_run=False, max_replies=10)

    assert summary["replies_posted"] == 0
    assert summary["skipped_already_replied"] == 1
    youtube.comments.return_value.insert.assert_not_called()


def test_run_skips_comments_already_in_the_local_ledger(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"comment_id": "c1"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(reply_to_comments, "LEDGER_PATH", ledger)
    youtube = _youtube_with_threads([_thread("c1")])
    monkeypatch.setattr(reply_to_comments, "get_youtube_service", lambda: youtube)

    summary = reply_to_comments.run(dry_run=False, max_replies=10)

    assert summary["replies_posted"] == 0
    assert summary["skipped_already_replied"] == 1
    youtube.comments.return_value.insert.assert_not_called()


def test_run_skips_comments_that_look_like_spam(monkeypatch, tmp_path):
    monkeypatch.setattr(reply_to_comments, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    youtube = _youtube_with_threads([_thread("c1", text="check my channel www.spam.example")])
    monkeypatch.setattr(reply_to_comments, "get_youtube_service", lambda: youtube)

    summary = reply_to_comments.run(dry_run=False, max_replies=10)

    assert summary["replies_posted"] == 0
    assert summary["skipped_spam"] == 1
    youtube.comments.return_value.insert.assert_not_called()


def test_run_dry_run_never_calls_insert_or_writes_the_ledger(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(reply_to_comments, "LEDGER_PATH", ledger)
    youtube = _youtube_with_threads([_thread("c1")])
    monkeypatch.setattr(reply_to_comments, "get_youtube_service", lambda: youtube)

    summary = reply_to_comments.run(dry_run=True, max_replies=10)

    assert summary["replies_posted"] == 1
    assert summary["dry_run"] is True
    youtube.comments.return_value.insert.assert_not_called()
    assert not ledger.exists()


def test_run_respects_max_replies_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(reply_to_comments, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    threads = [_thread(f"c{i}") for i in range(5)]
    youtube = _youtube_with_threads(threads)
    monkeypatch.setattr(reply_to_comments, "get_youtube_service", lambda: youtube)

    summary = reply_to_comments.run(dry_run=False, max_replies=2)

    assert summary["replies_posted"] == 2
    assert youtube.comments.return_value.insert.call_count == 2


def test_run_returns_error_when_channel_id_cannot_be_resolved(monkeypatch, tmp_path):
    monkeypatch.setattr(reply_to_comments, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {"items": []}
    monkeypatch.setattr(reply_to_comments, "get_youtube_service", lambda: youtube)

    summary = reply_to_comments.run(dry_run=False, max_replies=10)

    assert summary == {"error": "no_channel_id"}
