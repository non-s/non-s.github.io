from utils.opening_retention import score_retention_opening


def test_score_retention_opening_rewards_frame_hook_and_reason_bridge():
    score = score_retention_opening(
        {
            "title": "Mushrooms release spores from hidden gills",
            "hook": "Mushrooms release spores from hidden gills.",
            "script": (
                "Mushrooms release spores from hidden gills. Watch the gills first, "
                "because those thin plates drop spores into moving air."
            ),
            "thumbnail_text": "HIDDEN GILLS",
            "category": "fungi",
        }
    )

    assert score["approved"] is True
    assert score["score"] >= 82
    assert "frame_hook_bridge" in score["strengths"]
    assert "reason_arrives_early" in score["strengths"]


def test_score_retention_opening_flags_generic_unbridged_opening():
    score = score_retention_opening(
        {
            "title": "Animals have another amazing secret",
            "hook": "Animals reveal one visible signal before the payoff.",
            "script": "Animals reveal one visible signal before the payoff. Something amazing happens later.",
            "thumbnail_text": "AMAZING SECRET TODAY",
            "category": "wildlife",
        }
    )

    assert score["approved"] is False
    assert score["score"] < 64
    assert "generic_opening_language" in score["risks"]
    assert "frame_text_not_echoed_early" in score["risks"]


def test_score_retention_opening_recognizes_bears_as_frontloaded_subject():
    score = score_retention_opening(
        {
            "title": "Bears reveal the scent map first",
            "hook": "Bears reveal the scent map first.",
            "script": (
                "Bears reveal the scent map first. Watch the scent map first, "
                "because smell can guide a bear before the eyes do."
            ),
            "thumbnail_text": "SCENT MAP",
            "category": "wildlife",
        }
    )

    assert score["approved"] is True
    assert score["subject"] == "bears"
    assert "subject_not_frontloaded" not in score["risks"]
    assert "frame_hook_bridge" in score["strengths"]


def test_score_retention_opening_counts_science_action_verbs():
    score = score_retention_opening(
        {
            "title": "Rock layers preserve the history of water",
            "hook": "Rock layers preserve the history of water.",
            "script": (
                "Rock layers preserve the history of water. Watch the stripe pattern first "
                "because each layer can mark mud, sand, ash, or ocean floor."
            ),
            "thumbnail_text": "ROCK TIMELINE",
            "category": "geology",
        }
    )

    assert "action_promise_early" in score["strengths"]
    assert "missing_early_action" not in score["risks"]
