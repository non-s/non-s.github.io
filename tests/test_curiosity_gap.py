from utils.curiosity_gap import CuriosityGapEngine


def test_specific_hook_beats_generic_hook():
    engine = CuriosityGapEngine()
    story = {
        "animal": "octopus",
        "category": "ocean",
        "pexels_download_url": "https://example.test/clip.mp4",
    }
    generic = engine.score_candidate(
        engine.build_candidates({"hook_seed": "This animal is amazing"})[0],
        story,
        {"recent_hooks": []},
    )
    specific = engine.score_candidate(
        engine.build_candidates({"hook_seed": "This octopus changes skin before it attacks"})[0],
        story,
        {"recent_hooks": []},
    )

    assert specific > generic


def test_recent_hook_overlap_is_penalized():
    engine = CuriosityGapEngine()
    story = {"category": "ocean", "pexels_download_url": "clip.mp4"}
    candidate = engine.build_candidates({"hook_seed": "This octopus changes skin before it attacks"})[0]

    fresh = engine.score_candidate(candidate, story, {"recent_hooks": []})
    repeated = engine.score_candidate(candidate, story, {"recent_hooks": [candidate.hook]})

    assert repeated < fresh
