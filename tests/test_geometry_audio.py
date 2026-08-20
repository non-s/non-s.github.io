from __future__ import annotations

from utils.geometry_audio import couple_geometry_to_audio


def test_geometry_to_sound_is_reproducible_bounded_and_traceable():
    profile = {
        "folds_theta": 8,
        "folds_phi": 3,
        "strand_count": 16,
        "melt_rate": 0.7,
        "music": {"key_shift": 3, "density": 0.5, "beat_seconds": 1.0},
    }
    first = couple_geometry_to_audio(profile)
    second = couple_geometry_to_audio(profile)
    assert first == second
    assert first is not profile
    assert -12 <= first["music"]["key_shift"] <= 12
    assert 0.35 <= first["music"]["density"] <= 1.0
    assert 0.5 <= first["music"]["beat_seconds"] <= 1.5
    assert first["music"]["geometry_link"]["version"] == 1
