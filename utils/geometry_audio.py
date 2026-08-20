"""Deterministic, bounded coupling from visual geometry into music intent."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

GEOMETRY_AUDIO_VERSION = 1


def couple_geometry_to_audio(profile: dict[str, Any]) -> dict[str, Any]:
    """Blend geometry into existing music parameters without replacing composition."""
    result = copy.deepcopy(profile)
    music = result.setdefault("music", {})
    folds_theta = int(result.get("folds_theta", 3))
    folds_phi = int(result.get("folds_phi", 3))
    strands = int(result.get("strand_count", 8))
    melt_rate = float(result.get("melt_rate", 0.2))
    base_key = int(music.get("key_shift", 0))
    interval = (folds_theta - folds_phi) % 5 - 2
    music["key_shift"] = int(np.clip(base_key + interval, -12, 12))
    base_density = float(music.get("density", 0.7))
    music["density"] = round(float(np.clip(0.7 * base_density + 0.3 * strands / 16.0, 0.35, 1.0)), 6)
    base_beat = float(music.get("beat_seconds", 0.9))
    music["beat_seconds"] = round(float(np.clip(base_beat * (1.05 - 0.1 * melt_rate), 0.5, 1.5)), 6)
    music["geometry_link"] = {
        "version": GEOMETRY_AUDIO_VERSION,
        "fold_interval": interval,
        "strand_density": strands,
        "melt_rate": melt_rate,
    }
    return result
