from __future__ import annotations

import cv2
import numpy as np

from utils.liquid_wire_quality import _audio_metrics, _frame_metrics


def _frame(x: int, hue: int) -> np.ndarray:
    hsv = np.zeros((180, 320, 3), dtype=np.uint8)
    cv2.circle(hsv, (x, 90), 38, (hue, 220, 240), 3)
    cv2.line(hsv, (x - 30, 70), (x + 35, 108), ((hue + 50) % 180, 240, 220), 2)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


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
