import json

from scripts.post_upload_session_ops import build_session_ops


def test_session_ops_recommends_related_video(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    first = {
        "video_id": "a",
        "title": "Octopus skin warning",
        "category": "ocean",
        "series": "Ocean Mysteries",
        "story_format": "mechanism_reveal",
    }
    second = {
        "video_id": "b",
        "title": "Octopus color signal",
        "category": "ocean",
        "series": "Ocean Mysteries",
        "story_format": "mechanism_reveal",
    }
    (videos / "a.done").write_text(json.dumps(first), encoding="utf-8")
    (videos / "b.done").write_text(json.dumps(second), encoding="utf-8")

    out = build_session_ops(tmp_path)

    assert out["related_video_recommendations"]
    assert (tmp_path / "_data" / "related_video_recommendations.json").exists()


def test_session_ops_survives_missing_inputs(tmp_path):
    out = build_session_ops(tmp_path)

    assert out["related_video_recommendations"] == []
    assert out["comment_reply_short_candidates"] == []
