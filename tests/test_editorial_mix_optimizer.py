from utils.editorial_mix_optimizer import build_mix_plan, classify_lane, mix_adjustment


def test_classify_lane_detects_trend_and_sequel():
    assert classify_lane({"freshness_score": 80}) == "trend"
    assert classify_lane({"sequence_variant": "same_format_new_animal"}) == "sequel"


def test_mix_adjustment_penalizes_overused_lane():
    assert mix_adjustment({"freshness_score": 80}, ["trend", "trend", "trend"]) < 0


def test_build_mix_plan_counts_lanes():
    plan = build_mix_plan([{"id": "a", "freshness_score": 90}, {"id": "b", "category": "cats"}])

    assert plan["counts"]["trend"] == 1
    assert plan["counts"]["recovery"] == 1
