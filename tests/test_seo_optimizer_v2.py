import json

from scripts.seo_metadata_lint import lint_repo
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


def test_metadata_lint_does_not_call_physical_nature_animal_missing():
    lint = lint_metadata(
        {
            "title": "Lightning turns air into a shock wave",
            "description": "A weather fact. #Shorts #NatureFacts #WildBrief",
            "tags": ["lightning", "weather", "science"],
            "category": "weather",
            "subject": "lightning",
        }
    )

    assert lint["approved"] is True
    assert "animal_not_front_loaded" not in lint["warnings"]


def test_optimise_story_keeps_seo_lint_compatible_title():
    story = optimise_story({"title": "why cats purr at night", "category": "cats"})

    assert story["title"].startswith("Cats")


def test_seo_lint_includes_pending_queue_with_rendered_hashtag_shape(tmp_path):
    data = tmp_path / "_data"
    data.mkdir()
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "short-demo.done").write_text(
        json.dumps(
            {
                "title": "Sharks sense tiny electric fields",
                "description": "A nature fact. #Shorts #NatureFacts #WildBrief",
                "tags": ["sharks", "science", "nature"],
            }
        ),
        encoding="utf-8",
    )
    (data / "stories_queue.json").write_text(
        json.dumps(
            {
                "stories": [
                    {
                        "id": "pending-shark",
                        "title": "Sharks follow one fin cue before the payoff",
                        "seo_title": "Sharks follow one fin cue before the payoff",
                        "description": "A shark short.",
                        "category": "ocean",
                        "yt_tags": ["sharks", "ocean", "animal facts"],
                        "discovery_hashtags": ["ocean", "sharks", "animalfacts", "nature"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = lint_repo(tmp_path)
    pending = [item for item in payload["items"] if item.get("kind") == "pending"]

    assert payload["pending_checked"] == 1
    assert payload["uploaded_checked"] == 1
    assert payload["items"][0]["path"] == "_videos/short-demo.done"
    assert pending[0]["errors"] == []
    assert "missing_shorts_hashtag" not in pending[0]["warnings"]
    assert "thin_tag_set" not in pending[0]["warnings"]
