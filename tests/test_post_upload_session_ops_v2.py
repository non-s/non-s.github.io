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
    assert payload["session_graph"]["action_score_threshold"] == 55
    assert payload["session_graph"]["target_reuse_limit"] == 2
    assert (tmp_path / "_data" / "session_graph.json").exists()
    assert (tmp_path / "_data" / "next_session_actions.json").exists()
    assert (tmp_path / "_data" / "sequel_candidates.json").exists()
    graph = json.loads((tmp_path / "_data" / "session_graph.json").read_text(encoding="utf-8"))
    actions = json.loads((tmp_path / "_data" / "next_session_actions.json").read_text(encoding="utf-8"))
    assert graph["action_score_threshold"] == 55
    assert graph["target_reuse_limit"] == 2
    assert actions["action_score_threshold"] == 55
    assert actions["target_reuse_limit"] == 2
