"""OpenCV-based visual signals for creative quality control.

These metrics are descriptive guardrails, not aesthetic truth: they help the
editorial council spot technically weak assets and compare visual variety.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from utils.creative_models import VisualDNA

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


def _entropy(gray: Any) -> float:
    histogram = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel().astype(float)
    probabilities = histogram[histogram > 0] / max(1.0, float(histogram.sum()))
    return float(-(probabilities * np.log2(probabilities)).sum())


def _sampled_frames(path: Path, samples: int) -> list[Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return []
    count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    indices = np.linspace(0, count - 1, min(max(3, samples), count), dtype=int)
    frames: list[Any] = []
    try:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = capture.read()
            if ok:
                frames.append(frame)
    finally:
        capture.release()
    return frames


def analyze_visual_dna(
    path: Path,
    *,
    samples: int = 12,
    recent_fingerprints: list[list[float] | tuple[float, ...]] | None = None,
) -> VisualDNA | None:
    """Describe what survived the final encode using inexpensive OpenCV signals.

    Metrics are normalized where practical so future schema migrations can
    compare videos rendered at different resolutions.  Novelty is descriptive;
    a separate policy decides whether it should block publication.
    """
    frames = _sampled_frames(path, samples)
    if not frames:
        return None
    brightness: list[float] = []
    contrast: list[float] = []
    saturation: list[float] = []
    entropy: list[float] = []
    edge_density: list[float] = []
    screen_fill: list[float] = []
    symmetry: list[float] = []
    centers: list[tuple[float, float]] = []
    flow: list[float] = []
    differences: list[float] = []
    palette_hist = np.zeros(12, dtype=float)
    previous = None
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        active = gray > 8
        edges = cv2.Canny(gray, 80, 160)
        brightness.append(float(gray.mean() / 255.0))
        contrast.append(float(gray.std() / 127.5))
        saturation.append(float(hsv[:, :, 1].mean() / 255.0))
        entropy.append(_entropy(gray) / 8.0)
        edge_density.append(float(np.count_nonzero(edges) / edges.size))
        screen_fill.append(float(active.mean()))
        ys, xs = np.nonzero(active)
        centers.append(
            (
                float(xs.mean() / max(1, gray.shape[1] - 1)) if len(xs) else 0.5,
                float(ys.mean() / max(1, gray.shape[0] - 1)) if len(ys) else 0.5,
            )
        )
        flipped = cv2.flip(gray, 1)
        symmetry.append(1.0 - min(1.0, float(cv2.absdiff(gray, flipped).mean() / 255.0)))
        colorful = (hsv[:, :, 1] > 32) & (hsv[:, :, 2] > 24)
        if np.any(colorful):
            palette_hist += np.histogram(hsv[:, :, 0][colorful], bins=12, range=(0, 180))[0]
        reduced = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
        if previous is not None:
            differences.append(float(cv2.absdiff(previous, reduced).mean() / 255.0))
            optical = cv2.calcOpticalFlowFarneback(previous, reduced, None, 0.5, 2, 12, 2, 5, 1.1, 0)
            magnitude = cv2.magnitude(optical[..., 0], optical[..., 1])
            flow.append(float(np.median(magnitude) / np.hypot(160, 90)))
        previous = reduced
    palette_total = float(palette_hist.sum())
    palette = (palette_hist / palette_total).tolist() if palette_total else [0.0] * 12
    fingerprint = [
        float(np.mean(screen_fill)),
        float(np.mean(centers, axis=0)[0]),
        float(np.mean(centers, axis=0)[1]),
        float(np.mean(symmetry)),
        float(np.mean(entropy)),
        float(np.mean(flow)) if flow else 0.0,
        float(np.mean(brightness)),
        float(np.mean(contrast)),
        float(np.mean(saturation)),
        *palette,
    ]
    distances = []
    for old in recent_fingerprints or []:
        if not old:
            continue
        width = min(len(old), len(fingerprint))
        delta = np.asarray(fingerprint[:width]) - np.asarray(old[:width])
        distances.append(float(np.linalg.norm(delta) / np.sqrt(width)))
    thirds = np.array_split(np.asarray(differences or [0.0]), 3)
    act_features = np.column_stack((
        screen_fill,
        np.asarray(centers)[:, 0],
        np.asarray(centers)[:, 1],
        symmetry,
        entropy,
        edge_density,
        brightness,
        saturation,
    ))
    acts = [part.mean(axis=0) for part in np.array_split(act_features, 3)]
    opening_middle = float(np.linalg.norm(acts[0] - acts[1]) / np.sqrt(act_features.shape[1]))
    middle_ending = float(np.linalg.norm(acts[1] - acts[2]) / np.sqrt(act_features.shape[1]))
    opening_ending = float(np.linalg.norm(acts[0] - acts[2]) / np.sqrt(act_features.shape[1]))
    activities = [float(np.mean(part)) for part in thirds]
    narrative_criteria = {
        "enough_observations": len(frames) >= 6,
        "distinct_adjacent_acts": min(opening_middle, middle_ending) >= .004,
        "irreversible_state_change": opening_ending >= .006,
        "dynamic_contrast": max(activities) - min(activities) >= .0005,
        "resolution_detected": activities[2] <= max(activities[0], activities[1]) * 1.35 + 1e-6,
    }
    return VisualDNA(
        composition={
            "screen_fill": round(float(np.mean(screen_fill)), 6),
            "center_mass": [round(float(value), 6) for value in np.mean(centers, axis=0)],
            "symmetry": round(float(np.mean(symmetry)), 6),
            "edge_density": round(float(np.mean(edge_density)), 6),
            "entropy": round(float(np.mean(entropy)), 6),
        },
        motion={
            "optical_flow_mean": round(float(np.mean(flow)) if flow else 0.0, 6),
            "optical_flow_variance": round(float(np.var(flow)) if flow else 0.0, 6),
            "frame_difference_mean": round(float(np.mean(differences)) if differences else 0.0, 6),
        },
        appearance={
            "brightness": round(float(np.mean(brightness)), 6),
            "contrast": round(float(np.mean(contrast)), 6),
            "saturation": round(float(np.mean(saturation)), 6),
            "dominant_palette": [round(float(value), 6) for value in palette],
        },
        temporal={
            "opening_activity": round(activities[0], 6),
            "middle_activity": round(activities[1], 6),
            "ending_activity": round(activities[2], 6),
            "opening_middle_distance": round(opening_middle, 6),
            "middle_ending_distance": round(middle_ending, 6),
            "opening_ending_distance": round(opening_ending, 6),
            "narrative_criteria": narrative_criteria,
            "narrative_pass": all(narrative_criteria.values()),
        },
        novelty={
            "fingerprint": [round(float(value), 6) for value in fingerprint],
            "recent_distance": round(min(distances), 6) if distances else None,
        },
        sample_count=len(frames),
    )


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
