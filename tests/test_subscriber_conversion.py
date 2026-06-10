from utils.subscriber_conversion import (
    build_fan_growth,
    contextual_cta,
    debate_prompt,
    detect_robotic_title,
    score_subscriber_conversion,
    series_identity,
)


def test_contextual_cta_uses_category_identity():
    assert "science fiction" in contextual_cta({"category": "fungi"}).lower()
    assert "earth" in contextual_cta({"category": "volcanoes"}).lower()


def test_debate_prompt_asks_for_opinion_not_generic_topic():
    prompt = debate_prompt({"category": "birds"})

    assert "adaptation" in prompt.lower()
    assert "what topic" not in prompt.lower()


def test_robotic_title_detector_blocks_repetitive_ai_shape():
    out = detect_robotic_title("Ducks does this for one reason")

    assert out["state"] == "block"


def test_subscriber_conversion_scores_series_and_debate_comment():
    story = {
        "title": "Mushrooms signal below the forest",
        "hook": "Mushrooms signal before the forest changes.",
        "cta_prompt": "Want more nature that feels like science fiction but is real?",
        "series": "Hidden Network #7",
        "packaging": {"pinned_comment": "Is this closer to a network or something stranger?"},
        "category": "fungi",
    }

    out = score_subscriber_conversion(story)

    assert out["score"] >= 76
    assert out["state"] == "strong"


def test_series_identity_numbers_from_memory():
    out = series_identity({"category": "fungi"}, {"series_counts": {"Hidden Network": 6}})

    assert out["label"] == "Hidden Network #7"


def test_fan_growth_ranks_subscribers_per_thousand_views():
    payload = build_fan_growth([
        {
            "video_id": "a",
            "title": "A",
            "category": "fungi",
            "story_format": "hidden_network",
            "analytics": {"views": 1000, "subscribersGained": 5, "comments": 20},
        },
        {
            "video_id": "b",
            "title": "B",
            "category": "weather",
            "analytics": {"views": 10000, "subscribersGained": 2, "comments": 10},
        },
    ], [{"author": "Ada"}, {"author": "Ada"}])

    assert payload["videos_ranked_by_subs_per_1k"][0]["video_id"] == "a"
    assert payload["recurring_commenters"][0]["author"] == "Ada"
