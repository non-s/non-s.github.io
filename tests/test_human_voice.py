from utils.human_voice import score_text


def test_human_voice_rewards_host_presence_and_detail():
    text = (
        "Chickens remember your face. I love this detail: they track eyes, "
        "voices, and tiny changes around the beak. That's why one calm "
        "farmer can feel familiar while a stranger makes them freeze."
    )
    result = score_text(text)
    assert result.score >= 80
    assert "host_presence" in result.strengths
    assert "concrete_detail" in result.strengths


def test_human_voice_penalizes_generic_copy():
    text = (
        "Did you know animals have fascinating unique adaptations in the "
        "animal kingdom? This amazing creature plays a vital role in nature."
    )
    result = score_text(text)
    assert result.score < 50
    assert "generic_phrasing" in result.issues
