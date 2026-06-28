from utils.loop_engine import LoopGenerator


def test_loop_plan_returns_valid_payload_for_empty_script():
    out = LoopGenerator().plan({}, {})

    assert out["callback_keyword"]
    assert out["final_line"]
    assert 0 <= out["loop_score"] <= 1


def test_loop_score_rises_with_callback_structure():
    generator = LoopGenerator()
    weak = generator.plan(
        {"script": "The octopus changes skin. Then the ocean moves on."},
        {"hook": "This octopus changes skin before it attacks."},
    )
    strong = generator.plan(
        {"script": "The octopus changes skin. That skin is the warning."},
        {"hook": "This octopus changes skin before it attacks."},
    )

    assert strong["loop_score"] >= weak["loop_score"]
    assert len(strong["final_line"].split()) <= 13


def test_loop_line_handles_plural_subject_callbacks():
    generator = LoopGenerator()
    forest = generator.plan(
        {"script": ("Forests reveal one visible signal. The payoff appears before the final move.")},
        {"hook": "Forests reveal one visible signal."},
    )
    wings = generator.plan(
        {"script": "The wings move first. That wings pattern explains the turn."},
        {"hook": "The wings move first."},
    )

    assert forest["final_line"] == "Now the first clue at the start makes sense."
    assert "forests at the start makes sense" not in forest["final_line"].lower()
    assert "wings at the start make sense" in wings["final_line"].lower()


def test_loop_rewrites_generic_question_to_visible_cue_callback():
    out = LoopGenerator().plan(
        {
            "script": (
                "Foxes can hunt sounds hidden under snow. Watch the snow pause before the jump. " "Would you hear it?"
            ),
            "hook": "Foxes can hunt sounds hidden under snow.",
        },
        {
            "hook": "Foxes can hunt sounds hidden under snow.",
            "first_frame_text": "SNOW HEARING",
        },
    )

    assert out["rewrite_applied"] is True
    assert out["callback_keyword"] == "snow hearing"
    assert out["final_line"] == "Now the snow hearing at the start makes sense."
    assert out["loop_score"] >= 0.45


def test_loop_preserves_question_that_already_reopens_the_cue():
    out = LoopGenerator().plan(
        {
            "script": (
                "Foxes can hunt sounds hidden under snow. Watch the snow pause before the jump. "
                "Did you catch the snow hearing?"
            ),
            "hook": "Foxes can hunt sounds hidden under snow.",
        },
        {
            "hook": "Foxes can hunt sounds hidden under snow.",
            "first_frame_text": "SNOW HEARING",
        },
    )

    assert out["rewrite_applied"] is False
    assert out["callback_keyword"] == "snow hearing"
    assert out["final_line"] == "Did you catch the snow hearing?"


def test_loop_scores_first_frame_cue_as_opening_context():
    out = LoopGenerator().plan(
        {
            "script": (
                "Chickens can remember individual faces. Watch the flock pause before it changes. " "Would you spot it?"
            ),
            "hook": "Chickens can remember individual faces.",
        },
        {
            "hook": "Chickens can remember individual faces.",
            "first_frame_text": "FACE MEMORY",
        },
    )

    assert out["callback_keyword"] == "face memory"
    assert out["final_line"] == "Now the face memory at the start makes sense."
    assert out["loop_score"] >= 0.45


def test_loop_rewrites_partial_signal_question_to_full_visible_cue():
    out = LoopGenerator().plan(
        {
            "script": (
                "Elephants reveal the ground signal first. Watch the ground move under them. "
                "Would you notice the signal?."
            ),
            "hook": "Elephants reveal the ground signal first.",
        },
        {
            "hook": "Elephants reveal the ground signal first.",
            "first_frame_text": "GROUND SIGNAL",
        },
    )

    assert out["rewrite_applied"] is True
    assert out["callback_keyword"] == "ground signal"
    assert out["final_line"] == "Now the ground signal at the start makes sense."
