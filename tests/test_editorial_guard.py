from utils.editorial_guard import editorial_issues, editorial_verdict


def test_editorial_guard_blocks_robotic_title_shapes():
    story = {
        "title": "Whale use their movement to use",
        "script": "The cue is not random: it helps whale solve one clear problem.",
    }

    issues = editorial_issues(story)

    assert "robotic_use_loop" in issues
    assert "robotic_not_random_line" in issues
    assert editorial_verdict(story)["approved"] is False


def test_editorial_guard_blocks_common_mojibake():
    bad_title = "Baby goats love bottle feeding \u00e2\u20ac\u201d here's why \u00f0\u0178"

    assert "encoding_artifact" in editorial_issues({"title": bad_title})


def test_editorial_guard_allows_specific_natural_copy():
    story = {
        "title": "Whales rely on movement to survive",
        "hook": "Whales rely on movement before the turn.",
        "script": (
            "Whales rely on movement before the turn. Watch the body line first. "
            "That detail helps them stay safe when the moment changes."
        ),
    }

    assert editorial_issues(story) == []


def test_editorial_guard_blocks_bad_plural_verb():
    assert "bad_plural_verb" in editorial_issues({"title": "Orangutans gives away the clue"})
    assert "bad_plural_verb" in editorial_issues({"title": "Cows reveals the next move"})


def test_editorial_guard_blocks_rely_loop():
    assert "robotic_rely_loop" in editorial_issues({"title": "Lions rely on movement to rely"})


def test_editorial_guard_blocks_singular_subject_with_plural_verb():
    assert "bad_singular_subject_verb" in editorial_issues({"title": "Octopus turn the detail into the clue"})
    assert "bad_singular_subject_verb" in editorial_issues({"title": "Goat rely on body posture"})
    assert "bad_singular_subject_verb" in editorial_issues({"title": "Bear turn the detail into the clue"})
    assert "bad_singular_subject_verb" in editorial_issues({"title": "Macaw remember because the beak changes"})


def test_editorial_guard_blocks_non_animal_body_language():
    issues = editorial_issues(
        {
            "title": "Plants reveal the next move through body posture",
            "script": "Plants use body posture before the move.",
            "category": "plants",
        }
    )

    assert "non_animal_body_language" in issues


def test_editorial_guard_blocks_bad_because_changes_hook():
    assert "bad_because_changes" in editorial_issues({"hook": "Bumblebee signal because the wings changes the outcome"})


def test_editorial_guard_blocks_stitched_category_title():
    issues = editorial_issues({"title": "Birds This black bird's ear tufts aren't ears at all"})

    assert "stitched_category_title" in issues


def test_editorial_guard_blocks_repeated_leading_animal_title():
    assert "stitched_repeated_animal_title" in editorial_issues({"title": "Wolves Gray wolves fake their own noses"})
    assert "stitched_repeated_animal_title" in editorial_issues({"title": "Horses White horses see in color"})


def test_editorial_guard_blocks_generic_successor_templates():
    assert "generic_signal_cue" in editorial_issues({"title": "Chickens remember the signal cue for a reason"})
    assert "generic_detail_clue_title" in editorial_issues({"title": "Lions turn the detail into the clue"})
    assert "generic_next_move_movement" in editorial_issues({"title": "Tigers reveal the next move through movement"})
    assert "generic_body_posture_template" in editorial_issues({"title": "Penguins rely on body posture to signal"})
    assert "generic_detail_template" in editorial_issues({"title": "Goats signal the next move with detail"})
    assert "generic_movement_template" in editorial_issues({"title": "Chickens signal the next move with movement"})
    assert "generic_false_face_memory" in editorial_issues({"title": "Bears recognize faces through tail position"})
    assert "generic_signal_through_body_cue" in editorial_issues(
        {"title": "Horses recognize signals through ear position"}
    )
    assert "generic_signal_through_body_cue" not in editorial_issues(
        {"title": "Dolphins recognize signals through call"}
    )
    assert "generic_rely_to_signal_cue" in editorial_issues({"title": "Cows rely on ear position to signal"})
    assert "generic_next_move_cue" in editorial_issues({"title": "Tigers signal the next move with first movement"})
    assert "generic_rely_to_signal_cue" not in editorial_issues({"title": "Penguins rely on flipper movement to slide"})
    assert "generic_movement_changes_title" in editorial_issues(
        {"title": "This movement changes what orangutans do next"}
    )
    assert "generic_movement_changes_title" in editorial_issues({"title": "This first move changes what cows do next"})
    assert "generic_first_movement_reason" in editorial_issues(
        {"title": "Snakes rely on the first movement for a reason"}
    )
    assert "generic_first_move_title" in editorial_issues({"title": "Cows read the moment from one first move"})
    assert "generic_first_move_title" in editorial_issues(
        {"title": "Elephants react differently when the first move appears"}
    )
    assert "generic_first_move_title" in editorial_issues({"title": "Snakes rely on first movement to survive"})
    assert "awkward_ear_movement_changes" in editorial_issues(
        {"title": "Elephants react differently when the ear movement changes"}
    )
    assert "awkward_this_ear_position_changes" in editorial_issues(
        {"title": "This ear position changes what lions do next"}
    )
    assert "awkward_head_cue_title" in editorial_issues({"title": "This head cue changes what chickens do next"})


def test_editorial_guard_blocks_operator_meta_language_in_script():
    issues = editorial_issues(
        {
            "title": "Ducks rely on the injury display for a reason",
            "script": (
                "Ducks rely on the injury display before the payoff. The previous ducks Short "
                "worked because it gave one visible animal. This sequel keeps that winning shape."
            ),
        }
    )

    assert "operator_meta_language" in issues


def test_editorial_guard_blocks_remake_meta_language_in_script():
    issues = editorial_issues(
        {
            "title": "Goats follow the feeding cue before the payoff",
            "script": (
                "Goats show the useful cue before the payoff. The original topic pulled "
                "attention with this angle. This remake cuts straight to the payoff."
            ),
        }
    )

    assert "operator_meta_language" in issues


def test_editorial_guard_blocks_truncated_heres_title():
    assert "truncated_heres_title" in editorial_issues({"title": "Tigers never roar at their prey — here's"})
