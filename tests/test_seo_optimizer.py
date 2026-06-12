"""Tests for deterministic Shorts SEO polishing."""

from utils.seo_optimizer import optimise_story, optimise_title, seo_score


def test_optimise_title_frontloads_animal_from_why_title():
    title = optimise_title(
        "Why cats play like this — it's not just fun",
        hook="Cats practice hunting through play.",
        tags=["cats", "play behavior"],
    )
    assert title.startswith("Cats ")
    assert not title.lower().startswith("why ")
    assert len(title) <= 60


def test_seo_score_rewards_frontloaded_animal():
    strong = seo_score("Dolphins call each other by name")
    weak = seo_score("Why dolphins call each other by name")
    assert strong["score"] > weak["score"]
    assert "animal_not_front_loaded" in weak["issues"]


def test_optimise_story_records_before_and_after():
    story = optimise_story(
        {
            "title": "Why dogs wag tails — it's not just happiness",
            "hook": "Dogs wag tails for more than happiness.",
            "yt_tags": ["dogs", "tail wagging"],
            "category": "dogs",
        }
    )
    assert story["title"].startswith("Dogs ")
    assert story["seo_title"] == story["title"]
    assert story["seo_optimisation"]["applied"] is True


def test_optimise_title_removes_redundant_category_prefix():
    title = optimise_title(
        "Birds This black bird's ear tufts aren't ears at all",
        hook="This black bird's ear tufts are feathers.",
        tags=["birds"],
    )
    assert title.startswith("This black bird")
    assert not title.startswith("Birds This")


def test_optimise_title_cleans_duplicate_animal_prefix():
    title = optimise_title(
        "Horses White horses and how they see in color",
        hook="White horses can see colors differently.",
        tags=["horses"],
    )
    assert title.startswith("White horses")
    assert not title.startswith("Horses White horses")
