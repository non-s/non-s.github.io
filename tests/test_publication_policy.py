from __future__ import annotations

from utils.publication_policy import evaluate_publication


def _valid():
    return (
        {"passed": True},
        {
            "sample_count": 12,
            "composition": {"screen_fill": 0.2},
            "novelty": {"recent_distance": 0.1},
        },
        {"loudness": {"rms_db": -18, "peak": 0.9}},
    )


def test_quality_gate_2_passes_objective_validity_and_requires_private_by_default(monkeypatch):
    monkeypatch.delenv("LIQUID_WIRE_PRIVATE_VALIDATION", raising=False)
    decision = evaluate_publication(*_valid())
    assert decision.passed is True
    assert decision.required_privacy == "private"
    assert decision.dimensions["technical"] == "pass"
    assert set(decision.dimensions) == {
        "technical", "visual", "temporal", "novelty", "audio", "puzzle", "experiment"
    }


def test_taste_is_a_review_prompt_not_a_rejection():
    quality, visual, audio = _valid()
    visual["composition"]["screen_fill"] = 0.01
    decision = evaluate_publication(quality, visual, audio)
    assert decision.passed is True
    assert "mobile legibility" in decision.review_prompts[0]


def test_near_duplicate_silence_and_unvalidated_puzzle_block():
    quality, visual, audio = _valid()
    visual["novelty"]["recent_distance"] = 0.001
    audio["loudness"]["rms_db"] = -100
    decision = evaluate_publication(quality, visual, audio, puzzle={"enabled": True, "validated": False})
    assert decision.passed is False
    assert decision.dimensions["novelty"] == "fail"
    assert decision.dimensions["audio"] == "fail"
    assert decision.dimensions["puzzle"] == "fail"


def test_invalid_multi_variable_experiment_blocks_publication():
    decision = evaluate_publication(*_valid(), experiment={"changed_variables": {"motion": 1, "audio": 2}})
    assert decision.passed is False
    assert decision.dimensions["experiment"] == "fail"
