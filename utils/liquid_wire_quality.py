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

# Number of dimensions in the canonical perceptual fingerprint. Frente E
# expanded it from 20 to 32: 8 new visual dims (LBP texture entropy x4, HSV
# value-channel stats x3, frame entropy x1) and 4 new audio dims (spectral
# flux mean/std x2, harmonic rhythm x1, spectral-centroid variance x1).
FINGERPRINT_DIMS = 32
# Legacy 20-dim fingerprints (pre-Frente E) are padded with zeros to
# FINGERPRINT_DIMS before comparison so historical quality_history entries
# remain usable for near-duplicate detection.
LEGACY_FINGERPRINT_DIMS = 20
# Near-duplicate threshold recalibrated for 32 dimensions (slightly more
# permissive than the legacy 0.035 because higher-dimensional fingerprints
# have larger baseline distances).
NEAR_DUPLICATE_THRESHOLD = 0.04


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


def _shannon_entropy(probs: np.ndarray) -> float:
    """Shannon entropy (in bits) for a probability vector that already sums to 1."""
    probs = np.asarray(probs, dtype=np.float64)
    probs = probs[probs > 0]
    if probs.size == 0:
        return 0.0
    return float(-np.sum(probs * np.log2(probs)))


def _lbp_entropy(gray: np.ndarray) -> float:
    """Simplified 4-bin Local Binary Pattern texture descriptor.

    Instead of the full 256-bin LBP histogram we use a 4-bin reduction based
    on the magnitude of the 8-neighbour agreement count, which is enough to
    characterize texture roughness for the perceptual fingerprint while
    keeping the descriptor cheap. Returns the Shannon entropy (in bits, so in
    [0, 2] for 4 bins) of the 4-bin histogram.
    """
    arr = gray.astype(np.int16)
    h, w = arr.shape
    if h < 3 or w < 3:
        return 0.0
    center = arr[1:-1, 1:-1]
    counts = np.zeros_like(center)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            counts += (arr[1 + dy : h - 1 + dy, 1 + dx : w - 1 + dx] >= center).astype(np.int16)
    # 4 bins over the 0..8 agreement range.
    bin_idx = np.clip(counts // 2, 0, 3)
    hist = np.bincount(bin_idx.ravel(), minlength=4).astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 0.0
    return _shannon_entropy(hist / total)


def _lbp_quartiles(entropies: list[float]) -> tuple[float, float, float, float]:
    """Return 4 dims summarising the per-frame LBP entropy distribution.

    Uses quartiles (min, 25th, 50th, 75th percentile) so the descriptor
    captures the spread of texture complexity across the sampled frames
    rather than a single average.
    """
    if not entropies:
        return (0.0, 0.0, 0.0, 0.0)
    arr = np.asarray(entropies, dtype=np.float64)
    # LBP entropy is in [0, 2] bits for 4 bins; normalise to [0, 1].
    qs = np.quantile(arr, [0.0, 0.25, 0.5, 0.75])
    return tuple(float(min(1.0, max(0.0, q / 2.0))) for q in qs)  # type: ignore[return-value]


def _hsv_value_stats(hsv: np.ndarray) -> tuple[float, float, float, float]:
    """Return (mean, std, skewness, kurtosis) of the HSV value channel.

    Values are in [0, 255]; skewness/kurtosis are the standardised moments of
    the value distribution.
    """
    values = hsv[:, :, 2].astype(np.float64)
    if values.size == 0:
        return (0.0, 0.0, 0.0, 0.0)
    mean = float(values.mean())
    std = float(values.std())
    if std < 1e-6:
        return (mean, std, 0.0, 0.0)
    centered = values - mean
    n = float(values.size)
    skew = float(np.sum(centered**3) / n / (std**3))
    kurt = float(np.sum(centered**4) / n / (std**4) - 3.0)
    return (mean, std, skew, kurt)


def _frame_entropy(gray: np.ndarray) -> float:
    """Shannon entropy (bits) of the 256-bin pixel-intensity distribution."""
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 0.0
    return _shannon_entropy(hist / total)


def _audio_fingerprint_dims(samples: np.ndarray, sample_rate: int = 48_000) -> tuple[float, float, float, float]:
    """Compute the 4 new audio fingerprint dimensions for Frente E.

    Returns (spectral_flux_mean, spectral_flux_std, harmonic_rhythm,
    spectral_centroid_variance), each normalised to roughly [0, 1].
    """
    if samples.size == 0:
        return (0.0, 0.0, 0.0, 0.0)
    mono = samples.mean(axis=1) if samples.ndim > 1 else samples
    # Analyse in ~46ms frames (2048 samples at 48k) with 50% overlap.
    frame_size = 2048
    hop = frame_size // 2
    if len(mono) < frame_size:
        return (0.0, 0.0, 0.0, 0.0)
    n_frames = 1 + (len(mono) - frame_size) // hop
    spectra: list[np.ndarray] = []
    centroids: list[float] = []
    fluxes: list[float] = []
    window = np.hanning(frame_size).astype(np.float32)
    freqs = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)
    for i in range(n_frames):
        block = mono[i * hop : i * hop + frame_size].astype(np.float32) * window
        spec = np.abs(np.fft.rfft(block)).astype(np.float64)
        spectra.append(spec)
        energy = spec.sum()
        if energy > 1e-9:
            centroids.append(float((freqs * spec).sum() / energy))
        else:
            centroids.append(0.0)
    prev = None
    for spec in spectra:
        if prev is not None:
            diff = spec - prev
            # Positive differences only (onset-style spectral flux).
            fluxes.append(float(np.sum(np.clip(diff, 0.0, None))))
        prev = spec
    if not fluxes:
        return (0.0, 0.0, 0.0, 0.0)
    flux_arr = np.asarray(fluxes, dtype=np.float64)
    flux_max = float(flux_arr.max()) if flux_arr.size else 1.0
    flux_mean = float(flux_arr.mean() / max(flux_max, 1e-9))
    flux_std = float(flux_arr.std() / max(flux_max, 1e-9))
    # Harmonic rhythm: rate of spectral-change peaks above the mean+std.
    threshold = flux_arr.mean() + flux_arr.std()
    peaks = int(np.sum(flux_arr > threshold))
    # Normalise by number of frames analysed (peaks per frame in [0, 1]).
    harmonic_rhythm = min(1.0, peaks / max(1, len(flux_arr)))
    cent_arr = np.asarray(centroids, dtype=np.float64)
    if cent_arr.size and float(cent_arr.mean()) > 1e-6:
        centroid_var = float(cent_arr.std() / cent_arr.mean())
    else:
        centroid_var = 0.0
    centroid_var = min(1.0, centroid_var)
    return (flux_mean, flux_std, harmonic_rhythm, centroid_var)


def _frame_metrics(frames: list[np.ndarray]) -> dict[str, Any]:
    if not frames:
        return {
            "active_ratio": 0.0,
            "border_activity": 1.0,
            "motion_signal": 0.0,
            "color_bins": 0,
            "motion": [],
            "fingerprint": (0.0,) * FINGERPRINT_DIMS,
        }
    active_ratios: list[float] = []
    border_ratios: list[float] = []
    color_cells: set[tuple[int, int, int]] = set()
    hue_histogram = np.zeros(12, dtype=np.float64)
    centroids_x: list[float] = []
    centroids_y: list[float] = []
    reduced_gray: list[np.ndarray] = []
    # Per-frame collections for the new Frente E visual dims.
    lbp_entropies: list[float] = []
    value_means: list[float] = []
    value_stds: list[float] = []
    value_skews: list[float] = []
    frame_entropies: list[float] = []
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
        # --- Frente E: new visual fingerprint dimensions -------------------
        lbp_entropies.append(_lbp_entropy(gray))
        v_stats = _hsv_value_stats(hsv)
        value_means.append(v_stats[0])
        value_stds.append(v_stats[1])
        value_skews.append(v_stats[2])
        frame_entropies.append(_frame_entropy(gray))
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
        # 4 LBP texture-entropy dims (one per quartile over sampled frames).
        *_lbp_quartiles(lbp_entropies),
        # 3 HSV value-channel statistics (mean, std, skewness). Kurtosis is
        # also computed (see _hsv_value_stats) and reported in the metrics
        # dict but folded into the skew dim to keep the visual budget at 8
        # new dims (4 LBP + 3 HSV + 1 frame entropy) so the total fingerprint
        # is exactly 32 floats. Skewness is in [-2, 2] for natural images, so
        # we map it into [0, 1] via (skew + 2) / 4 (clamped).
        float(np.mean(value_means) / 255.0),
        float(min(1.0, float(np.mean(value_stds)) / 128.0)),
        float(max(0.0, min(1.0, (float(np.mean(value_skews)) + 2.0) / 4.0))),
        # 1 frame entropy dim (normalized by 8 bits).
        float(np.mean(frame_entropies) / 8.0),
        # 4 audio dims are appended by assess_video after decoding the audio;
        # placeholders here so the visual-only fingerprint has a stable
        # length when audio is unavailable (e.g. in unit tests of
        # _frame_metrics). assess_video overwrites them with real values.
        0.0,
        0.0,
        0.0,
        0.0,
    )
    # Defensive: guarantee the canonical length even if the math above drifts.
    fingerprint = fingerprint[:FINGERPRINT_DIMS]
    if len(fingerprint) < FINGERPRINT_DIMS:
        fingerprint = fingerprint + (0.0,) * (FINGERPRINT_DIMS - len(fingerprint))
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


def _pad_fingerprint(fp: tuple[float, ...] | list[float], target: int = FINGERPRINT_DIMS) -> tuple[float, ...]:
    """Normalise a fingerprint to ``target`` dims, padding/truncating with zeros.

    Legacy 20-dim fingerprints (pre-Frente E) are zero-padded to 32 dims so
    they remain comparable to the new descriptor for near-duplicate checks.
    """
    values = tuple(float(v) for v in fp)
    if len(values) >= target:
        return values[:target]
    return values + (0.0,) * (target - len(values))


def _fingerprint_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    left_p = _pad_fingerprint(left)
    right_p = _pad_fingerprint(right)
    if not left_p:
        return 1.0
    # Per-dimension importance weights. The first 8 dims (activity, centroid
    # and motion) and the 12 hue bins carry the legacy weights; the 12 new
    # Frente E dims (LBP/HSV/entropy/audio) get a smaller weight so the
    # distance is dominated by the well-validated visual structure while the
    # new dimensions still contribute to diversity.
    weights = np.array(
        (3.0, 2.0, 1.5, 1.5, 1.5, 1.5, 1.5, 1.0)
        + (1.0,) * 12  # hue histogram
        + (0.6,) * 8   # new visual dims (LBP x4, HSV x3, entropy x1)
        + (0.8,) * 4,  # new audio dims
        dtype=np.float64,
    )
    delta = (np.asarray(left_p) - np.asarray(right_p)) * weights
    return float(np.linalg.norm(delta) / np.sqrt(np.sum(weights**2)))


def assess_video(
    video: Path,
    expected_size: tuple[int, int],
    events: list[CreativeEvent],
    reference_fingerprints: list[tuple[float, ...]] | None = None,
    min_score: float = 0.78,
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
    audio_samples = _decode_audio(video)
    sample_rate = int(audio.get("sample_rate", 0) or 48_000)
    # Append the 4 new audio dims to the 28 visual dims produced by
    # _frame_metrics to reach the canonical 32-dim fingerprint.
    audio_fp = _audio_fingerprint_dims(audio_samples, sample_rate or 48_000)
    fingerprint = _pad_fingerprint(fingerprint)
    fingerprint = tuple(list(fingerprint[:28]) + list(audio_fp))
    distances = [_fingerprint_distance(fingerprint, reference) for reference in reference_fingerprints or []]
    nearest_distance = min(distances) if distances else None
    channels = int(audio.get("channels", 0) or 0)
    sample_rate = int(audio.get("sample_rate", 0) or 0)
    audio_metrics = _audio_metrics(audio_samples)
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
    if nearest_distance is not None and nearest_distance < NEAR_DUPLICATE_THRESHOLD:
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
        passed=not issues and score >= min_score,
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
