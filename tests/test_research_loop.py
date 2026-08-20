from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from utils.analytics_feedback import age_window, normalized_metrics, sync_catalog_performance
from utils.atomic_state import load_versioned, save_versioned
from utils.experiment_engine import Experiment, Hypothesis, record_experiment, record_hypothesis, record_result
from utils.research_cycle import run_research_cycle


@pytest.mark.parametrize(
    "hours,expected",
    [(0.5, "early"), (2, "1h"), (8, "6h"), (30, "24h"), (100, "72h"), (400, "mature")],
)
def test_age_windows_are_non_overlapping(hours, expected):
    published = datetime(2026, 1, 1, tzinfo=UTC)
    observed = published + timedelta(hours=hours)
    assert age_window(published.isoformat(), observed.isoformat()) == expected


def test_normalized_metrics_do_not_invent_unavailable_api_fields():
    result = normalized_metrics({"views": 100, "likes": 4, "comments": 1, "duration": "PT1M30S"})
    assert result["duration_seconds"] == 90
    assert result["engagement_rate"] == 0.05
    assert "impressions_ctr" not in result
    assert "subscriber_conversion" not in result


def test_catalog_feedback_matches_content_id_and_computes_fitness(tmp_path):
    catalog = [
        {
            "content_id": "lw_one",
            "kind": "short",
            "visual_dna": {"novelty": {"recent_distance": 0.4}},
            "performance_windows": {},
        }
    ]
    save_versioned(tmp_path / "catalog_memory.json", catalog, 1)
    stats = [
        {
            "video_id": "yt1",
            "views": 250,
            "likes": 10,
            "comments": 2,
            "duration": "PT30S",
            "published_at": "2026-01-01T00:00:00+00:00",
            "averageViewPercentage": 75,
            "viewedPercentage": 70,
        }
    ]
    summary = sync_catalog_performance(
        tmp_path,
        stats,
        {"yt1": {"content_id": "lw_one"}},
        observed_at="2026-01-01T02:00:00+00:00",
    )
    assert summary == {"matched": 1, "unmatched": 0, "updated": 1}
    updated = load_versioned(tmp_path / "catalog_memory.json", 1, {}, [])[0]
    assert updated["youtube_video_id"] == "yt1"
    assert updated["performance_windows"]["1h"]["views"] == 250
    assert updated["fitness"]["model"] == "short_v1"
    assert updated["fitness"]["confidence"] < 1
    assert updated["fitness_window"] == "1h"
    assert updated["fitness_observed_at"] == "2026-01-01T02:00:00+00:00"


def test_catalog_feedback_refuses_phantom_creations(tmp_path):
    save_versioned(tmp_path / "catalog_memory.json", [], 1)
    summary = sync_catalog_performance(
        tmp_path,
        [{"video_id": "unknown", "views": 1}],
        {},
        observed_at="2026-01-01T00:00:00+00:00",
    )
    assert summary["unmatched"] == 1
    assert load_versioned(tmp_path / "catalog_memory.json", 1, {}, []) == []


def test_experiment_ledger_enforces_one_variable_and_tracks_evidence(tmp_path):
    ledger = tmp_path / "research.json"
    hypothesis = Hypothesis(
        statement="A reveal opening improves short retention",
        independent_variable="temporal.opening_strategy",
        dependent_metric="average_percentage_viewed",
        expected_direction="increase",
        rationale="Opening activity is observable in visual DNA.",
    )
    hypothesis_id = record_hypothesis(ledger, hypothesis)
    experiment = Experiment(
        hypothesis_id=hypothesis_id,
        control_content_ids=("lw_a",),
        treatment_content_ids=("lw_b",),
        changed_variables={"temporal.opening_strategy": ["collapse", "reveal"]},
        format="short",
        target_window="72h",
    )
    experiment_id = record_experiment(ledger, experiment)
    assert record_result(ledger, experiment_id, effect=0.08, samples=12, confidence=0.8) == "supported"
    data = load_versioned(ledger, 1, {}, {})
    assert data["hypotheses"][hypothesis_id]["status"] == "supported"
    assert data["experiments"][experiment_id]["result"]["effect"] == 0.08


def test_experiment_rejects_confounded_design():
    with pytest.raises(ValueError, match="exactly one"):
        Experiment(
            hypothesis_id="hyp_1",
            control_content_ids=("a",),
            treatment_content_ids=("b",),
            changed_variables={"geometry": 1, "title": 2},
            format="short",
            target_window="24h",
        )


def test_research_cycle_refuses_to_manufacture_hypotheses_without_data(tmp_path):
    report = run_research_cycle(tmp_path)
    assert report["data_status"] == "insufficient_data"
    assert report["proposed_hypothesis_ids"] == []
    assert (tmp_path / "research_report.json").exists()
    assert "Insufficient" in (tmp_path / "research_report.md").read_text(encoding="utf-8")


def test_research_cycle_proposes_traceable_noncausal_hypothesis(tmp_path):
    catalog = []
    for index in range(10):
        value = index / 10
        catalog.append(
            {
                "content_id": f"lw_{index}",
                "kind": "short",
                "fitness_window": "72h",
                "genome": {"family": "orb" if index % 2 else "ribbon"},
                "fitness": {"score": value, "confidence": 0.8},
                "visual_dna": {
                    "composition": {"screen_fill": value, "symmetry": 0.5, "entropy": 0.4},
                    "motion": {"optical_flow_mean": value},
                    "appearance": {"brightness": value, "saturation": 0.3},
                    "temporal": {"opening_activity": value},
                },
            }
        )
    save_versioned(tmp_path / "catalog_memory.json", catalog, 1)
    report = run_research_cycle(tmp_path)
    assert report["data_status"] == "sufficient_for_hypotheses"
    assert report["proposed_hypothesis_ids"]
    assert all(signal["causal"] is False for signal in report["correlations"])
    assert all(signal["format"] == "short" and signal["window"] == "72h" for signal in report["correlations"])
    ledger = load_versioned(tmp_path / "research_ledger.json", 1, {}, {})
    assert report["proposed_hypothesis_ids"][0] in ledger["hypotheses"]


def test_research_never_mixes_formats_or_maturity_windows(tmp_path):
    catalog = []
    for index in range(14):
        catalog.append(
            {
                "content_id": f"lw_{index}",
                "kind": "short" if index % 2 else "long",
                "fitness_window": "24h" if index % 3 else "72h",
                "fitness": {"score": index / 14, "confidence": 0.8},
                "visual_dna": {
                    "composition": {"screen_fill": index / 14, "symmetry": 0.5, "entropy": 0.4},
                    "motion": {"optical_flow_mean": index / 14},
                    "appearance": {"brightness": index / 14, "saturation": 0.3},
                    "temporal": {"opening_activity": index / 14},
                },
            }
        )
    save_versioned(tmp_path / "catalog_memory.json", catalog, 1)
    report = run_research_cycle(tmp_path)
    assert report["correlations"] == []
    assert report["data_status"] == "insufficient_data"
