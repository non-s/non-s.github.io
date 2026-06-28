import re

from utils.packaging import (
    cta_prompt,
    normalize_story_category,
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


def test_score_packaging_recognizes_science_subjects_and_non_animal_action_verbs():
    score = score_packaging(
        _story(
            title="Lightning makes air explode into thunder",
            seo_title="Lightning makes air explode into thunder",
            hook="Lightning turns hot air into thunder.",
            script=(
                "Lightning turns hot air into thunder. Watch the bright channel first, "
                "because superheated air expands faster than sound can keep up."
            ),
            thumbnail_text="THUNDER SNAP",
            category="weather",
        )
    )

    assert "subject_not_clear" not in score["risks"]
    assert "missing_action_word" not in score["risks"]


def test_score_packaging_accepts_nature_reserve_action_verbs():
    stories = [
        _story(
            title="Mushrooms release spores from hidden gills",
            seo_title="Mushrooms release spores from hidden gills",
            hook="Mushrooms release spores from hidden gills.",
            script=(
                "Mushrooms release spores from hidden gills. Watch under the cap first, "
                "because that surface sends the next fungal generation into the air."
            ),
            thumbnail_text="SPORE GILLS",
            category="fungi",
        ),
        _story(
            title="Rivers sort mud and sand along each bank",
            seo_title="Rivers sort mud and sand along each bank",
            hook="Rivers sort sediment while they bend.",
            script=(
                "Rivers sort sediment while they bend. Watch the river bank first, "
                "because slower water drops heavier grains along the edge."
            ),
            thumbnail_text="BANK SORTING",
            category="rivers",
        ),
        _story(
            title="The moon keeps one face turned toward Earth",
            seo_title="The moon keeps one face turned toward Earth",
            hook="The moon keeps one face turned toward Earth.",
            script=(
                "The moon keeps one face turned toward Earth. Watch the locked orbit first, "
                "because its spin and path around Earth stay synchronized."
            ),
            thumbnail_text="LOCKED FACE",
            category="space",
        ),
    ]

    for story in stories:
        score = score_packaging(story)
        assert "missing_action_word" not in score["risks"]


def test_score_packaging_accepts_behavior_verbs_outside_old_animal_template_set():
    score = score_packaging(
        _story(
            title="Bees dance directions back to the hive",
            seo_title="Bees dance directions back to the hive",
            hook="Bees dance a map back to the hive.",
            script=(
                "Bees dance a map back to the hive. Watch the angle and duration first, "
                "because that pattern tells the others where food is waiting."
            ),
            thumbnail_text="DANCE MAP",
            category="insects",
        )
    )

    assert "missing_action_word" not in score["risks"]


def test_score_packaging_recognizes_hourly_queue_nature_cues_and_actions():
    rivers = score_packaging(
        _story(
            title="Rivers carve bends by stealing from one bank",
            seo_title="Rivers carve bends by stealing from one bank",
            hook="Rivers move sideways while they flow.",
            script=(
                "Rivers move sideways while they flow. Watch the outside bank, "
                "because faster water cuts that side while sediment drops inside the bend."
            ),
            thumbnail_text="BANK SHIFT",
            category="rivers",
        )
    )
    birds = score_packaging(
        _story(
            title="Birds see ultraviolet patterns we miss",
            seo_title="Birds see ultraviolet patterns we miss",
            hook="Birds see colors humans cannot see.",
            script=(
                "Birds see colors humans cannot see. Watch the feathers, "
                "because ultraviolet patterns can change mate and food signals."
            ),
            thumbnail_text="UV PATTERN",
            category="birds",
        )
    )

    assert "missing_visible_cue" not in rivers["risks"]
    assert "missing_action_word" not in rivers["risks"]
    assert "missing_visible_cue" not in birds["risks"]
    assert "missing_action_word" not in birds["risks"]


def test_score_packaging_accepts_visible_cue_in_opening_script():
    score = score_packaging(
        _story(
            title="Plants turn sunlight into stored sugar",
            seo_title="Plants turn sunlight into stored sugar",
            hook="Plants turn light into food.",
            script=(
                "Plants turn light into food. Watch the leaf surface, because chlorophyll captures light "
                "and builds sugar from air and water."
            ),
            thumbnail_text="LIGHT TO SUGAR",
            category="plants",
        )
    )

    assert "missing_visible_cue" not in score["risks"]


def test_normalize_story_category_recovers_science_lanes_from_copy():
    assert (
        normalize_story_category(
            _story(
                title="Plants count touches before snapping shut",
                seo_title="Plants count touches before snapping shut",
                hook="Plants can count touches before closing.",
                category="insects",
            )
        )
        == "plants"
    )
    assert (
        normalize_story_category(
            _story(
                title="Magnets make invisible fields visible",
                seo_title="Magnets make invisible fields visible",
                hook="Magnets can show a hidden force map.",
                category="wildlife",
            )
        )
        == "physics"
    )


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


def test_package_story_repairs_generic_frame_zero_copy():
    packaged = package_story(
        _story(
            title="Forests detect changes with their pattern",
            seo_title="Forests detect changes with their pattern",
            hook="Forests detect changes with their pattern.",
            script=(
                "Forests detect changes with their pattern. Watch the pattern, because that detail "
                "helps viewers understand what changes next."
            ),
            thumbnail_text="FORESTS PATTERN",
            category="forests",
            local_rewrite={"method": "deterministic_subject_fallback"},
        )
    )

    assert packaged["title"] == "Forests make cooler air under the canopy"
    assert packaged["hook"] == "Forests can cool the air below them."
    assert packaged["thumbnail_text"] == "COOL CANOPY"
    assert "detect changes with their pattern" not in packaged["script"].lower()
    assert packaged["frame_zero_repair"]["method"] == "curiosity_angle_frame_zero_repair"
    assert packaged["packaging"]["frame_zero"]["approved"] is True
    assert packaged["packaging"]["opening_retention"]["approved"] is True


def test_package_story_rewrites_low_frame_zero_retention_bridge():
    packaged = package_story(
        _story(
            title="Elephants can feel rumbles through the ground",
            seo_title="Elephants can feel rumbles through the ground",
            hook="Elephants can sense low rumbles underfoot.",
            script=(
                "Elephants can sense low rumbles underfoot. Watch the feet and stillness, "
                "because low elephant calls can travel through ground as vibrations."
            ),
            thumbnail_text="GROUND SIGNAL",
            category="wildlife",
        )
    )

    repair = packaged["frame_zero_repair"]
    assert repair["method"] == "curiosity_angle_frame_zero_retention_rewrite"
    assert repair["before"]["score"] < 82
    assert repair["after"]["score"] >= 82
    assert "Watch the ground signal first" in packaged["script"]
    assert packaged["packaging"]["opening_retention"]["approved"] is True


def test_package_story_reapplies_stale_frame_zero_repair_text():
    packaged = package_story(
        _story(
            title="Elephants can feel rumbles through the ground",
            seo_title="Elephants can feel rumbles through the ground",
            hook="Elephants can sense low rumbles underfoot.",
            script=(
                "Elephants can sense low rumbles underfoot. Watch the feet and stillness, "
                "because low elephant calls can travel through ground as vibrations."
            ),
            thumbnail_text="GROUND SIGNAL",
            category="wildlife",
            first_2s_narration="Elephants reveal the ground signal first Watch the ground signal first",
            frame_zero_repair={
                "method": "curiosity_angle_frame_zero_retention_rewrite",
                "reason": "opening_retention_below_floor",
                "cue": "ground signal",
                "after": {"score": 100, "approved": True},
            },
        )
    )

    assert packaged["hook"] == "Elephants reveal the ground signal first."
    assert packaged["frame_zero_repair"]["before"]["score"] < 82
    assert packaged["packaging"]["opening_retention"]["approved"] is True


def test_package_story_reapplies_stale_frame_zero_repair_below_tightening_band():
    packaged = package_story(
        _story(
            title="Bears can smell a meal long before seeing it",
            seo_title="Bears can smell a meal long before seeing it",
            hook="Bears can smell a meal long before seeing it.",
            script=(
                "Bears can smell a meal long before seeing it. Watch the nose first, "
                "because smell drives many bear decisions before the eyes do. That huge scent map "
                "helps them find food, avoid danger, and read who crossed the area earlier."
            ),
            thumbnail_text="SCENT MAP",
            category="wildlife",
            local_rewrite={"method": "curiosity_angle_duplicate_title_rescue"},
            first_2s_narration="Bears reveal the scent map first. Watch the scent map first, because",
            frame_zero_repair={
                "method": "curiosity_angle_frame_zero_retention_rewrite",
                "reason": "opening_retention_below_floor",
                "cue": "scent map",
                "after": {"score": 92, "approved": True},
            },
        )
    )

    assert packaged["hook"] == "Bears reveal the scent map first."
    assert packaged["script"].startswith("Bears reveal the scent map first. Watch the scent map first")
    assert packaged["frame_zero_repair"]["reason"] == "stale_frame_zero_repair"
    assert packaged["packaging"]["opening_retention"]["approved"] is True
    assert "frame_text_not_echoed_early" not in packaged["packaging"]["opening_retention"]["risks"]


def test_package_story_attaches_opening_retention_bridge():
    packaged = package_story(_story())

    retention_opening = packaged["packaging"]["opening_retention"]
    assert retention_opening["approved"] is True
    assert "frame_hook_bridge" in retention_opening["strengths"]
    assert "reason_arrives_early" in retention_opening["strengths"]
    assert packaged["first_2s_narration"] == " ".join(re.findall(r"[A-Za-z0-9']+", packaged["script"])[:12])
    assert packaged["subject"] == "ducks"
    assert packaged["cue"] not in {"", "cue", "visible cue"}
    assert packaged["visual_cue"] == packaged["cue"]


def test_package_story_refreshes_stale_first_2s_narration():
    packaged = package_story(
        _story(
            title="Rock layers expose erosion in bare open hills",
            seo_title="Rock layers expose erosion in bare open hills",
            hook="Rock layers show erosion without much cover.",
            script=(
                "Rock layers show erosion without much cover. Watch the bare ridges, because soft rock "
                "and sparse plants let rain and wind carve the surface quickly."
            ),
            thumbnail_text="BARE EROSION",
            category="geology",
            first_2s_narration="Old hook words that no longer match the current script",
        )
    )

    expected = " ".join(re.findall(r"[A-Za-z0-9']+", packaged["script"])[:12])
    assert packaged["first_2s_narration"] == expected
    assert packaged["opening_contract_refresh"]["reason"] == "first_2s_narration_stale"
    assert "Old hook words" in packaged["opening_contract_refresh"]["before"]


def test_package_story_scores_payoff_from_reveal_sentence_not_total_duration():
    packaged = package_story(
        _story(
            title="Forests trap cool air below thick leaves",
            seo_title="Forests trap cool air below thick leaves",
            hook="Forests trap cool air below thick leaves.",
            script=(
                "Forests trap cool air below thick leaves. Watch the shadow line first, because that detail "
                "shows the mechanism in motion. The shaded layer keeps soil moisture from leaving as fast, "
                "so air near the ground heats more slowly during the warmest hours. That is why small forest "
                "paths can feel cooler than open grass even when both places sit under the same sun. By the "
                "last line, the opening detail has a job viewers can name."
            ),
            thumbnail_text="COOL SHADE",
            category="forests",
            yt_tags=["forests"],
            local_rewrite={"method": "curiosity_angle_rescue"},
        )
    )

    preflight = packaged["packaging"]["preflight_inputs"]
    assert preflight["duration_hint_s"] > 19
    assert preflight["payoff_time_s"] <= 10.5
    assert preflight["payoff_reveal_sentence_index"] == 0


def test_package_story_still_flags_genuinely_late_payoff():
    packaged = package_story(
        _story(
            title="A forest path hides a cool-air trick",
            seo_title="A forest path hides a cool-air trick",
            hook="A forest path hides a cool-air trick.",
            script=(
                "The path looks ordinary at first. The camera moves across moss, trunks, leaf litter, roots, "
                "stones, damp soil, low branches, and a slow pan under the canopy before any explanation "
                "starts. The shade line matters because leaves block direct sun and slow evaporation near "
                "the ground."
            ),
            thumbnail_text="COOL SHADE",
            category="forests",
            yt_tags=["forests"],
            local_rewrite={"method": "curiosity_angle_rescue"},
        )
    )

    preflight = packaged["packaging"]["preflight_inputs"]
    assert preflight["payoff_time_s"] > 10.5
    assert preflight["payoff_reveal_sentence_index"] == 2


def test_package_story_recognizes_science_subjects_in_first_words():
    packaged = package_story(
        _story(
            title="Crystals grow by repeating one tiny pattern",
            seo_title="Crystals grow by repeating one tiny pattern",
            hook="Crystals build shape from repeating atoms.",
            script=(
                "Crystals build shape from repeating atoms. Watch the crystal edge first, "
                "because each repeating unit gives the next layer a place to lock in."
            ),
            thumbnail_text="CRYSTAL GROWTH",
            category="chemistry",
        )
    )

    retention_opening = packaged["packaging"]["opening_retention"]
    assert retention_opening["subject"] == "crystals"
    assert "subject_not_frontloaded" not in retention_opening["risks"]
    assert packaged["subject"] == "crystals"
    assert packaged["cue"] == "crystal growth"


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


def test_package_story_replaces_stale_animal_series_for_weather():
    packaged = package_story(
        _story(
            title="Lightning turns air into a shock wave",
            seo_title="Lightning turns air into a shock wave",
            hook="Lightning turns air into a shock wave.",
            script=(
                "Lightning turns air into a shock wave. Watch the flash first, because lightning heats "
                "a narrow path of air extremely fast. Which storm signal next?"
            ),
            thumbnail_text="THUNDER SNAP",
            category="weather",
            series="Animal Superpowers #16",
            story_format="animal_intelligence",
            yt_tags=["weather", "lightning"],
        )
    )

    assert packaged["story_format"] == "earth_engine"
    assert packaged["series"].startswith("Earth Engine")
    assert "animal" not in packaged["series"].lower()
    assert "animal signal" not in packaged["cta_prompt"].lower()
    assert "another nature signal" in packaged["pinned_comment"].lower()


def test_package_story_preserves_success_recovery_format_and_copy():
    packaged = package_story(
        _story(
            title="Forests cool the ground through canopy shade",
            seo_title="Forests cool the ground through canopy shade",
            hook="Forests cool the ground with canopy shade.",
            script=(
                "Forests cool the ground with canopy shade. Watch the canopy shade first, "
                "because leaves block direct sun and hold moisture near the soil."
            ),
            thumbnail_text="COOL CANOPY",
            category="forests",
            story_format="earth_engine",
            success_recovery={
                "category": "forests",
                "visible": "canopy shade",
                "format": "body_superpower",
                "hook_style": "outcome_first",
            },
            experiments={"hook_style": "outcome_first"},
        )
    )

    assert packaged["story_format"] == "body_superpower"
    assert packaged["seo_title"] == "Forests cool the ground through canopy shade"
    assert packaged["hook"] == "Forests cool the ground with canopy shade."
    assert packaged["thumbnail_text"] == "COOL CANOPY"


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
