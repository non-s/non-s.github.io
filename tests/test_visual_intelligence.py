from __future__ import annotations

import cv2
import numpy as np

from utils.visual_intelligence import analyze_image, creative_quality_flags


def test_analyze_image_reports_visual_signals(tmp_path):
    path = tmp_path / "image.png"
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    image[:, 40:] = 255
    assert cv2.imwrite(str(path), image)
    signals = analyze_image(path)
    assert signals["brightness"] > 100
    assert signals["contrast"] > 0
    assert signals["edge_density"] > 0


def test_quality_flags_are_review_prompts_not_rejections():
    flags = creative_quality_flags({"brightness": 10, "sharpness": 2}, {"motion_signal": 0.1})
    assert len(flags) == 3
