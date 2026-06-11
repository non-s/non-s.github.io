from utils.swipe_risk import SwipeRiskScore


def test_motion_and_short_copy_reduce_swipe_risk():
    scorer = SwipeRiskScore()
    weak = scorer.score_opening(
        {
            "first_frame_text_words": 7,
            "hook_words": 14,
            "visual_motion_score": 0.20,
            "caption_chars_per_second": 21,
            "contrast_score": 0.45,
            "hook_specificity": 0.30,
            "novelty_score": 0.30,
        }
    )
    strong = scorer.score_opening(
        {
            "first_frame_text_words": 3,
            "hook_words": 8,
            "visual_motion_score": 0.80,
            "caption_chars_per_second": 11,
            "contrast_score": 0.85,
            "hook_specificity": 0.82,
            "novelty_score": 0.71,
        }
    )

    assert strong["score"] < weak["score"]
    assert weak["band"] == "high"
    assert strong["band"] == "low"
