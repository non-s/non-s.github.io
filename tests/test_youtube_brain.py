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


def test_creator_premortem_accepts_tight_forty_word_short_script():
    story = {
        "title": "Plants turn sunlight into stored sugar",
        "seo_title": "Plants turn sunlight into stored sugar",
        "hook": "Plants turn light into food.",
        "script": (
            "Plants turn light into food. Watch the leaf surface, because chlorophyll captures light "
            "and builds sugar from air and water. The green color is a tiny factory at work. "
            "Which plant clue should we decode next?"
        ),
        "thumbnail_text": "LIGHT TO SUGAR",
        "category": "plants",
        "story_format": "plant_mechanism",
    }

    brain = creator_premortem(story)

    assert "shorts_length_fit" in brain["strengths"]
    assert "script_length_risk" not in brain["risks"]


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
    assert "opening_retention_gap_risk" in brain["risks"]


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


def test_creator_premortem_accepts_space_action_verbs():
    story = {
        **_strong_story(),
        "title": "The moon keeps one face turned toward Earth",
        "seo_title": "The moon keeps one face turned toward Earth",
        "hook": "The moon keeps one face turned toward Earth.",
        "script": (
            "The moon keeps one face turned toward Earth. Watch the locked orbit first, "
            "because its spin and path around Earth stay synchronized."
        ),
        "thumbnail_text": "LOCKED FACE",
        "category": "space",
        "story_format": "space_engine",
    }

    brain = creator_premortem(story)

    assert "action_driven_promise" in brain["strengths"]
    assert "no_action_promise" not in brain["risks"]


def test_creator_premortem_counts_alphanumeric_thumbnail_tokens():
    story = {
        **_strong_story(),
        "title": "Mantises judge distance with 3D vision",
        "seo_title": "Mantises judge distance with 3D vision",
        "hook": "Mantises judge distance before they strike.",
        "script": (
            "Mantises judge distance before they strike. Watch the body angle first, "
            "because that depth check decides when the strike lands."
        ),
        "thumbnail_text": "3D STRIKE",
        "category": "insects",
    }

    brain = creator_premortem(story)

    assert "thumbnail_text_scannable" in brain["strengths"]
    assert "thumbnail_text_not_scannable" not in brain["risks"]


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


def test_creator_premortem_uses_nature_promise_for_forests():
    story = {
        **_strong_story(),
        "title": "Forests signal through leaf movement",
        "seo_title": "Forests signal through leaf movement",
        "hook": "Watch the leaf movement; the payoff lands seconds later.",
        "script": (
            "Forests reveal one visible signal. Watch the leaf movement, because forests use it "
            "to send a clear signal before the next move. The payoff appears before the final move."
        ),
        "thumbnail_text": "LEAF MOVE",
        "category": "forests",
        "story_format": "cute_behavior",
    }

    brain = creator_premortem(story)

    assert brain["viewer_promise"] == "See the forest detail that changes the whole scene."
    assert "cute behavior" not in brain["viewer_promise"]
    assert brain["satisfaction_bet"] == "The viewer gets one visible nature cue and one reason, fast."


def test_creator_premortem_rephrases_cute_behavior_for_animals():
    story = {
        **_strong_story(),
        "story_format": "cute_behavior",
    }

    brain = creator_premortem(story)

    assert brain["viewer_promise"] == "See why this visible behavior matters for ducks."
    assert "cute behavior" not in brain["viewer_promise"]


def test_creator_premortem_keeps_animal_subject_inside_nature_category():
    story = {
        **_strong_story(),
        "title": "Sharks rely on fin movement to survive",
        "seo_title": "Sharks rely on fin movement to survive",
        "hook": "Sharks rely on fin movement before the payoff.",
        "script": (
            "Sharks rely on fin movement before the payoff. Watch the fin movement, "
            "because that detail helps them survive."
        ),
        "thumbnail_text": "FIN SHIFT",
        "category": "ocean",
        "story_format": "survival_trick",
    }

    brain = creator_premortem(story)

    assert brain["viewer_promise"] == "See why sharks survival trick matters."
    assert brain["satisfaction_bet"] == "The viewer gets one visible behavior and one reason, fast."


def test_creator_premortem_recognizes_plural_science_subjects():
    fossil_story = {
        "title": "Fossils turn old bones into time clues",
        "seo_title": "Fossils turn old bones into time clues",
        "hook": "Fossils turn old bones into time clues.",
        "script": (
            "Fossils turn old bones into time clues. Watch the fossil shape first because minerals can "
            "replace bone while preserving the original outline. That preserved shape lets scientists "
            "read environments after the animal is gone."
        ),
        "thumbnail_text": "FOSSIL CLUE",
        "category": "discoveries",
        "story_format": "science_clue",
    }
    magnet_story = {
        "title": "Magnets reveal invisible fields in filings",
        "seo_title": "Magnets reveal invisible fields in filings",
        "hook": "Magnets reveal invisible fields in filings.",
        "script": (
            "Magnets reveal invisible fields in filings. Watch the filings first because each tiny piece "
            "lines up with the field around the magnet. The hidden force becomes a visible map in seconds."
        ),
        "thumbnail_text": "FIELD MAP",
        "category": "physics",
        "story_format": "physics_demo",
    }

    assert "subject_not_immediately_clear" not in creator_premortem(fossil_story)["risks"]
    assert "subject_not_immediately_clear" not in creator_premortem(magnet_story)["risks"]


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
