from utils.remake_factory import append_remakes_to_queue, build_remake_story
from utils.agency_gate import production_allows
from utils.youtube_brain import creator_premortem


def test_build_remake_story_is_queue_compatible():
    story = build_remake_story(
        {
            "source_video_id": "abc",
            "source_title": "Ducklings know math before they can swim",
            "views": 1200,
            "growth_score": 500,
        },
        generated_at="2026-06-06T00:00:00+00:00",
    )
    assert story["id"].startswith("remake-")
    assert story["consumed"] is False
    assert story["remake_of"]["video_id"] == "abc"
    assert story["hook"]
    assert story["script"].startswith(story["hook"])
    assert "original topic" not in story["script"].lower()
    assert "remake" not in story["script"].lower()
    assert story["seo_title"] == "Ducklings compare groups before they swim"
    assert "number sense" in story["script"]
    assert "remake" not in story["description"].lower()
    assert "proven wild brief topic" not in story["yt_description"].lower()
    assert story["category"] == "farm"
    approved, reasons, _checks = production_allows(story)
    assert approved is True
    assert reasons == []


def test_feeding_remake_has_action_and_scannable_thumbnail():
    story = build_remake_story(
        {
            "source_video_id": "goat1",
            "source_title": "Baby goats love bottle feeding",
            "views": 1200,
            "growth_score": 200,
        },
        generated_at="2026-06-06T00:00:00+00:00",
    )

    assert story["seo_title"] == "Goats learn feeding routines fast"
    assert "voices, smells" in story["script"]
    assert len(story["thumbnail_text"].split()) <= 4
    assert creator_premortem(story)["state"] == "publish_minded"


def test_remake_factory_rejects_bad_suggested_hook_grammar():
    story = build_remake_story(
        {
            "source_video_id": "tiger1",
            "source_title": "Tigers never roar at their prey",
            "retention_surgery": {"suggested_hook": "Tigers changes for one visible reason."},
            "views": 1200,
            "growth_score": 200,
        },
        generated_at="2026-06-06T00:00:00+00:00",
    )

    assert story["hook"] == "Tigers use stripes to break up their outline."
    assert "Tigers changes" not in story["script"]


def test_append_remakes_to_queue_dedupes_source_video():
    queue = {"stories": [{"id": "existing", "remake_of": {"video_id": "abc"}}]}
    updated, created = append_remakes_to_queue(
        queue,
        [
            {"source_video_id": "abc", "source_title": "Ducklings know math"},
            {"source_video_id": "def", "source_title": "Cows remember faces"},
        ],
    )
    assert len(created) == 1
    assert created[0]["remake_of"]["video_id"] == "def"
    assert len(updated["stories"]) == 2


def test_append_remakes_to_queue_dedupes_existing_source_url():
    queue = {
        "stories": [
            {
                "id": "existing",
                "source_url": "https://www.youtube.com/shorts/abc",
                "url": "https://www.youtube.com/shorts/abc",
                "seo_title": "Goats reveal one body clue",
                "title": "Goats reveal one body clue",
                "category": "farm",
                "script": "Goats reveal one body clue because the movement shows the payoff.",
            }
        ]
    }

    updated, created = append_remakes_to_queue(
        queue,
        [
            {"source_video_id": "abc", "source_title": "Goats reveal one body clue"},
        ],
    )

    assert created == []
    assert len(updated["stories"]) == 1


def test_append_remakes_to_queue_dedupes_existing_angle():
    existing = build_remake_story(
        {
            "source_video_id": "cow-pexels",
            "source_title": "Cows remember faces for years",
        },
        generated_at="2026-06-06T00:00:00+00:00",
    )
    existing["source_url"] = "https://www.pexels.com/video/cow-1/"
    existing["url"] = "https://www.pexels.com/video/cow-1/"
    queue = {"stories": [existing]}

    updated, created = append_remakes_to_queue(
        queue,
        [
            {"source_video_id": "def", "source_title": "Cows remember faces for years"},
        ],
    )

    assert created == []
    assert len(updated["stories"]) == 1


def test_append_remakes_skips_new_animal_request_without_alternate_subject():
    updated, created = append_remakes_to_queue(
        {"stories": []},
        [
            {
                "source_video_id": "cow1",
                "source_title": "Cows remember faces for years",
                "action": "make sequel with a new animal in the same story shape",
                "instructions": ["Use a different animal or a visibly different angle when possible."],
            }
        ],
    )

    assert created == []
    assert updated["stories"] == []


def test_rebuilding_existing_remake_preserves_operational_annotations():
    queue = {
        "stories": [
            {
                "id": "existing",
                "production_mode": "remake_factory",
                "remake_of": {"video_id": "tiger1", "title": "Tigers never roar at their prey"},
                "autonomy": {"priority": 130, "state": "publish_ready"},
                "queue_prune": {"state": "publish_ready", "score": 100},
                "publish_score": {"approved": True, "state": "publish_ready", "score": 95},
            }
        ]
    }

    updated, created = append_remakes_to_queue(
        queue,
        [
            {
                "source_video_id": "tiger1",
                "source_title": "Tigers never roar at their prey",
                "retention_surgery": {"suggested_hook": "Tigers changes for one visible reason."},
            }
        ],
    )

    story = updated["stories"][0]
    assert created == []
    assert story["id"] == "existing"
    assert story["autonomy"]["priority"] == 130
    assert story["queue_prune"]["state"] == "publish_ready"
    assert story["publish_score"]["score"] == 95
    assert "Tigers changes" not in story["script"]
