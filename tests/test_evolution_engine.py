from __future__ import annotations

import copy

import pytest

from utils.evolution_engine import adaptive_exploration_rate, archive_of_elites, evolve_profile


def _item(index: int, *, family: str = "orb", kind: str = "short", score: float = 0.7) -> dict:
    return {
        "content_id": f"lw_{index}",
        "genome_id": f"genome_{index}",
        "kind": kind,
        "genome": {
            "family": family,
            "generation": index,
            "geometry": {"folds_theta": 3, "folds_phi": 5},
            "motion": {"melt_rate": 0.2},
            "appearance": {"palette": {"base_hue": 0.3}},
            "audio": {"genre": "lofi_ambient"},
        },
        "visual_dna": {"novelty": {"recent_distance": 0.2 + index / 100}},
        "fitness": {"score": score, "confidence": 0.8},
    }


def _profile(seed: int = 10) -> dict:
    return {
        "seed": seed,
        "family": "ribbon",
        "folds_theta": 6,
        "folds_phi": 6,
        "melt_rate": 0.5,
        "palette": {"base_hue": 0.8},
        "music": {"swing": 0.1},
        "genre": "lofi_ambient",
    }


def test_archive_of_elites_is_cell_bounded_and_rejects_low_confidence():
    catalog = [_item(i, family="orb", score=i / 10) for i in range(5)]
    low = _item(9, score=1.0)
    low["fitness"]["confidence"] = 0.01
    elites = archive_of_elites([*catalog, low], per_cell=2)
    assert len(elites) == 2
    assert all(item["content_id"] != "lw_9" for item in elites)


def test_cold_start_explores_aggressively():
    assert adaptive_exploration_rate([]) == 0.8
    assert adaptive_exploration_rate([_item(i) for i in range(20)]) >= 0.5


def test_shadow_mode_records_decision_without_mutating_profile():
    profile = _profile()
    before = copy.deepcopy(profile)
    decision = evolve_profile(profile, "short", [_item(1)], mode="shadow")
    assert decision.parent_content_id == "lw_1"
    assert decision.mutation is not None
    assert decision.applied is False
    assert profile == before


def test_active_mode_inherits_and_applies_exactly_one_bounded_mutation():
    profile = _profile()
    decision = evolve_profile(profile, "short", [_item(1)], mode="active")
    assert decision.applied is True
    assert profile["generation"] == 2
    assert profile["parents"] == ["lw_1"]
    assert len(profile["mutations"]) == 1
    assert decision.mutation.category in {"geometry", "motion", "appearance", "audio"}
    assert decision.mutation.before != decision.mutation.after


def test_invalid_mode_falls_back_to_shadow(monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_EVOLUTION_MODE", "reckless")
    decision = evolve_profile(_profile(), "short", [_item(1)])
    assert decision.mode == "shadow"


@pytest.mark.parametrize("seed", range(20))
def test_canary_applies_to_exactly_ten_percent_by_seed(seed):
    decision = evolve_profile(_profile(seed), "short", [_item(1)], mode="canary")
    assert decision.applied is (seed % 10 == 0)
