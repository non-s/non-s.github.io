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
    assert all("signal the next move with movement" not in option.lower() for option in options)


def test_thumbnail_options_are_short_scannable_phrases():
    options = thumbnail_options(_story(thumbnail_text="this phrase is far too long for a short thumbnail"))

    assert options
    assert all(len(option.split()) <= 4 for option in options)
    assert "FAKE INJURY" in options


def test_score_packaging_penalizes_generic_clickbait():
    weak = score_packaging(
        _story(
            title="Animals have another secret hiding in plain sight",
            seo_title="Animals have another secret hiding in plain sight",
            thumbnail_text="AMAZING SECRET TODAY",
            hook="Animals are amazing.",
        )
    )

    assert weak["state"] == "rewrite_packaging"
    assert "generic_clickbait_language" in weak["risks"]


def test_score_packaging_penalizes_generic_successor_templates():
    weak = score_packaging(
        _story(
            title="Chickens remember the signal cue for a reason",
            seo_title="Chickens remember the signal cue for a reason",
            thumbnail_text="CHICKENS SIGNAL",
            hook="Chickens remember the signal cue before the payoff.",
        )
    )

    assert weak["state"] == "rewrite_packaging"
    assert "generic_clickbait_language" in weak["risks"]


def test_score_packaging_penalizes_generic_ducklings_movement_shape():
    score = score_packaging(
        _story(
            title="Ducklings rely on wing movement to steer",
            seo_title="Ducklings rely on wing movement to steer",
            hook="Ducklings rely on wing movement before the move.",
            thumbnail_text="DUCKLINGS WING",
        )
    )

    assert score["state"] == "rewrite_packaging"
    assert "generic_clickbait_language" in score["risks"]
    assert "subject_not_clear" not in score["risks"]
    assert "missing_action_word" not in score["risks"]


def test_package_story_keeps_visible_subject_in_selected_hook():
    packaged = package_story(
        _story(
            title="Ducklings rely on wing position to survive",
            seo_title="Ducklings rely on wing position to survive",
            hook="Ducklings rely on wing position.",
            script=(
                "Ducklings rely on wing position. Watch the wing angle, "
                "because ducklings use it to stay safe when the moment changes."
            ),
            thumbnail_text="WING ANGLE",
            category="farm",
            source_url="https://www.pexels.com/video/duckling-swimming/",
        )
    )

    assert "ducklings" in packaged["hook"].lower()
    assert "group" in packaged["hook"].lower()
    assert packaged["thumbnail_text"] == "TINY MATH"


def test_score_packaging_penalizes_generic_rely_to_signal_shape():
    weak = score_packaging(
        _story(
            title="Ducklings rely on wing movement to signal",
            seo_title="Ducklings rely on wing movement to signal",
            hook="Ducklings rely on wing movement before the move.",
            thumbnail_text="DUCKLINGS WING",
        )
    )

    assert weak["state"] == "rewrite_packaging"
    assert "generic_clickbait_language" in weak["risks"]


def test_title_options_use_natural_head_movement_language():
    options = title_options(
        _story(
            title="Chickens react differently when their heads move",
            seo_title="Chickens react differently when their heads move",
            hook="Chickens read one visible signal.",
            script=(
                "Chickens read one visible signal. Watch head movement, because chickens use it "
                "to recognize familiar signals faster."
            ),
            thumbnail_text="CHICKENS HEAD MOVEMENT",
            category="farm",
        )
    )

    assert any("view steady" in option.lower() for option in options)
    assert all("head cue" not in option.lower() for option in options)
    assert all("head movement" not in option.lower() for option in options)


def test_package_story_uses_fungi_detail_instead_of_subject_as_cue():
    packaged = package_story(
        _story(
            title="Mushrooms use mushrooms before they change",
            seo_title="Mushrooms use mushrooms before they change",
            hook="Mushrooms signal through underground threads.",
            script=(
                "Mushrooms signal through underground threads. Watch the thread network first, "
                "because it moves nutrients before the forest changes."
            ),
            thumbnail_text="FUNGAL WEB",
            category="fungi",
            yt_tags=["mushrooms", "mycelium", "forest network"],
        )
    )

    assert "use mushrooms" not in packaged["title"].lower()
    assert "underground threads" in pinned_comment(packaged).lower()
    assert "underground threads" in replay_prompt(packaged).lower()


def test_package_story_uses_nature_signal_language_for_forests():
    packaged = package_story(
        _story(
            title="Forests read the moment from one leaves",
            seo_title="Forests read the moment from one leaves",
            hook="This forests changes right before the payoff.",
            script=(
                "Forests reveal one visible signal. Watch the leaves, because forests use it "
                "to send a clear signal before the next move."
            ),
            thumbnail_text="FORESTS LEAVES",
            category="forests",
            yt_tags=[],
        )
    )

    assert packaged["title"] == "Forests make cooler air under the canopy"
    assert packaged["thumbnail_text"] == "COOL CANOPY"
    assert "another nature signal" in pinned_comment(packaged).lower()
    assert "one leaves" not in packaged["packaging"]["pinned_comment"].lower()


def test_package_story_uses_nature_signal_language_for_trees():
    packaged = package_story(
        _story(
            title="Trees signal through root network",
            seo_title="Trees signal through root network",
            hook="Trees reveal one visible signal.",
            script=(
                "Trees reveal one visible signal. Watch roots, because that detail shows how trees shift "
                "before the payoff."
            ),
            thumbnail_text="ROOT NETWORK",
            category="trees",
            yt_tags=[],
        )
    )

    assert "another nature signal" in pinned_comment(packaged).lower()
    assert "trees quietly engineer" in cta_prompt(packaged).lower()


def test_package_story_keeps_animal_signal_for_animals_in_nature_categories():
    packaged = package_story(
        _story(
            title="Sharks rely on fin movement to survive",
            seo_title="Sharks rely on fin movement to survive",
            hook="Sharks rely on fin movement before the payoff.",
            script=(
                "Sharks rely on fin movement before the payoff. Watch the fin movement, "
                "because that detail helps them survive."
            ),
            thumbnail_text="FIN SHIFT",
            category="ocean",
            yt_tags=[],
        )
    )

    assert "another animal signal" in pinned_comment(packaged).lower()


def test_package_story_normalizes_earth_category_from_title_and_tags():
    packaged = package_story(
        _story(
            title="Earth systems signal through cloud patterns",
            seo_title="Earth systems signal through cloud patterns",
            hook="Watch the cloud pattern; the payoff lands seconds later.",
            script=(
                "Earth systems reveal one visible signal. Watch the cloud pattern, because that detail "
                "shows how earth systems shift before the payoff."
            ),
            thumbnail_text="LEAF CLUE",
            category="insects",
            yt_tags=["earth systems", "earth_from_space", "clouds", "atmosphere"],
        )
    )

    assert packaged["category"] == "earth_from_space"
    assert packaged["thumbnail_text"] == "STORM ENGINE"
    assert "another nature signal" in pinned_comment(packaged).lower()


def test_package_story_adds_comment_and_community_hook():
    packaged = package_story(_story(thumbnail_text=""))

    assert packaged["packaging"]["pinned_comment"]
    assert packaged["packaging"]["community_prompt"]
    assert packaged["packaging"]["cta_prompt"]
    assert packaged["packaging"]["replay_prompt"]
    assert packaged["series"]
    assert packaged["thumbnail_text"]
    assert "adaptation" in pinned_comment(packaged).lower()
    assert "tomorrow" in pinned_comment(packaged).lower()


def test_package_story_preserves_remake_factory_packaging():
    packaged = package_story(
        _story(
            title="Goats follow the feeding cue before the payoff",
            seo_title="Goats follow the feeding cue before the payoff",
            hook="Goats show the useful cue before the payoff.",
            thumbnail_text="GOATS FEEDING CUE",
            production_mode="remake_factory",
            source="Remake Factory",
        )
    )

    assert packaged["title"] == "Goats follow the feeding cue before the payoff"
    assert packaged["hook"] == "Goats show the useful cue before the payoff."
    assert packaged["thumbnail_text"] == "GOATS FEEDING CUE"
    assert packaged["packaging"]["selected_variant"]


def test_packaging_assigns_repeatable_series_cta_and_loop_prompt():
    story = _story()

    assert series_name(story) in {"Survival Tricks", "Watch The Cue", "Nature Signals"}
    assert "Want" in cta_prompt(story)
    assert "signal" in cta_prompt(_story(category="farm")).lower()
    assert "rewatch" in replay_prompt(story).lower()
