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
    audio_rms_db: float
    audio_peak: float
    stereo_width: float
    silence_ratio: float
    sampled_frames: int
    issues: tuple[str, ...]
    fingerprint: tuple[float, ...] = ()
    nearest_distance: float | None = None

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


def _decode_audio(video: Path, limit_seconds: int = 60) -> np.ndarray:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video),
            "-t",
            str(limit_seconds),
            "-f",
            "f32le",
            "-ac",
            "2",
            "-ar",
            "48000",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    samples = np.frombuffer(result.stdout, dtype=np.float32)
    return samples[: len(samples) - len(samples) % 2].reshape(-1, 2)


def _audio_metrics(samples: np.ndarray) -> dict[str, float]:
    if samples.size == 0:
        return {"rms_db": -120.0, "peak": 0.0, "stereo_width": 0.0, "silence_ratio": 1.0}
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    peak = float(np.max(np.abs(samples)))
    mono_energy = np.mean(np.abs(np.mean(samples, axis=1))) + 1e-9
    side_energy = np.mean(np.abs(samples[:, 0] - samples[:, 1]))
    frame_energy = np.mean(np.abs(samples), axis=1)
    return {
        "rms_db": float(20 * np.log10(max(rms, 1e-6))),
        "peak": peak,
        "stereo_width": float(side_energy / mono_energy),
        "silence_ratio": float(np.mean(frame_energy < 1e-4)),
    }


def _frame_metrics(frames: list[np.ndarray]) -> dict[str, Any]:
    if not frames:
        return {
            "active_ratio": 0.0,
            "border_activity": 1.0,
            "motion_signal": 0.0,
            "color_bins": 0,
            "motion": [],
            "fingerprint": (0.0,) * 20,
        }
    active_ratios: list[float] = []
    border_ratios: list[float] = []
    color_cells: set[tuple[int, int, int]] = set()
    hue_histogram = np.zeros(12, dtype=np.float64)
    centroids_x: list[float] = []
    centroids_y: list[float] = []
    reduced_gray: list[np.ndarray] = []
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        active = gray > 8
        active_ratios.append(float(np.mean(active)))
        ys, xs = np.nonzero(active)
        centroids_x.append(float(np.mean(xs) / max(1, gray.shape[1] - 1)) if len(xs) else 0.5)
        centroids_y.append(float(np.mean(ys) / max(1, gray.shape[0] - 1)) if len(ys) else 0.5)
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
            hue_histogram += np.histogram(hsv[:, :, 0][colorful], bins=12, range=(0, 180))[0]
            quantized = hsv[colorful] // np.array([15, 32, 32], dtype=np.uint8)
            color_cells.update(map(tuple, np.unique(quantized, axis=0).tolist()))
        reduced_gray.append(cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA))
    motion = [
        float(np.mean(cv2.absdiff(previous, current)))
        for previous, current in zip(reduced_gray, reduced_gray[1:], strict=False)
    ]
    hue_total = float(np.sum(hue_histogram))
    if hue_total:
        hue_histogram /= hue_total
    motion_median = float(np.median(motion)) if motion else 0.0
    fingerprint = (
        float(np.mean(active_ratios)),
        float(np.std(active_ratios)),
        float(np.mean(centroids_x)),
        float(np.std(centroids_x)),
        float(np.mean(centroids_y)),
        float(np.std(centroids_y)),
        min(1.0, motion_median / 12.0),
        min(1.0, (float(np.std(motion)) if motion else 0.0) / 12.0),
        *(float(value) for value in hue_histogram),
    )
    return {
        "active_ratio": float(np.median(active_ratios)),
        "border_activity": float(np.median(border_ratios)),
        "motion_signal": motion_median,
        "color_bins": len(color_cells),
        "motion": motion,
        "fingerprint": fingerprint,
    }


def _sync_signal(times: list[float], motion: list[float], events: list[CreativeEvent]) -> float:
    if len(times) < 2 or not motion:
        return 0.0
    energies = [float(visual_state(t, events)["total"]) for t in times[1:]]
    if np.std(energies) < 1e-6 or np.std(motion) < 1e-6:
        return 0.0
    return float(np.corrcoef(np.asarray(energies), np.asarray(motion))[0, 1])


def _fingerprint_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return 1.0
    weights = np.array((3.0, 2.0, 1.5, 1.5, 1.5, 1.5, 1.5, 1.0, *((1.0,) * 12)))
    delta = (np.asarray(left) - np.asarray(right)) * weights
    return float(np.linalg.norm(delta) / np.sqrt(np.sum(weights**2)))


def assess_video(
    video: Path,
    expected_size: tuple[int, int],
    events: list[CreativeEvent],
    reference_fingerprints: list[tuple[float, ...]] | None = None,
) -> QualityReport:
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
    fingerprint = tuple(float(value) for value in metrics["fingerprint"])
    distances = [_fingerprint_distance(fingerprint, reference) for reference in reference_fingerprints or []]
    nearest_distance = min(distances) if distances else None
    channels = int(audio.get("channels", 0) or 0)
    sample_rate = int(audio.get("sample_rate", 0) or 0)
    audio_metrics = _audio_metrics(_decode_audio(video))
    rms_db = audio_metrics["rms_db"]
    peak = audio_metrics["peak"]
    stereo_width = audio_metrics["stereo_width"]
    silence_ratio = audio_metrics["silence_ratio"]
    issues: list[str] = []
    if (int(visual.get("width", 0)), int(visual.get("height", 0))) != expected_size:
        issues.append("wrong_dimensions")
    if channels < 2 or sample_rate != 48_000:
        issues.append("audio_not_stereo_48k")
    if not -34.0 <= rms_db <= -8.0:
        issues.append("audio_loudness_out_of_range")
    if peak >= 0.999:
        issues.append("audio_clipping")
    if stereo_width < 0.01:
        issues.append("stereo_image_too_narrow")
    if silence_ratio > 0.20:
        issues.append("excessive_audio_silence")
    if not 0.018 <= active <= 0.58:
        issues.append("object_occupancy_out_of_range")
    if border > 0.025:
        issues.append("object_touches_frame_border")
    if motion < 0.10:
        issues.append("insufficient_motion")
    if colors < 12:
        issues.append("insufficient_color_variety")
    if nearest_distance is not None and nearest_distance < 0.035:
        issues.append("perceptual_near_duplicate")
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
        audio_rms_db=round(rms_db, 4),
        audio_peak=round(peak, 5),
        stereo_width=round(stereo_width, 5),
        silence_ratio=round(silence_ratio, 5),
        sampled_frames=len(frames),
        issues=tuple(issues),
        fingerprint=tuple(round(value, 6) for value in fingerprint),
        nearest_distance=round(nearest_distance, 6) if nearest_distance is not None else None,
    )
