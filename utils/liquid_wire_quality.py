"""Blocking perceptual quality gate for generated Liquid Wire videos."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from utils.liquid_wire_timeline import CreativeEvent, visual_state


class QualityGateError(RuntimeError):
    """Raised when a render is technically valid but artistically unusable."""


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    score: float
    active_ratio: float
    border_activity: float
    motion_signal: float
    color_bins: int
    sync_signal: float
    audio_channels: int
    audio_sample_rate: int
    sampled_frames: int
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _media_info(video: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height,channels,sample_rate",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _sample_frames(video: Path, count: int = 16) -> tuple[list[np.ndarray], list[float]]:
    capture = cv2.VideoCapture(str(video))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = max(1.0, float(capture.get(cv2.CAP_PROP_FPS)))
    indices = np.linspace(0, max(0, frame_count - 1), min(count, max(1, frame_count)), dtype=int)
    frames: list[np.ndarray] = []
    times: list[float] = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if ok:
            frames.append(frame)
            times.append(float(index) / fps)
    capture.release()
    return frames, times


def _frame_metrics(frames: list[np.ndarray]) -> dict[str, Any]:
    if not frames:
        return {"active_ratio": 0.0, "border_activity": 1.0, "motion_signal": 0.0, "color_bins": 0, "motion": []}
    active_ratios: list[float] = []
    border_ratios: list[float] = []
    color_cells: set[tuple[int, int, int]] = set()
    reduced_gray: list[np.ndarray] = []
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        active = gray > 8
        active_ratios.append(float(np.mean(active)))
        border = max(2, round(min(gray.shape) * 0.035))
        border_mask = np.zeros_like(active)
        border_mask[:border, :] = True
        border_mask[-border:, :] = True
        border_mask[:, :border] = True
        border_mask[:, -border:] = True
        border_ratios.append(float(np.mean(active[border_mask])))
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        colorful = active & (hsv[:, :, 1] > 45) & (hsv[:, :, 2] > 35)
        if np.any(colorful):
            quantized = hsv[colorful] // np.array([15, 32, 32], dtype=np.uint8)
            color_cells.update(map(tuple, np.unique(quantized, axis=0).tolist()))
        reduced_gray.append(cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA))
    motion = [
        float(np.mean(cv2.absdiff(previous, current)))
        for previous, current in zip(reduced_gray, reduced_gray[1:], strict=False)
    ]
    return {
        "active_ratio": float(np.median(active_ratios)),
        "border_activity": float(np.median(border_ratios)),
        "motion_signal": float(np.median(motion)) if motion else 0.0,
        "color_bins": len(color_cells),
        "motion": motion,
    }


def _sync_signal(times: list[float], motion: list[float], events: list[CreativeEvent]) -> float:
    if len(times) < 2 or not motion:
        return 0.0
    energies = [float(visual_state(t, events)["total"]) for t in times[1:]]
    if np.std(energies) < 1e-6 or np.std(motion) < 1e-6:
        return 0.0
    return float(np.corrcoef(np.asarray(energies), np.asarray(motion))[0, 1])


def assess_video(video: Path, expected_size: tuple[int, int], events: list[CreativeEvent]) -> QualityReport:
    info = _media_info(video)
    streams = info.get("streams", [])
    visual: dict[str, Any] = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio: dict[str, Any] = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    frames, times = _sample_frames(video)
    metrics = _frame_metrics(frames)
    active = float(metrics["active_ratio"])
    border = float(metrics["border_activity"])
    motion = float(metrics["motion_signal"])
    colors = int(metrics["color_bins"])
    sync = _sync_signal(times, list(metrics["motion"]), events)
    channels = int(audio.get("channels", 0) or 0)
    sample_rate = int(audio.get("sample_rate", 0) or 0)
    issues: list[str] = []
    if (int(visual.get("width", 0)), int(visual.get("height", 0))) != expected_size:
        issues.append("wrong_dimensions")
    if channels < 2 or sample_rate != 48_000:
        issues.append("audio_not_stereo_48k")
    if not 0.018 <= active <= 0.58:
        issues.append("object_occupancy_out_of_range")
    if border > 0.025:
        issues.append("object_touches_frame_border")
    if motion < 0.10:
        issues.append("insufficient_motion")
    if colors < 12:
        issues.append("insufficient_color_variety")
    score = (
        0.20 * (not issues or "wrong_dimensions" not in issues)
        + 0.15 * (channels >= 2 and sample_rate == 48_000)
        + 0.20 * (0.018 <= active <= 0.58)
        + 0.15 * (border <= 0.025)
        + 0.18 * min(1.0, motion / 1.8)
        + 0.08 * min(1.0, colors / 48.0)
        + 0.04 * max(0.0, min(1.0, (sync + 1.0) / 2.0))
    )
    return QualityReport(
        passed=not issues and score >= 0.78,
        score=round(float(score), 4),
        active_ratio=round(active, 5),
        border_activity=round(border, 5),
        motion_signal=round(motion, 5),
        color_bins=colors,
        sync_signal=round(sync, 5),
        audio_channels=channels,
        audio_sample_rate=sample_rate,
        sampled_frames=len(frames),
        issues=tuple(issues),
    )
