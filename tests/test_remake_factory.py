from utils.remake_factory import append_remakes_to_queue, build_remake_story


def test_build_remake_story_is_queue_compatible():
    story = build_remake_story({
        "source_video_id": "abc",
        "source_title": "Ducklings know math before they can swim",
        "views": 1200,
        "growth_score": 500,
    }, generated_at="2026-06-06T00:00:00+00:00")
    assert story["id"].startswith("remake-")
    assert story["consumed"] is False
    assert story["remake_of"]["video_id"] == "abc"
    assert story["hook"]
    assert story["script"].startswith(story["hook"])
    assert story["category"] == "farm"


def test_append_remakes_to_queue_dedupes_source_video():
    queue = {"stories": [{"id": "existing", "remake_of": {"video_id": "abc"}}]}
    updated, created = append_remakes_to_queue(queue, [
        {"source_video_id": "abc", "source_title": "Ducklings know math"},
        {"source_video_id": "def", "source_title": "Cows remember faces"},
    ])
    assert len(created) == 1
    assert created[0]["remake_of"]["video_id"] == "def"
    assert len(updated["stories"]) == 2
