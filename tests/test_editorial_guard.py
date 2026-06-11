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


def test_editorial_guard_blocks_singular_subject_with_plural_verb():
    assert "bad_singular_subject_verb" in editorial_issues({"title": "Octopus turn the detail into the clue"})
    assert "bad_singular_subject_verb" in editorial_issues({"title": "Goat rely on body posture"})
    assert "bad_singular_subject_verb" in editorial_issues({"title": "Bear turn the detail into the clue"})
    assert "bad_singular_subject_verb" in editorial_issues({"title": "Macaw remember because the beak changes"})


def test_editorial_guard_blocks_non_animal_body_language():
    issues = editorial_issues({
        "title": "Plants reveal the next move through body posture",
        "script": "Plants use body posture before the move.",
        "category": "plants",
    })

    assert "non_animal_body_language" in issues


def test_editorial_guard_blocks_bad_because_changes_hook():
    assert "bad_because_changes" in editorial_issues({"hook": "Bumblebee signal because the wings changes the outcome"})
