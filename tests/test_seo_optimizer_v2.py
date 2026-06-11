from utils.seo_optimizer import lint_metadata, optimise_story


def test_metadata_lint_flags_generic_title():
    lint = lint_metadata({"title": "Animal fact of the day", "description": "#Shorts", "tags": ["animals"]})

    assert "generic_title" in lint["errors"]
    assert lint["approved"] is False


def test_metadata_lint_accepts_searchable_short_title():
    lint = lint_metadata(
        {
            "title": "Sharks sense tiny electric fields",
            "description": "A nature fact. #Shorts #NatureFacts #WildBrief",
            "tags": ["sharks", "science", "nature"],
        }
    )

    assert lint["approved"] is True


def test_optimise_story_keeps_seo_lint_compatible_title():
    story = optimise_story({"title": "why cats purr at night", "category": "cats"})

    assert story["title"].startswith("Cats")
