from utils.packaging import package_story


def test_package_story_attaches_world_class_preflight(monkeypatch):
    monkeypatch.setattr("utils.packaging.load_format_memory", lambda: {})
    story = {
        "id": "story-1",
        "category": "ocean",
        "title": "Octopus changes skin before it attacks",
        "hook": "This octopus changes skin before it attacks",
        "thumbnail_text": "Skin warning",
        "script": "This octopus changes skin because the cue warns before the attack.",
        "pexels_download_url": "https://example.test/clip.mp4",
        "yt_tags": ["octopus", "ocean"],
    }

    out = package_story(story)
    packaging = out["packaging"]

    assert packaging["curiosity_gap"]["score"] >= 0
    assert packaging["swipe_risk"]["band"] in {"low", "medium", "high"}
    assert packaging["loop_plan"]["loop_score"] >= 0
    assert "editorial_rulebook" in packaging
