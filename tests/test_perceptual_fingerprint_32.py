"""Frente E — Diversidade perceptual verificavel.

Testes para a expansao da impressao digital perceptual de 20 para 32
dimensoes em utils/liquid_wire_quality.py. Os novos dims cobrem textura
LBP, estatisticas HSV, entropia de frame (visual) e fluxo espectral /
ritmo harmonico / variancia do centroide (audio).
"""

from __future__ import annotations

import cv2
import numpy as np

from utils.liquid_wire_quality import (
    FINGERPRINT_DIMS,
    LEGACY_FINGERPRINT_DIMS,
    NEAR_DUPLICATE_THRESHOLD,
    _audio_fingerprint_dims,
    _fingerprint_distance,
    _frame_metrics,
    _pad_fingerprint,
)


def _moving_circle(x: int, hue: int) -> np.ndarray:
    hsv = np.zeros((180, 320, 3), dtype=np.uint8)
    cv2.circle(hsv, (x, 90), 38, (hue, 220, 240), 3)
    cv2.line(hsv, (x - 30, 70), (x + 35, 108), ((hue + 50) % 180, 240, 220), 2)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _dense_grid(hue: int) -> np.ndarray:
    """A texture-heavy frame (grid of dots) very different from a circle."""
    hsv = np.zeros((180, 320, 3), dtype=np.uint8)
    for y in range(20, 180, 18):
        for x in range(20, 320, 18):
            cv2.circle(hsv, (x, y), 5, (hue, 200, 220), -1)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _fingerprint(frames: list[np.ndarray]) -> tuple:
    return tuple(_frame_metrics(frames)["fingerprint"])


def test_fingerprint_is_exactly_32_dimensions() -> None:
    fp = _fingerprint([_moving_circle(120, 10), _moving_circle(145, 70)])
    assert len(fp) == FINGERPRINT_DIMS == 32


def test_fingerprint_values_in_unit_range() -> None:
    fp = _fingerprint([_moving_circle(120, 10), _moving_circle(145, 70), _moving_circle(165, 130)])
    assert all(0.0 <= v <= 1.0 for v in fp), fp


def test_fingerprint_is_deterministic() -> None:
    frames = [_moving_circle(120, 10), _moving_circle(145, 70), _moving_circle(165, 130)]
    first = _fingerprint(frames)
    second = _fingerprint(frames)
    assert first == second
    assert _fingerprint_distance(first, second) == 0.0


def test_legacy_20_dim_fingerprint_padded_to_32_for_comparison() -> None:
    legacy = tuple(0.05 * i for i in range(LEGACY_FINGERPRINT_DIMS))
    padded = _pad_fingerprint(legacy)
    assert len(padded) == FINGERPRINT_DIMS
    assert padded[:LEGACY_FINGERPRINT_DIMS] == legacy
    assert padded[LEGACY_FINGERPRINT_DIMS:] == (0.0,) * (FINGERPRINT_DIMS - LEGACY_FINGERPRINT_DIMS)
    # Distance between a legacy fingerprint and its padded version is 0.
    full = legacy + (0.0,) * (FINGERPRINT_DIMS - LEGACY_FINGERPRINT_DIMS)
    assert _fingerprint_distance(legacy, full) == 0.0


def test_near_duplicate_detection_with_32_dim_fingerprint() -> None:
    base = _fingerprint([_moving_circle(120, 10), _moving_circle(145, 70)])
    duplicate = _fingerprint([_moving_circle(120, 10), _moving_circle(145, 70)])
    assert _fingerprint_distance(base, duplicate) < NEAR_DUPLICATE_THRESHOLD
    different = _fingerprint([_dense_grid(20), _dense_grid(140)])
    assert _fingerprint_distance(base, different) > NEAR_DUPLICATE_THRESHOLD


def test_different_visual_content_produces_different_fingerprints() -> None:
    circles = _fingerprint([_moving_circle(120, 10), _moving_circle(150, 90), _moving_circle(180, 170)])
    grid = _fingerprint([_dense_grid(30), _dense_grid(120)])
    # The two visual styles are perceptually very different (sparse moving
    # circles vs a dense static grid), so their fingerprints must differ
    # well beyond the near-duplicate threshold.
    assert _fingerprint_distance(circles, grid) > NEAR_DUPLICATE_THRESHOLD


def test_audio_fingerprint_dims_have_4_values_in_unit_range() -> None:
    sr = 48_000
    t = np.linspace(0, 1, sr, endpoint=False)
    # A signal with a clear spectral evolution: rising chirp.
    freq = 200 + 2000 * t
    phase = 2 * np.pi * np.cumsum(freq) / sr
    mono = 0.3 * np.sin(phase)
    samples = np.column_stack([mono, mono]).astype(np.float32)
    dims = _audio_fingerprint_dims(samples, sr)
    assert len(dims) == 4
    assert all(0.0 <= v <= 1.0 for v in dims)


def test_audio_fingerprint_dims_silence_is_zero() -> None:
    samples = np.zeros((1000, 2), dtype=np.float32)
    dims = _audio_fingerprint_dims(samples, 48_000)
    assert dims == (0.0, 0.0, 0.0, 0.0)
