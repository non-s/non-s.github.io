from utils.growth_engine import (
    analyze_retention,
    build_format_memory,
    detect_weak_content,
    experiment_plan,
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


def test_packaging_selector_hides_rejected_title_variants():
    selected = select_best_packaging(_story(
        title="Chickens rely on head movement to signal",
        seo_title="Chickens rely on head movement to signal",
        hook="Chickens rely on head movement before the move.",
        thumbnail_text="CHICKEN HEAD",
        category="farm",
    ))

    titles = [row["title"] for row in selected["top_variants"]]
    assert all("signal the next move with movement" not in title.lower() for title in titles)
    assert all("rely on movement to signal" not in title.lower() for title in titles)
    assert all("rely on head movement to signal" not in title.lower() for title in titles)
    assert all("signal the next move with" not in title.lower() for title in titles)
    assert all("this movement changes what" not in title.lower() for title in titles)


def test_format_memory_uses_real_performance_when_available():
    markers = [
        {
            "category": "fungi",
            "story_format": "hidden_network",
            "title": "Mushrooms signal through roots",
            "thumbnail_text": "FUNGAL INTERNET",
            "hook": "Mushrooms signal below the forest.",
            "analytics": {
                "views": 10000,
                "likes": 700,
                "comments": 90,
                "averageViewPercentage": 88,
                "subscribersGained": 40,
            },
        }
        for _ in range(8)
    ]

    memory = build_format_memory(markers)

    assert memory["sample_count"] == 8
    assert memory["category_weights"]["fungi"] > 1
    assert memory["format_weights"]["hidden_network"] > 1


def test_format_memory_does_not_learn_malformed_winning_titles():
    markers = [
        {
            "category": "wildlife",
            "story_format": "body_superpower",
            "title": "Lions use their ears to use",
            "thumbnail_text": "LION EARS",
            "hook": "Lions use their ears to use.",
            "analytics": {"views": 10000, "likes": 800, "comments": 100, "averageViewPercentage": 90},
        },
        {
            "category": "ocean",
            "story_format": "animal_memory",
            "title": "Dolphins recognize signals through call",
            "thumbnail_text": "DOLPHIN CALL",
            "hook": "Dolphins recognize the call.",
            "analytics": {"views": 1000, "likes": 80, "comments": 10, "averageViewPercentage": 70},
        },
    ]

    memory = build_format_memory(markers)

    winning = " ".join(memory["winning_title_patterns"])
    weak = " ".join(memory["weak_patterns"])
    assert "to use" not in winning
    assert "to use" in weak


def test_weak_content_detector_blocks_generic_recycled_packaging():
    weak = detect_weak_content({
        "title": "Animals have another amazing secret",
        "hook": "Animals are amazing.",
        "script": "Animals are amazing. Animals are amazing. Animals are amazing.",
        "thumbnail_text": "AMAZING SECRET TODAY",
        "category": "wildlife",
    })

    assert weak["state"] == "block"
    assert weak["risk"] >= 55


def test_experiment_plan_records_lightweight_assignment():
    plan = experiment_plan(_story(), {"sample_count": 20, "winning_hook_patterns": {"{subject} {action}": 4}})

    assert plan["mode"] in {"explore", "exploit"}
    assert "hook" in plan["assignment"]
