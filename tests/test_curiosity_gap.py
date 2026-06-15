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


def test_plural_subject_templates_use_plural_grammar():
    engine = CuriosityGapEngine()
    hooks = [
        item.hook
        for item in engine.build_candidates({"category": "forests", "action": "changes", "cue": "leaf movement"})
    ]
    joined = " | ".join(hooks).lower()

    assert "this forests changes" not in joined
    assert "these forests change after the leaf movement" in joined
    assert "why do these forests change after the leaf movement" in joined
    assert "payoff" not in joined
