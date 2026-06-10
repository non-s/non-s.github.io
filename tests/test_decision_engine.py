from utils.decision_engine import decide_story


def test_decision_engine_returns_explainable_decision():
    story = {
        "title": "Mushrooms signal through underground threads",
        "seo_title": "Mushrooms signal through underground threads",
        "hook": "Watch the roots before the forest changes.",
        "script": (
            "Watch the roots before the forest changes. Fungal threads move signals "
            "through soil, because the forest is connected below the surface. "
            "That hidden network explains how nutrients and warnings can travel fast."
        ),
        "thumbnail_text": "ROOT SIGNAL",
        "category": "fungi",
        "story_format": "hidden_network",
        "series": "Hidden Network",
        "cta_prompt": "Want more nature that feels like science fiction but is real?",
        "pinned_comment": "Is this closer to a network, a warning system, or something stranger?",
    }

    decision = decide_story(story)

    assert decision["decision"] in {"publish", "rewrite_or_test", "observe", "reject"}
    assert decision["confidence"]["confidence_score"] >= 0
    assert len(decision["data_sources"]) >= 4
    assert decision["reasoning"]
