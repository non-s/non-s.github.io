from utils.growth_engine import (
    analyze_retention,
    generate_packaging_options,
    score_topic,
    select_best_packaging,
)


def _story(**overrides):
    story = {
        "title": "Mushrooms talk through underground threads",
        "seo_title": "Mushrooms talk through underground threads",
        "hook": "Mushrooms signal through underground threads.",
        "script": (
            "Mushrooms signal through underground threads. Watch the tiny caps, "
            "because the real action is below them. Mycelium moves nutrients and "
            "warnings through soil. That is why one forest can behave like a network. "
            "What should we decode next?"
        ),
        "thumbnail_text": "FUNGAL INTERNET",
        "category": "fungi",
        "yt_tags": ["mushrooms", "mycelium", "forest network"],
    }
    story.update(overrides)
    return story


def test_score_topic_returns_opportunity_breakdown():
    out = score_topic(_story())

    assert out["score"] >= 64
    assert out["verdict"] in {"produce", "scale"}
    assert {"viral_potential", "visual_potential", "replay_potential"} <= set(out["signals"])


def test_retention_analyzer_flags_weak_scripts():
    weak = analyze_retention(_story(
        hook="Did you know nature is amazing?",
        script="Did you know nature is amazing? It is interesting.",
    ))

    assert weak["verdict"] in {"rewrite", "discard"}
    assert "hook_below_threshold" in weak["reasons"]


def test_packaging_generates_required_option_counts():
    options = generate_packaging_options(_story())

    assert len(options["titles"]) == 10
    assert len(options["thumbnail_texts"]) == 10
    assert len(options["hooks"]) == 5


def test_packaging_selector_returns_scored_variants():
    selected = select_best_packaging(_story())

    assert selected["best"]["score"] > 0
    assert len(selected["top_variants"]) == 10
