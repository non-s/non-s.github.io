from utils.packaging import (
    cta_prompt,
    package_story,
    pinned_comment,
    replay_prompt,
    score_packaging,
    series_name,
    thumbnail_options,
    title_options,
)


def _story(**overrides):
    story = {
        "title": "Ducks fake injuries to protect young",
        "seo_title": "Ducks fake injuries to protect young",
        "hook": "Ducks fake injuries to protect their young.",
        "script": (
            "Ducks fake injuries to protect their young. Watch the wing movement first, "
            "because that cue pulls predators away from the nest."
        ),
        "thumbnail_text": "WATCH THE WING",
        "category": "birds",
    }
    story.update(overrides)
    return story


def test_title_options_create_magnetic_specific_variants():
    options = title_options(_story())

    assert any("watch" in option.lower() or "why" in option.lower() for option in options)
    assert all(len(option) <= 82 for option in options)


def test_thumbnail_options_are_short_scannable_phrases():
    options = thumbnail_options(_story(thumbnail_text="this phrase is far too long for a short thumbnail"))

    assert options
    assert all(len(option.split()) <= 4 for option in options)
    assert "WATCH THE WING" in options


def test_score_packaging_penalizes_generic_clickbait():
    weak = score_packaging(_story(
        title="Animals have another secret hiding in plain sight",
        seo_title="Animals have another secret hiding in plain sight",
        thumbnail_text="AMAZING SECRET TODAY",
        hook="Animals are amazing.",
    ))

    assert weak["state"] == "rewrite_packaging"
    assert "generic_clickbait_language" in weak["risks"]


def test_package_story_adds_comment_and_community_hook():
    packaged = package_story(_story(thumbnail_text=""))

    assert packaged["packaging"]["pinned_comment"]
    assert packaged["packaging"]["community_prompt"]
    assert packaged["packaging"]["cta_prompt"]
    assert packaged["packaging"]["replay_prompt"]
    assert packaged["series"]
    assert packaged["thumbnail_text"]
    assert "next animal" in pinned_comment(packaged).lower()


def test_packaging_assigns_repeatable_series_cta_and_loop_prompt():
    story = _story()

    assert series_name(story) in {"Survival Tricks", "Watch The Cue", "Nature Signals"}
    assert "Follow" in cta_prompt(story)
    assert "rewatch" in replay_prompt(story).lower()
