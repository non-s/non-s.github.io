from __future__ import annotations

from upload_youtube import _build_upload_body, _production_contract_issues


def _approved_metadata() -> dict:
    return {
        "title": "A Shape Dreaming in Color",
        "description": "Original procedural generative art and music made with code.",
        "visual_source": "procedural_python",
        "audio_source": "synthetic_python",
        "generator_profile": {"engine_version": "2.1"},
        "quality_report": {
            "passed": True,
            "issues": [],
            "fingerprint": [0.1] * 32,
        },
    }


def test_production_contract_accepts_engine_2_1_evidence() -> None:
    assert _production_contract_issues(_approved_metadata()) == []


def test_production_contract_accepts_legacy_20_dim_fingerprint() -> None:
    metadata = _approved_metadata()
    metadata["quality_report"]["fingerprint"] = [0.1] * 20
    assert _production_contract_issues(metadata) == []


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


def test_production_contract_rejects_wrong_dim_fingerprint() -> None:
    metadata = _approved_metadata()
    metadata["quality_report"]["fingerprint"] = [0.1] * 25
    issues = _production_contract_issues(metadata)
    assert "perceptual_fingerprint_missing" in issues


def test_engine_4_1_requires_autonomous_evidence_and_governance() -> None:
    metadata = _approved_metadata()
    metadata["generator_profile"]["engine_version"] = "4.1"
    issues = _production_contract_issues(metadata)
    assert "autonomous_identity_missing" in issues
    assert "observed_dna_missing" in issues
    assert "publication_policy_not_approved" in issues


def test_engine_4_1_rejects_misleading_or_unproven_metadata() -> None:
    metadata = _approved_metadata()
    metadata["generator_profile"]["engine_version"] = "4.1"
    metadata["title"] = "You Won't Believe This Viral Shape"
    metadata["description"] = "Pretty colors."
    issues = _production_contract_issues(metadata)
    assert "metadata:misleading_clickbait" in issues
    assert "metadata:procedural_provenance_missing" in issues


def test_engine_4_1_accepts_complete_contract_and_obeys_kill_switch() -> None:
    metadata = _approved_metadata()
    metadata.update(
        {
            "generator_profile": {"engine_version": "4.1"},
            "content_id": "lw_1",
            "genome": {"version": 1},
            "visual_dna": {"version": 1},
            "audio_dna": {"version": 1},
            "publication_readiness": {"passed": True},
            "autonomy_state": {"publication_allowed": True},
        }
    )
    assert _production_contract_issues(metadata) == []
    metadata["autonomy_state"]["publication_allowed"] = False
    assert "publication_kill_switch_active" in _production_contract_issues(metadata)


def test_private_validation_contract_overrides_direct_public_upload() -> None:
    metadata = {"publication_readiness": {"required_privacy": "private"}}
    body, effective, target = _build_upload_body(metadata, "description", "en", "public", None, False)
    assert body["status"]["privacyStatus"] == "private"
    assert effective == "private"
    assert target == ""
