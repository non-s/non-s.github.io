from __future__ import annotations

from utils.atomic_state import save_versioned
from utils.long_form_policy import eligible_long_form_families, long_form_eligible


def _short(index, score=0.7, confidence=0.8, window="72h"):
    return {
        "content_id": f"lw_{index}",
        "kind": "short",
        "genome": {"family": "orb"},
        "fitness": {"score": score, "confidence": confidence},
        "performance_windows": {window: {"views": 100}},
    }


def test_long_form_requires_two_mature_confident_short_replications(tmp_path):
    save_versioned(tmp_path / "catalog_memory.json", [_short(1)], 1)
    assert long_form_eligible(tmp_path) is False
    save_versioned(tmp_path / "catalog_memory.json", [_short(1), _short(2)], 1)
    assert long_form_eligible(tmp_path) is True
    assert eligible_long_form_families(tmp_path)["orb"]["replications"] == 2


def test_early_or_low_confidence_signals_do_not_promote_long_form(tmp_path):
    catalog = [_short(1, confidence=0.1), _short(2, window="24h"), _short(3, score=0.2)]
    save_versioned(tmp_path / "catalog_memory.json", catalog, 1)
    assert eligible_long_form_families(tmp_path) == {}
