import json

from scripts.post_upload_session_ops import build_session_ops


def test_session_ops_writes_graph_artifacts(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    for video_id in ("a", "b"):
        (videos / f"{video_id}.done").write_text(
            json.dumps({"video_id": video_id, "title": f"Video {video_id}", "category": "ocean", "series": "Ocean"}),
            encoding="utf-8",
        )

    payload = build_session_ops(tmp_path)

    assert payload["session_graph"]["edges"] >= 1
    assert (tmp_path / "_data" / "session_graph.json").exists()
    assert (tmp_path / "_data" / "next_session_actions.json").exists()
    assert (tmp_path / "_data" / "sequel_candidates.json").exists()
