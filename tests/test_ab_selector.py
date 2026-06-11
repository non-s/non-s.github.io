from utils.ab_selector import BayesianABSelector


def test_live_variant_is_deterministic_without_winner():
    selector = BayesianABSelector()
    context = {"story_id": "story-123", "enough_data": False}

    first = selector.choose_live_variant("hook_style", ["a", "b", "c"], context)
    second = selector.choose_live_variant("hook_style", ["a", "b", "c"], context)

    assert first == second


def test_winner_is_preferred_when_enough_data():
    selector = BayesianABSelector()
    out = selector.choose_live_variant(
        "hook_style",
        ["a", "winner"],
        {"story_id": "story-123", "winner": "winner", "enough_data": True, "exploration_percent": 0},
    )

    assert out == "winner"


def test_insufficient_samples_do_not_crown_winner():
    selector = BayesianABSelector()
    ranked = selector.rank_axis(
        [{"variants": {"hook_style": "a"}, "metrics": {"average_view_percentage": 90}}],
        "hook_style",
        min_samples=2,
        min_days=1,
    )

    assert ranked["winner"] == ""
