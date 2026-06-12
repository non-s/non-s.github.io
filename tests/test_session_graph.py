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


def test_session_graph_does_not_turn_malformed_titles_into_sequels():
    markers = [
        {
            "video_id": "bad",
            "title": "Birds This black bird's ear tufts aren't ears at all",
            "category": "birds",
        },
        {
            "video_id": "good",
            "title": "Dolphins recognize signals through call",
            "category": "ocean",
        },
    ]

    graph = build_session_graph(markers)
    titles = [item["title"] for item in graph["sequel_candidates"]]

    assert "Birds This black bird's ear tufts aren't ears at all" not in titles
    assert titles == ["Dolphins recognize signals through call"]
    assert all(node["title"] != "Birds This black bird's ear tufts aren't ears at all" for node in graph["nodes"])


def test_pinned_comment_payload_uses_handoff():
    text = pinned_comment_payload({}, {"title": "Next Short", "url": "https://youtu.be/x"})

    assert "Next Short" in text
    assert "https://youtu.be/x" in text


def test_choose_handoff_skips_same_video():
    source = {"video_id": "a", "category": "birds"}
    chosen = choose_handoff(source, [{"video_id": "a", "category": "birds"}, {"video_id": "b", "category": "birds"}])

    assert chosen["video_id"] == "b"


def test_choose_handoff_respects_blocked_targets():
    source = {"video_id": "a", "category": "birds"}
    chosen = choose_handoff(
        source,
        [
            {"video_id": "b", "category": "birds", "title": "Ducks follow ripples before feeding", "views": 1000},
            {"video_id": "c", "category": "birds", "title": "Owls map sound before they land", "views": 10},
        ],
        blocked_targets={"b"},
    )

    assert chosen["video_id"] == "c"


def test_choose_handoff_skips_malformed_target_title():
    source = {"video_id": "a", "category": "birds"}
    chosen = choose_handoff(
        source,
        [
            {"video_id": "bad", "category": "birds", "title": "Bird slides because of this tail", "views": 1000},
            {"video_id": "good", "category": "birds", "title": "Dolphins recognize signals through call", "views": 10},
        ],
    )

    assert chosen["video_id"] == "good"


def test_session_graph_caps_repeated_target_recommendations():
    markers = [
        {
            "video_id": "hero",
            "title": "Ducks follow ripples before feeding",
            "category": "birds",
            "series": "Bird Signals",
            "story_format": "mechanism",
            "views": 5000,
        },
        {
            "video_id": "alt",
            "title": "Owls map sound before they land",
            "category": "birds",
            "series": "Bird Signals",
            "story_format": "mechanism",
            "views": 50,
        },
    ]
    markers.extend(
        {
            "video_id": f"source-{idx}",
            "title": f"Parrots copy sound pattern {idx}",
            "category": "birds",
            "series": "Bird Signals",
            "story_format": "mechanism",
            "views": 100 + idx,
        }
        for idx in range(6)
    )

    graph = build_session_graph(markers)
    target_counts = {}
    for action in graph["next_session_actions"]:
        target_counts[action["target_video_id"]] = target_counts.get(action["target_video_id"], 0) + 1

    assert graph["target_reuse_limit"] == 2
    assert max(target_counts.values()) <= 2
    assert len(target_counts) > 2


def test_session_graph_keeps_low_score_edges_out_of_operator_actions():
    markers = [
        {
            "video_id": "source",
            "title": "Cats land quietly before the jump",
            "category": "cats",
            "series": "Pet Secrets",
        },
        {
            "video_id": "target",
            "title": "Dogs listen for one word before sprinting",
            "category": "dogs",
            "series": "Pet Secrets",
        },
    ]

    graph = build_session_graph(markers)

    assert graph["edges"][0]["score"] == 34
    assert graph["action_score_threshold"] == 55
    assert graph["next_session_actions"] == []
    assert graph["coverage"] == 0.0
