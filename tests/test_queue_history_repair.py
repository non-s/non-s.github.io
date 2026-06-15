from scripts.repair_queue_history import repair_story


def test_repair_story_preserves_upload_state_for_consumed_records():
    story = {
        "id": "old-forest",
        "title": "Forests read the moment from one leaves",
        "seo_title": "Forests read the moment from one leaves",
        "hook": "Forests reveal one visible signal",
        "script": (
            "Forests reveal one visible signal. Watch the leaves, because forests use it "
            "to send a clear signal before the next move. Now the forests at the start makes sense."
        ),
        "thumbnail_text": "FORESTS LEAVES",
        "category": "forests",
        "consumed": True,
        "uploaded_video_id": "abc123",
        "consumed_at": "2026-06-13T00:00:00+00:00",
    }

    repaired, issues, applied = repair_story(story)

    assert applied is True
    assert "awkward_uncountable_one_cue" in issues
    assert repaired["consumed"] is True
    assert repaired["uploaded_video_id"] == "abc123"
    assert repaired["consumed_at"] == "2026-06-13T00:00:00+00:00"
    assert repaired["title"] == "Forests make cooler air under the canopy"
    assert "forests use it" not in repaired["script"].lower()
    assert "one leaves" not in str(repaired.get("packaging", "")).lower()
    assert "cute behavior" not in str(repaired.get("youtube_brain", "")).lower()
    assert repaired["history_repair"]["previous_title_had_issues"] is True
