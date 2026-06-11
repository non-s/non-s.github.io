from utils.ab_selector import BayesianABSelector


def _row(variant, day, engaged=100, mean=70):
    return {
        "pulled_at": day,
        "variants": {"hook_style": variant},
        "metrics": {"engaged_views": engaged, "average_view_percentage": mean},
        "derived": {"engaged_view_rate": mean / 100},
    }


def test_ab_selector_guardrails_require_engaged_views():
    selector = BayesianABSelector()
    rows = [_row("a", "2026-06-10", engaged=1), _row("a", "2026-06-11", engaged=1)]

    status = selector.guardrail_status(rows, min_samples=2, min_days=2, min_engaged_views=10)

    assert status["eligible"] is False
    assert "below_min_engaged_views" in status["reasons"]


def test_rank_axis_returns_guardrails_and_losers():
    selector = BayesianABSelector()
    rows = [
        _row("winner", "2026-06-10", mean=90),
        _row("winner", "2026-06-11", mean=90),
        _row("loser", "2026-06-10", mean=20),
        _row("loser", "2026-06-11", mean=20),
    ]

    ranked = selector.rank_axis(rows, "hook_style", min_samples=2, min_days=1)

    assert ranked["winner"] == "winner"
    assert "guardrails" in ranked
    assert "loser" in ranked["paused_losers"]
