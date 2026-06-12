import json

from scripts.session_graph_actioner import build_actions


def test_session_graph_actioner_preserves_target_diversity_metadata(tmp_path):
    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    (data_dir / "session_graph.json").write_text(
        json.dumps(
            {
                "action_score_threshold": 60,
                "target_reuse_limit": 2,
                "edges": [
                    {"source_video_id": "a", "target_video_id": "b", "score": 80},
                    {"source_video_id": "c", "target_video_id": "d", "score": 62},
                    {"source_video_id": "e", "target_video_id": "d", "score": 40},
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_actions(tmp_path)
    saved = json.loads((data_dir / "session_graph_actions.json").read_text(encoding="utf-8"))

    assert report["action_score_threshold"] == 60
    assert report["target_reuse_limit"] == 2
    assert report["unique_target_count"] == 2
    assert len(report["actions"]) == 2
    assert saved["action_score_threshold"] == 60
    assert saved["target_reuse_limit"] == 2
    assert saved["unique_target_count"] == 2
