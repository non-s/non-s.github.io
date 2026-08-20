"""Versioned creative records shared by generation, perception and research.

The generator profile remains the engine's internal configuration.  These
records are the stable public contract persisted in video metadata.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

GENOME_VERSION = 2
VISUAL_DNA_VERSION = 1
AUDIO_DNA_VERSION = 1
ENGINE_VERSION = "4.2"
STRATEGY_VERSION = 2


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Genome:
    """Reproducible creative intent supplied to the procedural engine."""

    seed: int
    family: str
    preset: str
    generation: int
    geometry: dict[str, Any]
    motion: dict[str, Any]
    appearance: dict[str, Any]
    temporal: dict[str, Any]
    audio: dict[str, Any]
    puzzle: dict[str, Any] = field(default_factory=lambda: {"enabled": False})
    parents: tuple[str, ...] = ()
    mutations: tuple[dict[str, Any], ...] = ()
    strategy_version: int = STRATEGY_VERSION
    version: int = GENOME_VERSION

    @classmethod
    def from_profile(cls, profile: dict[str, Any], preset: str) -> Genome:
        raw_palette = profile.get("palette")
        palette: dict[str, Any] = raw_palette if isinstance(raw_palette, dict) else {}
        raw_composition = profile.get("composition")
        composition: dict[str, Any] = raw_composition if isinstance(raw_composition, dict) else {}
        timeline = profile.get("timeline") if isinstance(profile.get("timeline"), list) else []
        return cls(
            seed=int(profile["seed"]),
            family=str(profile.get("family", "unknown")),
            preset=preset,
            generation=max(0, int(profile.get("generation", 0))),
            geometry={
                "folds_theta": int(profile.get("folds_theta", 0)),
                "folds_phi": int(profile.get("folds_phi", 0)),
                "wire_density": profile.get("wire_density"),
                "strand_count": profile.get("strand_count"),
            },
            motion={
                "melt_rate": profile.get("melt_rate"),
                "rotation_rate": profile.get("rotation_rate"),
                "camera_speed": profile.get("camera_speed"),
            },
            appearance={
                "palette": palette,
                "haze": profile.get("haze_color"),
            },
            temporal={
                "opening_strategy": timeline[0].get("kind") if timeline and isinstance(timeline[0], dict) else None,
                "events": timeline,
            },
            audio={
                "genre": profile.get("genre", "lofi_ambient"),
                "music": profile.get("music", {}),
                "composition_mode": composition.get("mode"),
                "composition_id": profile.get("audio_composition_id"),
            },
            puzzle=profile.get("puzzle", {"enabled": False}),
            parents=tuple(str(value) for value in profile.get("parents", []) if value),
            mutations=tuple(value for value in profile.get("mutations", []) if isinstance(value, dict)),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Genome:
        """Load v1/v2 Genome metadata through an explicit, lossless migration."""
        version = int(payload.get("version", 1))
        if version > GENOME_VERSION:
            raise ValueError(f"unsupported future Genome version: {version}")
        migrated = dict(payload)
        if version == 1:
            migrated.setdefault("strategy_version", 1)
            migrated["version"] = GENOME_VERSION
        migrated["parents"] = tuple(str(value) for value in migrated.get("parents", ()))
        migrated["mutations"] = tuple(
            value for value in migrated.get("mutations", ()) if isinstance(value, dict)
        )
        return cls(**migrated)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def genome_id(self) -> str:
        return _canonical_hash(self.to_dict())[:24]


@dataclass(frozen=True)
class VisualDNA:
    """Observed properties of the final compressed render, never intent."""

    composition: dict[str, Any]
    motion: dict[str, Any]
    appearance: dict[str, Any]
    temporal: dict[str, Any]
    novelty: dict[str, Any]
    sample_count: int
    version: int = VISUAL_DNA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def dna_id(self) -> str:
        return _canonical_hash(self.to_dict())[:24]


@dataclass(frozen=True)
class AudioDNA:
    """Observed audio properties decoded from the final compressed video."""

    loudness: dict[str, Any]
    stereo: dict[str, Any]
    temporal: dict[str, Any]
    spectral: dict[str, Any]
    version: int = AUDIO_DNA_VERSION

    @classmethod
    def from_quality_report(cls, report: dict[str, Any]) -> AudioDNA:
        raw_fingerprint = report.get("fingerprint")
        fingerprint: list[Any] | tuple[Any, ...] = (
            raw_fingerprint if isinstance(raw_fingerprint, (list, tuple)) else []
        )
        spectral = list(fingerprint[-4:]) if len(fingerprint) >= 4 else [0.0] * 4
        return cls(
            loudness={"rms_db": report.get("audio_rms_db"), "peak": report.get("audio_peak")},
            stereo={"width": report.get("stereo_width"), "channels": report.get("audio_channels")},
            temporal={"silence_ratio": report.get("silence_ratio"), "visual_sync_signal": report.get("sync_signal")},
            spectral={
                "flux_mean": spectral[0],
                "flux_std": spectral[1],
                "harmonic_rhythm": spectral[2],
                "centroid_variance": spectral[3],
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def dna_id(self) -> str:
        return _canonical_hash(self.to_dict())[:24]


def content_id(genome: Genome, visual_dna: VisualDNA) -> str:
    """Stable identity for one requested genome and its observed output."""
    return f"lw_{_canonical_hash({'genome': genome.to_dict(), 'visual_dna': visual_dna.to_dict()})[:20]}"
