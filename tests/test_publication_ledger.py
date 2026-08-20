import json

from utils.atomic_state import load_versioned
from utils.publication_ledger import publication_receipt, rebuild_publication_state


def _metadata(content_id: str, title: str) -> dict:
    return {
        "content_id": content_id,
        "title": title,
        "scene": "living wire",
        "kind": "short",
        "generated_at": "2026-08-20T10:00:00Z",
        "genome": {"family": "orb", "puzzle": {}},
        "quality_report": {"passed": True},
    }


def test_receipt_is_self_contained() -> None:
    receipt = publication_receipt("video-1", _metadata("lw-1", "Unique Bloom"), uploaded_at="2026-08-20T11:00:00Z")
    assert receipt["video_tag"]["content_id"] == "lw-1"
    assert receipt["catalog_record"]["content_id"] == "lw-1"


def test_rebuild_merges_out_of_order_receipts_idempotently(tmp_path) -> None:
    evidence, data = tmp_path / "evidence", tmp_path / "data"
    for folder, video_id, content_id, title, uploaded in (
        ("new", "v2", "lw-2", "Second Tide", "2026-08-20T12:00:00Z"),
        ("old", "v1", "lw-1", "First Bloom", "2026-08-20T11:00:00Z"),
    ):
        target = evidence / folder
        target.mkdir(parents=True)
        payload = publication_receipt(video_id, _metadata(content_id, title), uploaded_at=uploaded)
        (target / f"publication_receipt_{video_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    first = rebuild_publication_state(evidence, data)
    second = rebuild_publication_state(evidence, data)

    assert first == second == {
        "receipts": 2,
        "legacy_matches": 0,
        "catalog_records": 2,
        "video_tags": 2,
        "experiment_assignments": 0,
    }
    catalog = load_versioned(data / "catalog_memory.json", 1, {}, [])
    assert {row["content_id"] for row in catalog} == {"lw-1", "lw-2"}
    assert set(json.loads((data / "video_tags.json").read_text())) == {"v1", "v2"}
    assert json.loads((data / "used_titles.json").read_text()) == ["Second Tide", "First Bloom"]


def test_rebuild_bootstraps_pre_receipt_metadata_from_title_and_time(tmp_path) -> None:
    evidence, data = tmp_path / "evidence", tmp_path / "data"
    evidence.mkdir()
    metadata = _metadata("lw-old", "Historic Bloom")
    (evidence / "liquid_wire_short.json").write_text(json.dumps(metadata), encoding="utf-8")
    data.mkdir()
    (data / "analytics.json").write_text(json.dumps({"all_videos": [{
        "video_id": "youtube-old",
        "title": "Historic Bloom",
        "published_at": "2026-08-20T10:04:00Z",
    }]}), encoding="utf-8")

    result = rebuild_publication_state(evidence, data)

    assert result["legacy_matches"] == 1
    assert json.loads((data / "video_tags.json").read_text())["youtube-old"]["content_id"] == "lw-old"


def test_rebuild_refuses_ambiguous_legacy_match(tmp_path) -> None:
    evidence, data = tmp_path / "evidence", tmp_path / "data"
    evidence.mkdir()
    for index, generated in enumerate(("2026-08-20T10:00:00Z", "2026-08-20T10:05:00Z")):
        metadata = _metadata(f"lw-{index}", "Repeated Title")
        metadata["generated_at"] = generated
        (evidence / f"candidate-{index}.json").write_text(json.dumps(metadata), encoding="utf-8")
    data.mkdir()
    (data / "analytics.json").write_text(json.dumps({"all_videos": [{
        "video_id": "youtube-ambiguous",
        "title": "Repeated Title",
        "published_at": "2026-08-20T10:03:00Z",
    }]}), encoding="utf-8")

    result = rebuild_publication_state(evidence, data)

    assert result["legacy_matches"] == 0


def test_rebuild_recovers_causal_cohort_from_self_contained_receipt(tmp_path) -> None:
    evidence, data = tmp_path / "evidence", tmp_path / "data"
    evidence.mkdir()
    metadata = _metadata("lw-treatment", "Measured Melt")
    metadata.update(
        {
            "experiment_id": "exp-1",
            "hypothesis_id": "hyp-1",
            "experiment_variant": "treatment",
            "experiment": {
                "experiment_id": "exp-1",
                "hypothesis_id": "hyp-1",
                "variant": "treatment",
                "changed_variables": {
                    "genome.motion.melt_rate": {"operation": "multiply", "factor": 1.2}
                },
                "target_window": "72h",
                "hypothesis": {
                    "statement": "Melt rate improves fitness",
                    "independent_variable": "genome.motion.melt_rate",
                    "dependent_metric": "fitness.score",
                    "expected_direction": "increase",
                    "rationale": "Observed cohort",
                    "status": "planned",
                    "samples": 0,
                    "confidence": 0.0,
                },
            },
        }
    )
    receipt = publication_receipt("video-1", metadata, uploaded_at="2026-08-20T11:00:00Z")
    (evidence / "publication_receipt_video-1.json").write_text(json.dumps(receipt), encoding="utf-8")

    first = rebuild_publication_state(evidence, data)
    second = rebuild_publication_state(evidence, data)

    assert first["experiment_assignments"] == second["experiment_assignments"] == 1
    ledger = load_versioned(data / "research_ledger.json", 1, {}, {})
    assert ledger["experiments"]["exp-1"]["treatment_content_ids"] == ["lw-treatment"]
    assert ledger["hypotheses"]["hyp-1"]["independent_variable"] == "genome.motion.melt_rate"
