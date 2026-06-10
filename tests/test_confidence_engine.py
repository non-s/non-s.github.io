from utils.confidence_engine import assess_confidence, blend_weight


def test_confidence_blocks_small_samples():
    confidence = assess_confidence("category", 2, observed=2)

    assert confidence["recommendation_strength"] == "observe"
    assert confidence["can_adjust_strategy"] is False
    assert blend_weight(1.3, confidence) == 1.0


def test_confidence_allows_observed_minimum_sample():
    confidence = assess_confidence("category", 5, observed=5)

    assert confidence["can_adjust_strategy"] is True
    assert confidence["confidence_score"] >= 0.55
    assert blend_weight(1.3, confidence) > 1.0
