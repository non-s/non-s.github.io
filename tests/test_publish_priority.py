from utils.publish_priority import SELECTION_RULE, autonomy_priority, publish_priority_key, queue_score, retention_lift


def test_publish_priority_prefers_autonomy_before_scores():
    low = {
        "autonomy": {"priority": 10},
        "queue_prune": {"score": 99},
        "publish_score": {"score": 99},
    }
    high = {
        "autonomy": {"priority": 130},
        "queue_prune": {"score": 70},
        "publish_score": {"score": 70},
    }

    assert publish_priority_key(high) > publish_priority_key(low)


def test_publish_priority_falls_back_to_queue_then_publish_score():
    low = {"queue_prune": {"score": 70}, "publish_score": {"score": 99}}
    high = {"queue_prune": {"score": 80}, "publish_score": {"score": 60}}

    assert autonomy_priority(low, queue_score(low)) == 70
    assert publish_priority_key(high) > publish_priority_key(low)


def test_publish_priority_retention_lift_breaks_close_autonomy_calls():
    strong_opening = {
        "autonomy": {"priority": 100},
        "queue_prune": {"score": 80},
        "packaging": {"loop_score": 0.92},
    }
    weak_opening = {
        "autonomy": {"priority": 101},
        "queue_prune": {"score": 95},
        "packaging": {"swipe_risk": {"band": "high"}, "loop_score": 0.2},
    }
    strong_score = {
        "score": 92,
        "opening_retention": {"score": 100},
        "retention": {"signals": {"replay_score": 90}},
        "objective_gate": {"payoff_time_s": 8.0, "swipe_risk_band": "low"},
    }
    weak_score = {
        "score": 96,
        "opening_retention": {"score": 44},
        "retention": {"signals": {"replay_score": 45}},
        "objective_gate": {"payoff_time_s": 13.0, "swipe_risk_band": "high"},
    }

    assert retention_lift(strong_opening, strong_score) > 0
    assert retention_lift(weak_opening, weak_score) < 0
    assert publish_priority_key(strong_opening, strong_score) > publish_priority_key(weak_opening, weak_score)


def test_publish_priority_retention_lift_does_not_override_large_autonomy_gap():
    low_priority_strong = {
        "autonomy": {"priority": 10},
        "queue_prune": {"score": 100},
        "packaging": {"loop_score": 1.0},
    }
    high_priority_weak = {
        "autonomy": {"priority": 130},
        "queue_prune": {"score": 70},
        "packaging": {"swipe_risk": {"band": "medium"}, "loop_score": 0.2},
    }

    assert publish_priority_key(
        high_priority_weak,
        {"score": 70, "opening_retention": {"score": 45}, "objective_gate": {"payoff_time_s": 12}},
    ) > publish_priority_key(
        low_priority_strong,
        {"score": 99, "opening_retention": {"score": 100}, "objective_gate": {"payoff_time_s": 8}},
    )


def test_publish_priority_selection_rule_names_retention_lift():
    assert "retention lift" in SELECTION_RULE
