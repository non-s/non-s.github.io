from utils.session_graph import build_session_graph, choose_handoff, pinned_comment_payload


def test_session_graph_builds_edges_and_actions():
    markers = [
        {
            "video_id": "a",
            "title": "Octopus one",
            "category": "ocean",
            "series": "Ocean",
            "story_format": "mechanism",
            "views": 100,
        },
        {
            "video_id": "b",
            "title": "Octopus two",
            "category": "ocean",
            "series": "Ocean",
            "story_format": "mechanism",
            "views": 200,
        },
    ]

    graph = build_session_graph(markers)

    assert graph["edges"]
    assert graph["next_session_actions"]
    assert graph["coverage"] == 1.0


def test_pinned_comment_payload_uses_handoff():
    text = pinned_comment_payload({}, {"title": "Next Short", "url": "https://youtu.be/x"})

    assert "Next Short" in text
    assert "https://youtu.be/x" in text


def test_choose_handoff_skips_same_video():
    source = {"video_id": "a", "category": "birds"}
    chosen = choose_handoff(source, [{"video_id": "a", "category": "birds"}, {"video_id": "b", "category": "birds"}])

    assert chosen["video_id"] == "b"
