from __future__ import annotations

from utils.strategy_intelligence import (
    creative_map,
    experiment_meta_learning,
    lineage_graph,
    pareto_frontier,
    value_of_information,
)


def _item(index, score, novelty, confidence=0.8):
    return {
        "content_id": f"lw_{index}",
        "fitness": {"score": score, "confidence": confidence},
        "visual_dna": {
            "novelty": {"recent_distance": novelty},
            "composition": {"screen_fill": index / 10, "entropy": (index % 3) / 2},
            "motion": {"optical_flow_mean": (index % 4) / 3},
        },
        "genome": {"generation": index, "family": "orb", "parents": [f"lw_{index - 1}"] if index else []},
    }


def test_pareto_keeps_tradeoff_winners_not_one_global_score():
    catalog = [_item(1, 0.9, 0.2), _item(2, 0.6, 0.9), _item(3, 0.5, 0.1)]
    assert pareto_frontier(catalog) == ["lw_1", "lw_2"]


def test_creative_map_requires_evidence_then_exposes_empty_regions():
    assert creative_map([_item(1, 0.5, 0.5)])["status"] == "insufficient_data"
    result = creative_map([_item(index, 0.5, 0.5) for index in range(8)])
    assert result["status"] == "ready"
    assert result["axes"] == ["density", "motion", "complexity"]
    assert result["empty_cells"]


def test_value_of_information_rewards_uncertainty_and_novelty_but_is_bounded():
    exploratory = value_of_information(uncertainty=1, novelty=1, expected_performance=0)
    exploitative = value_of_information(uncertainty=0, novelty=0, expected_performance=1)
    assert 0 <= exploitative < exploratory <= 1


def test_lineage_graph_preserves_unresolved_historical_parents():
    graph = lineage_graph([_item(3, 0.5, 0.5)])
    assert graph["nodes"][0]["generation"] == 3
    assert graph["edges"] == [{"from": "lw_2", "to": "lw_3", "resolved": "false"}]


def test_meta_learning_measures_decisive_experiment_yield():
    ledger = {
        "experiments": {
            "a": {"changed_variables": {"motion": [1, 2]}, "result": {"status": "supported"}},
            "b": {"changed_variables": {"motion": [2, 3]}, "result": {"status": "inconclusive"}},
        }
    }
    summary = experiment_meta_learning(ledger)
    assert summary["variables"]["motion"] == {"experiments": 2, "decisive": 1, "learning_yield": 0.5}
