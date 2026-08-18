"""utils/render_config.py — centralized tuning constants for the renderer and quality gate.

Historically these magic numbers were scattered inline across
``generate_liquid_wire_video.py`` and ``utils/liquid_wire_quality.py``.
Centralizing them here makes the tuning surface explicit and lets a
maintainer adjust thresholds without hunting through 1500-line files.

Values are frozen at their original (production-tuned) defaults; changing
any of them shifts the visual/audio character of the channel.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderConfig:
    """Frame-rendering constants (``generate_liquid_wire_video.py``)."""

    fps: int = 30
    sample_rate: int = 44_100
    # Mesh resolution (theta x phi). Higher = denser wireframe.
    n_theta: int = 86
    n_phi: int = 42
    # Perspective projection denominator constant.
    perspective_near: float = 4.4
    perspective_scale: float = 1.72
    # JPEG quality for frame saves (supersampled pre-downscale).
    frame_jpeg_quality: int = 92
    # JPEG quality for the final thumbnail save.
    thumbnail_jpeg_quality: int = 94
    # FFmpeg encoding.
    ffmpeg_crf: int = 18
    ffmpeg_preset: str = "medium"
    ffmpeg_audio_bitrate: str = "160k"
    ffmpeg_timeout_seconds: int = 900
    # Supersampling factor (2 = render at 2x then LANCZOS downscale).
    ss_factor_default: int = 2
    # Multiprocessing worker cap.
    max_workers: int = 8


@dataclass(frozen=True)
class QualityGateConfig:
    """Perceptual quality-gate thresholds (``utils/liquid_wire_quality.py``)."""

    # Audio loudness (RMS in dB) must be within [min, max].
    audio_rms_db_min: float = -34.0
    audio_rms_db_max: float = -8.0
    # Peak amplitude above this = clipping.
    audio_clipping_peak: float = 0.999
    # Stereo width below this = mono-like.
    stereo_width_min: float = 0.01
    # Silence ratio above this = too much silence.
    silence_ratio_max: float = 0.20
    # Object occupancy (fraction of frame) must be within [min, max].
    object_occupancy_min: float = 0.018
    object_occupancy_max: float = 0.58
    # Border touch fraction above this = object touches frame edge.
    border_touch_max: float = 0.025
    # Motion below this = too static.
    motion_min: float = 0.10
    # Color variety below this = too monochrome.
    color_variety_min: int = 12
    # Score weights (must sum to ~1.0).
    weight_dimensions: float = 0.20
    weight_audio_format: float = 0.15
    weight_occupancy: float = 0.20
    weight_border: float = 0.15
    weight_motion: float = 0.18
    weight_color: float = 0.12
    # Near-duplicate distance threshold (32-dim fingerprint).
    near_duplicate_threshold: float = 0.04


RENDER = RenderConfig()
QUALITY = QualityGateConfig()
