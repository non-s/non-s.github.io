"""OpenCV-based visual signals for creative quality control.

These metrics are descriptive guardrails, not aesthetic truth: they help the
editorial council spot technically weak assets and compare visual variety.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

# Dynamic imports keep static checking independent from the local NumPy stub
# version while OpenCV remains a declared runtime dependency.
cv2: Any = importlib.import_module("cv2")
np: Any = importlib.import_module("numpy")


def analyze_image(path: Path) -> dict[str, float]:
    """Measure brightness, contrast, saturation, sharpness and edge density."""
    image = cv2.imread(str(path))
    if image is None:
        return {}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(gray, 80, 160)
    return {
        "brightness": round(float(gray.mean()), 2),
        "contrast": round(float(gray.std()), 2),
        "saturation": round(float(hsv[:, :, 1].mean()), 2),
        "sharpness": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2),
        "edge_density": round(float(np.count_nonzero(edges) / edges.size), 4),
    }


def analyze_video(path: Path, samples: int = 3) -> dict[str, float]:
    """Sample a video to estimate luminance and visible frame-to-frame change."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return {}
    frame_count = max(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 1)
    indices = [int(frame_count * fraction) for fraction in np.linspace(0.15, 0.85, max(samples, 1))]
    brightnesses: list[float] = []
    motions: list[float] = []
    previous: Any = None
    try:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightnesses.append(float(gray.mean()))
            if previous is not None:
                motions.append(float(cv2.absdiff(gray, previous).mean()))
            previous = gray
    finally:
        capture.release()
    if not brightnesses:
        return {}
    return {
        "sample_brightness": round(float(np.mean(brightnesses)), 2),
        "brightness_variation": round(float(np.std(brightnesses)), 2),
        "motion_signal": round(float(np.mean(motions)) if motions else 0.0, 2),
        "sample_count": float(len(brightnesses)),
    }


def creative_quality_flags(thumbnail: dict[str, float], video: dict[str, float]) -> list[str]:
    """Return conservative technical review prompts, not automatic rejections."""
    flags: list[str] = []
    if thumbnail and thumbnail.get("brightness", 128) < 35:
        flags.append("thumbnail may be too dark for feed discovery")
    if thumbnail and thumbnail.get("sharpness", 100) < 12:
        flags.append("thumbnail may be visually soft")
    if video and video.get("motion_signal", 10) < 1:
        flags.append("video has very little visual change; review pacing")
    return flags
