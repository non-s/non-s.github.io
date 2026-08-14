from __future__ import annotations

import cv2
import numpy as np

from utils.liquid_wire_quality import (
    FINGERPRINT_DIMS,
    LEGACY_FINGERPRINT_DIMS,
    NEAR_DUPLICATE_THRESHOLD,
    _audio_metrics,
    _fingerprint_distance,
    _frame_metrics,
    _pad_fingerprint,
)


def _frame(x: int, hue: int) -> np.ndarray:
    hsv = np.zeros((180, 320, 3), dtype=np.uint8)
    cv2.circle(hsv, (x, 90), 38, (hue, 220, 240), 3)
    cv2.line(hsv, (x - 30, 70), (x + 35, 108), ((hue + 50) % 180, 240, 220), 2)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _fingerprint_frames() -> tuple:
    return tuple(_frame_metrics([_frame(120, 10), _frame(145, 70), _frame(165, 130)])["fingerprint"])


def test_frame_metrics_detect_a_moving_colorful_object() -> None:
    metrics = _frame_metrics([_frame(120, 10), _frame(145, 70), _frame(165, 130)])
    assert 0.01 < metrics["active_ratio"] < 0.2
    assert metrics["border_activity"] == 0.0
    assert metrics["motion_signal"] > 0.1
    assert metrics["color_bins"] >= 2


def test_frame_metrics_reject_visual_silence() -> None:
    blank = np.zeros((180, 320, 3), dtype=np.uint8)
    metrics = _frame_metrics([blank, blank.copy()])
    assert metrics["active_ratio"] == 0.0
    assert metrics["motion_signal"] == 0.0
    assert metrics["color_bins"] == 0


def test_audio_metrics_measure_level_width_and_silence() -> None:
    time = np.linspace(0, 1, 48_000, endpoint=False)
    left = 0.2 * np.sin(2 * np.pi * 220 * time)
    right = 0.2 * np.sin(2 * np.pi * 220 * time + 0.3)
    metrics = _audio_metrics(np.column_stack((left, right)).astype(np.float32))
    assert -20.0 < metrics["rms_db"] < -10.0
    assert 0.19 < metrics["peak"] < 0.21
    assert metrics["stereo_width"] > 0.1
    assert metrics["silence_ratio"] < 0.01


def test_audio_metrics_detect_silence() -> None:
    metrics = _audio_metrics(np.zeros((1000, 2), dtype=np.float32))
    assert metrics["rms_db"] == -120.0
    assert metrics["silence_ratio"] == 1.0


def test_perceptual_fingerprint_has_32_dimensions() -> None:
    fp = _fingerprint_frames()
    assert len(fp) == FINGERPRINT_DIMS == 32


def test_perceptual_fingerprint_values_in_unit_range() -> None:
    fp = _fingerprint_frames()
    assert all(0.0 <= v <= 1.0 for v in fp)


def test_perceptual_fingerprint_is_deterministic() -> None:
    first = _fingerprint_frames()
    second = _fingerprint_frames()
    assert first == second
    assert _fingerprint_distance(first, second) == 0.0


def test_perceptual_fingerprint_detects_duplicates() -> None:
    first = _fingerprint_frames()
    duplicate = _fingerprint_frames()
    different = tuple(_frame_metrics([_frame(80, 160), _frame(95, 160), _frame(105, 160)])["fingerprint"])
    assert _fingerprint_distance(first, duplicate) == 0.0
    # Frente E recalibrated the near-duplicate threshold to 0.04 for 32 dims.
    assert _fingerprint_distance(first, different) > NEAR_DUPLICATE_THRESHOLD


def test_pad_fingerprint_lifts_legacy_20_to_32() -> None:
    legacy = tuple(0.1 * i for i in range(LEGACY_FINGERPRINT_DIMS))
    padded = _pad_fingerprint(legacy)
    assert len(padded) == FINGERPRINT_DIMS
    assert padded[:LEGACY_FINGERPRINT_DIMS] == legacy
    assert padded[LEGACY_FINGERPRINT_DIMS:] == (0.0,) * (FINGERPRINT_DIMS - LEGACY_FINGERPRINT_DIMS)


def test_fingerprint_distance_compares_legacy_and_full() -> None:
    legacy = tuple(0.1 * i for i in range(LEGACY_FINGERPRINT_DIMS))
    full = legacy + (0.0,) * (FINGERPRINT_DIMS - LEGACY_FINGERPRINT_DIMS)
    # A legacy 20-dim fingerprint padded with zeros must match a 32-dim
    # fingerprint that shares the same first 20 dims and zero tails.
    assert _fingerprint_distance(legacy, full) == 0.0
