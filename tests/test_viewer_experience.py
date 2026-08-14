from utils.viewer_experience import assess_viewer_experience


def _story() -> dict[str, str]:
    return {"community_prompt": "Comment WIREFRAME or ORGANIC.", "visual_direction": "slow liquid wireframe motion"}


def test_review_rewards_clear_and_participatory_asset():
    result = assess_viewer_experience(
        title="Liquid Wire | Wireframe Dreams | ambient visuals",
        description="Generative procedural visuals with original synthesized music.",
        story_card=_story(),
        visual={"thumbnail": {"brightness": 120, "contrast": 35}},
    )
    assert result["clarity_score"] == 1.0
    assert result["participation_ready"] is True


def test_review_rejects_clickbait_and_unsupported_claims():
    result = assess_viewer_experience(
        title="You won't believe this deep sleep trick",
        description="", story_card={}, visual={"thumbnail": {"brightness": 5, "contrast": 2}},
    )
    assert result["clarity_score"] == 0.0
    assert any("reject" in flag for flag in result["flags"])
