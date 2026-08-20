from __future__ import annotations

import json

import numpy as np
import pytest

from utils.atomic_state import load_versioned, save_versioned
from utils.creative_models import ENGINE_VERSION, Genome, VisualDNA, content_id
from utils.research_engine import compute_fitness, hypothesis_status
from utils.visual_intelligence import analyze_visual_dna


def _profile() -> dict:
    return {
        "seed": 42,
        "family": "orb",
        "folds_theta": 3,
        "folds_phi": 5,
        "melt_rate": 0.2,
        "palette": {"base_hue": 0.4},
        "timeline": [{"kind": "reveal", "start": 0, "duration": 1}],
        "composition": {"mode": "dorian"},
    }


def test_genome_is_reproducible_and_separate_from_observation():
    first = Genome.from_profile(_profile(), "short")
    second = Genome.from_profile(_profile(), "short")
    assert first.genome_id == second.genome_id
    assert first.version == 1
    assert ENGINE_VERSION
    dna = VisualDNA({}, {}, {}, {}, {"fingerprint": []}, 3)
    assert content_id(first, dna).startswith("lw_")
    assert "brightness" not in first.to_dict()


def test_visual_dna_observes_frames(monkeypatch, tmp_path):
    frames = []
    for position in (15, 30, 45, 60):
        frame = np.zeros((80, 120, 3), dtype=np.uint8)
        frame[20:60, position : position + 20] = (20, 120, 240)
        frames.append(frame)
    monkeypatch.setattr("utils.visual_intelligence._sampled_frames", lambda path, samples: frames)
    dna = analyze_visual_dna(tmp_path / "final.mp4")
    assert dna is not None
    assert dna.sample_count == 4
    assert dna.motion["frame_difference_mean"] > 0
    assert dna.appearance["saturation"] > 0
    assert len(dna.novelty["fingerprint"]) == 21


def test_versioned_state_is_atomic_migratable_and_backed_up(tmp_path):
    path = tmp_path / "memory.json"
    save_versioned(path, {"items": [1]}, 1)
    save_versioned(path, {"items": [1, 2]}, 1)
    assert path.with_suffix(".json.bak").exists()
    assert load_versioned(path, 2, {1: lambda data: {**data, "migrated": True}}, {})["migrated"] is True
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1


def test_versioned_state_rejects_legacy_payload(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="unversioned"):
        load_versioned(path, 1, {}, [])


def test_catalog_memory_is_bounded_and_versioned(monkeypatch, tmp_path):
    import utils.creative_memory as memory

    monkeypatch.setattr(memory, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(memory, "CATALOG_LIMIT", 2)
    for index in range(3):
        memory.record_creation({"content_id": f"lw_{index}", "kind": "short"})
    catalog = memory.load_catalog()
    assert [item["content_id"] for item in catalog] == ["lw_1", "lw_2"]
    assert json.loads((tmp_path / "catalog_memory.json").read_text())["schema_version"] == 1


def test_fitness_models_are_distinct_explainable_and_uncertain():
    metrics = {
        "views": 100,
        "average_percentage_viewed": 75,
        "viewed_percentage": 70,
        "impressions_ctr": 0.08,
        "average_view_duration_seconds": 300,
        "duration_seconds": 600,
        "engagement_rate": 0.04,
        "subscriber_conversion": 0.01,
    }
    short = compute_fitness(metrics, "short", novelty=0.8)
    long = compute_fitness(metrics, "long", novelty=0.8)
    assert short.model != long.model
    assert short.weights != long.weights
    assert 0 < short.score <= 1
    assert short.confidence < 1
    assert hypothesis_status(0.2, 3, 0.9) == "insufficient_data"
    assert hypothesis_status(0.2, 20, 0.9) == "supported"
    assert hypothesis_status(-0.2, 20, 0.9) == "contradicted"
