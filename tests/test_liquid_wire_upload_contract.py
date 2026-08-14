from __future__ import annotations

from upload_youtube import _production_contract_issues


def _approved_metadata() -> dict:
    return {
        "visual_source": "procedural_python",
        "audio_source": "synthetic_python",
        "generator_profile": {"engine_version": "2.1"},
        "quality_report": {
            "passed": True,
            "issues": [],
            "fingerprint": [0.1] * 20,
        },
    }


def test_production_contract_accepts_engine_2_1_evidence() -> None:
    assert _production_contract_issues(_approved_metadata()) == []


def test_production_contract_rejects_external_or_unverified_assets() -> None:
    metadata = _approved_metadata()
    metadata["audio_source"] = "downloaded_music"
    metadata["quality_report"]["passed"] = False
    issues = _production_contract_issues(metadata)
    assert "audio_source_not_procedural" in issues
    assert "quality_gate_not_approved" in issues


def test_production_contract_rejects_old_engine_and_missing_fingerprint() -> None:
    metadata = _approved_metadata()
    metadata["generator_profile"]["engine_version"] = "2.0"
    metadata["quality_report"]["fingerprint"] = []
    issues = _production_contract_issues(metadata)
    assert "engine_version_below_2_1" in issues
    assert "perceptual_fingerprint_missing" in issues
