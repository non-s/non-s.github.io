from __future__ import annotations

import cv2
import numpy as np

from utils.visual_intelligence import analyze_image, analyze_video, creative_quality_flags


def test_analyze_image_reports_visual_signals(tmp_path):
    path = tmp_path / "image.png"
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    image[:, 40:] = 255
    assert cv2.imwrite(str(path), image)
    signals = analyze_image(path)
    assert signals["brightness"] > 100
    assert signals["contrast"] > 0
    assert signals["edge_density"] > 0


def test_analyze_image_unreadable_returns_empty(tmp_path):
    path = tmp_path / "nonexistent.png"
    signals = analyze_image(path)
    assert signals == {}


def test_analyze_image_color_image_has_saturation(tmp_path):
    path = tmp_path / "color.png"
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    image[:] = (0, 0, 255)  # Red in BGR
    assert cv2.imwrite(str(path), image)
    signals = analyze_image(path)
    assert signals["saturation"] > 0


def test_quality_flags_are_review_prompts_not_rejections():
    flags = creative_quality_flags({"brightness": 10, "sharpness": 2}, {"motion_signal": 0.1})
    assert len(flags) == 3


def test_quality_flags_empty_dicts_return_no_flags():
    assert creative_quality_flags({}, {}) == []


def test_quality_flags_good_values_return_no_flags():
    flags = creative_quality_flags({"brightness": 128, "sharpness": 100}, {"motion_signal": 10})
    assert flags == []


def test_quality_flags_dark_thumbnail_only():
    flags = creative_quality_flags({"brightness": 20, "sharpness": 100}, {"motion_signal": 10})
    assert len(flags) == 1
    assert "dark" in flags[0]


def test_analyze_video_invalid_path_returns_empty(tmp_path):
    path = tmp_path / "nonexistent.mp4"
    signals = analyze_video(path)
    assert signals == {}
