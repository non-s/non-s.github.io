from __future__ import annotations

from utils.candidate_selector import candidate_budget, select_candidate
from utils.creative_models import AudioDNA


def _profile(seed=7):
    return {
        "seed": seed,
        "family": "orb",
        "folds_theta": 3,
        "folds_phi": 5,
        "melt_rate": 0.2,
        "palette": {"base_hue": 0.4},
    }


def test_candidate_budget_is_bounded(monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_CHEAP_CANDIDATES", "999")
    assert candidate_budget("short") == 8
    monkeypatch.setenv("LIQUID_WIRE_CHEAP_CANDIDATES", "0")
    assert candidate_budget("long") == 1


def test_candidate_selection_is_reproducible_and_changes_at_most_one_field(monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_CHEAP_CANDIDATES", "4")
    selected_a, report_a = select_candidate(_profile(), "short", [])
    selected_b, report_b = select_candidate(_profile(), "short", [])
    assert selected_a == selected_b
    assert report_a == report_b
    mutation = report_a["selected"]["mutation"]
    assert set(mutation) == {"field", "before", "after"}
    assert report_a["budget"] == 4


def test_family_saturation_reduces_candidate_score(monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_CHEAP_CANDIDATES", "1")
    catalog = [{"genome": {"family": "orb"}} for _ in range(12)]
    _, saturated = select_candidate(_profile(), "short", catalog)
    _, fresh = select_candidate({**_profile(), "family": "ribbon"}, "short", catalog)
    assert fresh["selected"]["score"] > saturated["selected"]["score"]


def test_rejection_memory_influences_but_cannot_dominate_candidate_score():
    _, report = select_candidate(
        _profile(),
        "short",
        [],
        {"low_motion": 5, "too_similar": 5, "bad_composition": 5},
    )
    assert report["rejection_memory"]["low_motion"] == 5
    assert all(-0.1 <= row["rejection_adjustment"] <= 0.1 for row in report["candidates"])


def test_audio_dna_uses_observed_quality_fingerprint():
    report = {
        "audio_rms_db": -18.0,
        "audio_peak": 0.9,
        "stereo_width": 0.4,
        "audio_channels": 2,
        "silence_ratio": 0.01,
        "sync_signal": 0.7,
        "fingerprint": [0.0] * 28 + [0.1, 0.2, 0.3, 0.4],
    }
    dna = AudioDNA.from_quality_report(report)
    assert dna.loudness["rms_db"] == -18.0
    assert dna.spectral["flux_mean"] == 0.1
    assert dna.spectral["centroid_variance"] == 0.4
    assert len(dna.dna_id) == 24
