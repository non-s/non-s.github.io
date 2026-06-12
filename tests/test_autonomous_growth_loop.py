from utils.autonomous_growth_loop import apply_plan_to_queue, build_plan


def _story(story_id: str, category: str = "farm", title: str = "Ducks fake injuries to protect young"):
    return {
        "id": story_id,
        "title": title,
        "seo_title": title,
        "hook": "Ducks fake injuries to protect their young.",
        "script": (
            "Ducks fake injuries when danger gets close. The movement pulls attention "
            "away from the nest and gives the young time to hide. One visible cue, "
            "one clear reason, one payoff."
        ),
        "category": category,
        "story_format": "animal_memory",
        "score": 9,
    }


def test_build_plan_creates_hypotheses_and_prioritises_queue():
    plan = build_plan(
        latest={
            "metric_scope": "youtube_analytics_and_public_statistics",
            "total_views": 2000,
            "subscribers_gained": 1,
            "shorts_tracked": 20,
            "avg_view_pct": 58,
            "category_avg_growth_score": {"farm": 400, "cats": 40},
            "format_avg_growth_score": {"animal_memory": 300, "single_fact": 80},
            "visual_learning": {
                "winner": "close_subject|feed_bright|high_contrast",
                "profiles": [{"profile": "close_subject|feed_bright|high_contrast", "n": 2}],
            },
            "top_performers": [{"title": "Ducks fake injuries to protect young"}],
        },
        experiments={"winners": {"hook_style": "outcome_first"}, "axis_stats": {}},
        post24={"counts": {"rewrite_hook": 2}},
        sequence_plan={
            "source_winners": 1,
            "variants": [
                {
                    "id": "seq-1",
                    "title": "Ducks part 2",
                    "sequence_variant": "same_format_new_animal",
                    "category": "farm",
                }
            ],
        },
        comments={"requested_animals": ["shark"], "content_prompts": ["do sharks remember?"]},
        queue={"stories": [_story("farm-1"), _story("cats-1", category="cats")]},
    )

    assert plan["autonomy_score"] >= 80
    assert plan["state"] == "fully_autonomous"
    assert plan["experiment_bank"]["hypotheses"]
    assert plan["sequence_bank"]["variant_count"] == 1
    assert plan["audience_requests"]["requested_animals"] == ["shark"]
    assert plan["visual_policy"]["winner"] == "close_subject|feed_bright|high_contrast"
    assert plan["queue"]["top_candidates"][0]["id"] == "farm-1"
    assert plan["queue"]["top_candidates"][0]["packaging_lab"]["title_variants"]
    assert any("Bias production" in item for item in plan["decisions"])


def test_apply_plan_to_queue_writes_autonomy_annotations():
    queue = {"stories": [_story("farm-1")]}
    plan = build_plan(
        latest={
            "category_avg_growth_score": {"farm": 400},
            "format_avg_growth_score": {"animal_memory": 300},
        },
        queue=queue,
    )

    updated, changed = apply_plan_to_queue(queue, plan)

    assert changed == 1
    annotation = updated["stories"][0]["autonomy"]
    assert annotation["priority"] > 0
    assert annotation["lane"] in {"proven_category", "fresh_experiment", "sequence"}
    assert annotation["state"] != "reject"
    assert annotation["packaging_lab"]["thumbnail_variants"]
