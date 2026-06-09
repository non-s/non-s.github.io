from utils.youtube_brain import creator_premortem, publish_brain


def _strong_story():
    return {
        "title": "Ducks fake injuries to protect young",
        "seo_title": "Ducks fake injuries to protect young",
        "hook": "Ducks fake injuries to protect their young.",
        "script": (
            "Ducks fake injuries to protect their young. Watch the wing movement first, "
            "because that cue pulls predators away from the nest. The duck keeps the "
            "threat focused on itself, then escapes when the chicks have cover."
        ),
        "thumbnail_text": "WATCH THE WING",
        "category": "birds",
        "story_format": "animal_intelligence",
    }


def test_creator_premortem_rewards_visible_action_and_payoff():
    brain = creator_premortem(_strong_story())

    assert brain["state"] == "publish_minded"
    assert brain["score"] >= 78
    assert "action_driven_promise" in brain["strengths"]
    assert brain["replay_reason"] == "watch_the_cue_again"


def test_creator_premortem_flags_generic_no_payoff_story():
    story = {
        "title": "Animals have another amazing secret",
        "hook": "Animals are amazing.",
        "script": "Animals are amazing and interesting.",
        "thumbnail_text": "AMAZING SECRET TODAY",
        "category": "wildlife",
    }

    brain = creator_premortem(story)

    assert brain["state"] == "do_not_publish"
    assert "no_action_promise" in brain["risks"]
    assert "payoff_not_explicit" in brain["risks"]


def test_publish_brain_accounts_for_production_basics():
    meta = {
        **_strong_story(),
        "has_captions": True,
        "has_broll": True,
        "visual_qa": {"checked": True, "approved": True},
        "publish_score": {"score": 85},
    }

    brain = publish_brain(meta)

    assert brain["state"] == "ship"
    assert brain["score"] >= 85
    assert "24h" in brain["post_publish_plan"]
