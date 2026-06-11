import json

from scripts.comment_to_short_pipeline import run
from utils.comment_to_short import build_candidates, merge_into_queue


def test_comment_to_short_scores_question():
    candidates = build_candidates(
        {"raw_comments": [{"text": "Can you do sharks next?", "likeCount": 4, "video_id": "v"}]}
    )

    assert candidates[0]["score"] >= 64
    assert candidates[0]["source"] == "youtube_comment"


def test_comment_to_short_pipeline_writes_candidates_and_queue(tmp_path, monkeypatch):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "comments.json").write_text(
        json.dumps({"raw_comments": [{"text": "Can you do sharks next?", "likeCount": 4, "video_id": "v"}]}),
        encoding="utf-8",
    )
    (tmp_path / "_data" / "stories_queue.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
    monkeypatch.setenv("COMMENT_TO_SHORT_ENABLED", "1")

    payload = run(tmp_path)

    assert payload["queued"] == 1
    assert (tmp_path / "_data" / "comment_to_short_candidates.json").exists()


def test_merge_into_queue_is_idempotent():
    candidate = {"id": "comment-short-a", "score": 90, "title": "Viewer question"}

    first = merge_into_queue({"stories": []}, [candidate])
    second = merge_into_queue(first, [candidate])

    assert len(second["stories"]) == 1
