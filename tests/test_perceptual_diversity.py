"""Frente E — Diversidade perceptual verificavel.

Testes de diversidade: 24 seeds diferentes devem produzir 24 impressoes
digitais perceptuais distintas, com distancia pareada acima do threshold de
near-duplicate (0.04), e a projecao PCA 2D deve produzir pontos 2D validos
para cada video.
"""

from __future__ import annotations

import cv2
import numpy as np

from scripts.generate_dashboard import _build_diversity_dataset, _pca_2d
from utils.liquid_wire_quality import (
    FINGERPRINT_DIMS,
    NEAR_DUPLICATE_THRESHOLD,
    _fingerprint_distance,
    _frame_metrics,
)


def _hue_for_seed(seed: int) -> int:
    """Map a seed (0..23) to one of 24 evenly-spaced hues (7.5 deg apart) in
    a shuffled order so consecutive seeds land far apart on the hue wheel.

    Uses a fixed bit-reversal permutation of the 24 indices: this guarantees
    that any two of the 24 hues are at least 7.5 deg apart (so they fall in
    different 15-deg hue histogram bins) while consecutive seeds are spread
    across the wheel.
    """
    # 24 evenly spaced hues, then permuted by a fixed shuffle (seed -> index).
    order = [0, 12, 6, 18, 3, 15, 9, 21, 1, 13, 7, 19, 4, 16, 10, 22, 2, 14, 8, 20, 5, 17, 11, 23]
    idx = order[seed % len(order)]
    return int(idx * 180 / 24)


def _seeded_frames(seed: int, n: int = 4) -> list[np.ndarray]:
    """Build ``n`` 320x180 BGR frames whose visual content is driven by
    ``seed`` so different seeds yield perceptually different clips.

    Each seed selects a different drawing "style" (filled circle, outline
    rectangle, diagonal stripes, scattered dots, concentric rings) and a
    different hue / position / size, so the activity, centroid, motion,
    LBP, HSV and entropy dims all vary strongly across seeds. This keeps
    every pair of seeds above the 0.04 near-duplicate diversity threshold.
    """
    rng = np.random.default_rng(seed)
    base_hue = _hue_for_seed(seed)
    style = seed % 5
    cx = int(rng.integers(80, 240))
    cy = int(rng.integers(50, 130))
    size = int(rng.integers(25, 60))
    frames: list[np.ndarray] = []
    for i in range(n):
        hue = int((base_hue + i * 53) % 180)
        hsv = np.zeros((180, 320, 3), dtype=np.uint8)
        xi = (cx + int(rng.integers(-30, 31))) % 320
        yi = (cy + int(rng.integers(-20, 21))) % 180
        if style == 0:
            cv2.circle(hsv, (xi, yi), size, (hue, 220, 240), -1)
        elif style == 1:
            cv2.rectangle(hsv, (xi - size, yi - size // 2), (xi + size, yi + size // 2), (hue, 220, 240), 3)
        elif style == 2:
            for k in range(-size, size, 6):
                cv2.line(hsv, (xi + k, yi - size), (xi + k + size, yi + size), (hue, 220, 240), 2)
        elif style == 3:
            for _ in range(int(rng.integers(20, 60))):
                px = int(rng.integers(0, 320))
                py = int(rng.integers(0, 180))
                cv2.circle(hsv, (px, py), int(rng.integers(1, 4)), (hue, 200, 220), -1)
        else:
            for r in range(8, size, 8):
                cv2.circle(hsv, (xi, yi), r, (hue, 220, 240), 1)
        # A seed-dependent textured grid overlay so LBP/entropy dims differ.
        step = int(rng.integers(10, 26))
        dot_hue = int((base_hue + 90) % 180)
        for gy in range(10, 180, step):
            for gx in range(10, 320, step):
                cv2.circle(hsv, (gx, gy), 2, (dot_hue, 180, 200), -1)
        frames.append(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR))
    return frames


def _seeded_fingerprint(seed: int) -> tuple:
    fp = _frame_metrics(_seeded_frames(seed))["fingerprint"]
    assert len(fp) == FINGERPRINT_DIMS
    return tuple(fp)


def test_24_seeds_produce_24_different_fingerprints() -> None:
    fingerprints = [_seeded_fingerprint(seed) for seed in range(24)]
    unique = set(fingerprints)
    assert len(unique) == 24


def test_pairwise_distance_above_diversity_threshold() -> None:
    fingerprints = [_seeded_fingerprint(seed) for seed in range(24)]
    below = []
    for i in range(len(fingerprints)):
        for j in range(i + 1, len(fingerprints)):
            dist = _fingerprint_distance(fingerprints[i], fingerprints[j])
            if dist <= NEAR_DUPLICATE_THRESHOLD:
                below.append((i, j, dist))
    assert not below, f"pairs below diversity threshold: {below[:5]}"


def test_pca_projection_produces_2d_points() -> None:
    fingerprints = [list(_seeded_fingerprint(seed)) for seed in range(24)]
    coords = _pca_2d(fingerprints)
    assert len(coords) == 24
    for coord in coords:
        assert len(coord) == 2
        assert all(np.isfinite(coord))


def test_diversity_dataset_from_quality_history() -> None:
    history = [
        {"fingerprint": list(_seeded_fingerprint(seed)), "genre": "lofi" if seed % 2 else "jazz"}
        for seed in range(10)
    ]
    ds = _build_diversity_dataset(history)
    assert ds["n"] == 10
    assert ds["unique_genres"] == 2
    assert {"lofi", "jazz"} == set(ds["genres"])
    assert ds["avg_distance"] > 0.0
    assert len(ds["points"]) == 10
    # 10 diverse seeds should not trigger the dense-cluster warning.
    assert ds["cluster_warning"] is False


def test_dense_cluster_warning_fires_for_near_duplicates() -> None:
    # 6 nearly-identical fingerprints -> pairwise distances ~0 -> warning.
    fp = list(_seeded_fingerprint(1))
    history = [{"fingerprint": fp, "genre": "lofi"} for _ in range(6)]
    ds = _build_diversity_dataset(history)
    assert ds["cluster_warning"] is True
