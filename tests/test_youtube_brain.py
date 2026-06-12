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


def test_creator_premortem_penalizes_malformed_packaging_language():
    story = {
        **_strong_story(),
        "title": "Sheep use their hooves to use",
        "seo_title": "Sheep use their hooves to use",
        "hook": "Sheep use their hooves to warn the herd.",
    }

    brain = creator_premortem(story)

    assert brain["state"] != "publish_minded"
    assert "malformed_packaging_language" in brain["risks"]
    assert "Rewrite the title like a human editor" in " ".join(brain["commands"])


def test_creator_premortem_accepts_natural_causal_payoff():
    story = {
        **_strong_story(),
        "script": (
            "Ducks fake injuries to protect their young. Watch the wing movement first. "
            "That detail helps them pull predators away from the nest before the duck escapes."
        ),
    }

    brain = creator_premortem(story)

    assert "clear_payoff" in brain["strengths"]
    assert "payoff_not_explicit" not in brain["risks"]


def test_creator_premortem_treats_rely_as_visible_action():
    story = {
        **_strong_story(),
        "title": "Lions rely on ear position for a reason",
        "seo_title": "Lions rely on ear position for a reason",
        "hook": "Lions rely on ear position before the payoff.",
        "script": (
            "Lions rely on ear position before the payoff. Watch the ears first, "
            "because that tiny cue explains the next move before the viewer swipes."
        ),
        "thumbnail_text": "LIONS EAR CUE",
        "category": "wildlife",
    }

    brain = creator_premortem(story)

    assert brain["state"] == "publish_minded"
    assert "action_driven_promise" in brain["strengths"]
    assert "no_action_promise" not in brain["risks"]


def test_creator_premortem_flags_generic_successor_templates():
    story = {
        **_strong_story(),
        "title": "Chickens remember the signal cue for a reason",
        "seo_title": "Chickens remember the signal cue for a reason",
        "hook": "Chickens remember the signal cue before the payoff.",
    }

    brain = creator_premortem(story)

    assert "generic_visual_cue_language" in brain["risks"]


def test_creator_premortem_recognizes_specific_subjects_outside_category_name():
    fox_story = {
        **_strong_story(),
        "title": "This tail position changes what foxes do next",
        "seo_title": "This tail position changes what foxes do next",
        "hook": "Foxes reveal one visible signal.",
        "script": (
            "Foxes reveal one visible signal. Watch tail position, because foxes use it "
            "to send a clear signal before the next move. The payoff appears before the final move."
        ),
        "thumbnail_text": "FOX TAIL CUE",
        "category": "arctic",
    }
    turtle_story = {
        **_strong_story(),
        "title": "Turtles read the moment from one head cue",
        "seo_title": "Turtles read the moment from one head cue",
        "hook": "Turtles reveal one visible signal.",
        "script": (
            "Turtles reveal one visible signal. Watch head movement, because turtles use it "
            "to send a clear signal before the next move. The payoff appears before the final move."
        ),
        "thumbnail_text": "TURTLE HEAD CUE",
        "category": "discoveries",
    }

    assert "subject_not_immediately_clear" not in creator_premortem(fox_story)["risks"]
    assert "subject_not_immediately_clear" not in creator_premortem(turtle_story)["risks"]


def test_creator_premortem_flags_internal_strategy_language():
    story = {
        **_strong_story(),
        "title": "Ducks rely on the injury display for a reason",
        "seo_title": "Ducks rely on the injury display for a reason",
        "hook": "Ducks rely on the injury display before the payoff.",
        "script": (
            "Ducks rely on the injury display before the payoff. The previous ducks Short "
            "worked because it gave one visible animal and one payoff. This sequel keeps "
            "that winning shape. Same proven pattern, new fact, no repeat."
        ),
    }

    brain = creator_premortem(story)

    assert "operator_meta_language" in brain["risks"]
    assert "Remove internal channel strategy language" in " ".join(brain["commands"])


def test_creator_premortem_flags_remake_strategy_language():
    story = {
        **_strong_story(),
        "title": "Goats follow the feeding cue before the payoff",
        "seo_title": "Goats follow the feeding cue before the payoff",
        "hook": "Goats show the useful cue before the payoff.",
        "script": (
            "Goats show the useful cue before the payoff. The original topic pulled "
            "attention with this angle. This remake cuts straight to the payoff."
        ),
    }

    assert "operator_meta_language" in creator_premortem(story)["risks"]


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
