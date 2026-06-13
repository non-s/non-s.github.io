import json
from pathlib import Path

from scripts.reconcile_queue_uploads import reconcile_queue_uploads


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_reconcile_queue_uploads_marks_uploaded_intent_consumed(tmp_path):
    _write_json(
        tmp_path / "_data/stories_queue.json",
        {
            "stories": [
                {"id": "bird-1", "title": "Birds read the moment", "consumed": False},
                {"id": "cat-1", "title": "Cats read the moment", "consumed": False},
            ]
        },
    )
    intents = tmp_path / "_data/upload_intents.jsonl"
    intents.parent.mkdir(parents=True, exist_ok=True)
    intents.write_text(
        "\n".join(
            [
                json.dumps({"story_id": "bird-1", "status": "prepared", "created_at": "old"}),
                json.dumps(
                    {
                        "story_id": "bird-1",
                        "status": "uploaded",
                        "created_at": "2026-06-13T08:41:25+00:00",
                        "video_id": "abc123",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = reconcile_queue_uploads(tmp_path)
    queue = json.loads((tmp_path / "_data/stories_queue.json").read_text(encoding="utf-8"))

    assert result["changed"] == 1
    assert result["pending"] == 1
    assert queue["stories"][0]["consumed"] is True
    assert queue["stories"][0]["consumed_at"] == "2026-06-13T08:41:25+00:00"
    assert queue["stories"][0]["uploaded_video_id"] == "abc123"
    assert queue["stories"][1]["consumed"] is False


def test_reconcile_queue_uploads_uses_done_marker_when_intent_missing(tmp_path):
    _write_json(
        tmp_path / "_data/stories_queue.json",
        {"stories": [{"id": "snake-1", "title": "Snakes use body shape", "consumed": False}]},
    )
    _write_json(
        tmp_path / "_videos/short-snake.done",
        {"story_id": "snake-1", "video_id": "vid456", "uploaded_at": "2026-06-13T07:00:00+00:00"},
    )

    result = reconcile_queue_uploads(tmp_path)
    queue = json.loads((tmp_path / "_data/stories_queue.json").read_text(encoding="utf-8"))

    assert result["changed"] == 1
    assert queue["stories"][0]["consumed"] is True
    assert queue["stories"][0]["uploaded_video_id"] == "vid456"
