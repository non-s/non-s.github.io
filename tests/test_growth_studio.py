from utils.growth_studio import (
    build_performance_matrix,
    choose_narrative_template,
    choose_narrator_profile,
    production_mode_for_story,
    remake_candidates,
    studio_brief_for_story,
    weekly_brief,
    winners_and_losers,
)


def test_choose_narrative_template_uses_hot_format():
    story = {
        "id": "a",
        "category": "ocean",
        "story_format": "animal_memory",
        "title": "Dolphins remember each other",
    }
    out = choose_narrative_template(story, {"hot_formats": ["animal_memory"]})
    assert out["id"] == "outcome_then_because"
    assert "because" in out["prompt_rule"].lower()


def test_choose_narrator_profile_uses_category_fit():
    warm = choose_narrator_profile({"category": "cats", "title": "Cats purr"})
    steady = choose_narrator_profile({"category": "reptiles", "title": "Snakes sense heat"})
    assert warm["variant"] == "jenny"
    assert steady["variant"] == "guy"


def test_studio_brief_contains_prompt_overlay():
    brief = studio_brief_for_story({
        "id": "story-1",
        "category": "farm",
        "title": "Goats recognize happy voices",
    })
    assert brief["production_mode"] in {"exploit", "explore", "moonshot", "steady"}
    assert brief["narrative_template"]["id"]
    assert brief["narrator"]["variant"]
    assert "Narrative template" in brief["prompt_overlay"]


def test_performance_matrix_finds_winners_and_losers():
    observations = [
        {
            "category": "cats",
            "story_format": "animal_memory",
            "narrator_voice": "en-US-JennyNeural",
            "experiments": {"hook_style": "outcome_first"},
            "series": "Pet Secrets",
            "humanity_label": "signature",
            "growth_score": 200,
            "average_view_percentage": 75,
        },
        {
            "category": "ocean",
            "story_format": "visual_detail",
            "narrator_voice": "en-US-AriaNeural",
            "experiments": {"hook_style": "question"},
            "series": "Ocean Mysteries",
            "humanity_label": "plain",
            "growth_score": 50,
            "average_view_percentage": 40,
        },
    ]
    matrix = build_performance_matrix(observations)
    wl = winners_and_losers(matrix)
    assert matrix["category"]["cats"]["mean_growth"] == 200
    assert wl["winners"]["category"]["value"] == "cats"
    assert wl["losers"]["category"]["value"] == "ocean"


def test_remake_candidates_classifies_almost_good_and_sequels():
    out = remake_candidates([
        {"video_id": "a", "title": "Cats", "views": 100, "view_pct": 58, "growth_score": 80},
        {"video_id": "b", "title": "Dogs", "views": 500, "view_pct": 68, "growth_score": 180},
    ])
    assert out[0]["action"].startswith("remake")
    assert "sequel" in out[1]["action"]


def test_weekly_brief_summarizes_growth_loop():
    observations = [{"category": "cats", "growth_score": 100, "experiments": {}}]
    matrix = build_performance_matrix(observations)
    brief = weekly_brief({"total_views": 1000, "avg_view_pct": 70}, observations, matrix, [])
    assert brief["views"] == 1000
    assert brief["best_category"] == "cats"
    assert brief["production_mix"]["exploit"] >= 50


def test_production_mode_is_deterministic():
    story = {"id": "fixed", "category": "cats", "story_format": "animal_memory"}
    strategy = {"hot_categories": ["cats"], "hot_formats": ["animal_memory"]}
    assert production_mode_for_story(story, strategy) == production_mode_for_story(story, strategy)
