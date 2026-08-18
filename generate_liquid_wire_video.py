"""Generate Liquid Wire videos from procedural visuals and synthetic audio.

This pipeline deliberately avoids stock footage and downloaded music. Every
frame is generated from deterministic math, and the ambient bed is synthesized
locally as simple layered sine waves.
"""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import logging
import math
import os
import secrets
import shutil
import subprocess
import wave
from datetime import UTC, datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from utils.ai_helper import ai_text
from utils.audio_mix import BUS_NAMES as MIX_BUS_NAMES
from utils.audio_mix import Mixer
from utils.chapter_markers import prepend_chapters
from utils.content_strategy import current_brt_hour, min_quality_score_for_slot
from utils.drums import DrumSequencer
from utils.dsp.dynamics import SideChainDuck
from utils.flow_field import FlowField, render_flow_particles
from utils.fluid_deform import fluid_deform
from utils.genres.registry import GENRES, get_genre
from utils.instruments import advanced as advanced_instruments
from utils.instruments import drums as drums_instruments
from utils.instruments import drums_extended as drums_extended_instruments
from utils.instruments import keys as keys_instruments
from utils.instruments import strings as strings_instruments
from utils.instruments import strings_extended as strings_extended_instruments
from utils.instruments import synth as synth_instruments
from utils.instruments import synth_extended as synth_extended_instruments
from utils.instruments import winds as winds_instruments
from utils.instruments import winds_extended as winds_extended_instruments
from utils.instruments.base import Instrument
from utils.instruments.base import NoteEvent as InstrumentNoteEvent
from utils.liquid_wire_composer import (
    MODES,
    CompositionPlan,
    build_composition,
    build_composition_for_genre,
)
from utils.liquid_wire_quality import QualityGateError, QualityReport, assess_video
from utils.liquid_wire_timeline import CreativeEvent, build_timeline, event_envelope, visual_state
from utils.organic_growth import OrganicGrowth, render_branches
from utils.particle_system import ParticleSystem
from utils.particle_system import render as render_particles
from utils.paths import data_dir
from utils.post_process import apply_all as apply_post
from utils.state_lock import state_lock

log = logging.getLogger(__name__)

# Registry mapping the instrument class names used by genre presets to the
# corresponding ``Instrument`` subclass. The genre presets store a string name
# (e.g. "AcousticPiano"); this table resolves it to the actual class so the
# synth engine can instantiate it for each instrument role.
INSTRUMENT_REGISTRY: dict[str, type[Instrument]] = {
    "AcousticPiano": keys_instruments.AcousticPiano,
    "ElectricPiano": keys_instruments.ElectricPiano,
    "Organ": keys_instruments.Organ,
    "Clavinet": keys_instruments.Clavinet,
    "Harpsichord": keys_instruments.Harpsichord,
    "StringEnsemble": strings_instruments.StringEnsemble,
    "BrassSection": strings_instruments.BrassSection,
    "AcousticGuitar": strings_instruments.AcousticGuitar,
    "DistortedGuitar": strings_instruments.DistortedGuitar,
    "BassGuitar": strings_instruments.BassGuitar,
    "Sitar": strings_instruments.Sitar,
    "Pad": synth_instruments.Pad,
    "Lead": synth_instruments.Lead,
    "SubBass": synth_instruments.SubBass,
    "SynthBass": synth_instruments.SynthBass,
    "Bell": synth_instruments.Bell,
    "Mallet": synth_instruments.Mallet,
    "Choir": synth_instruments.Choir,
    "Flute": winds_instruments.Flute,
    "Kalimba": winds_instruments.Kalimba,
    "Timpani": drums_instruments.Timpani,
    # Advanced high-fidelity instruments.
    "GlassHarp": advanced_instruments.GlassHarp,
    "MusicBox": advanced_instruments.MusicBox,
    "Theremin": advanced_instruments.Theremin,
    "PulsarSynth": advanced_instruments.PulsarSynth,
    "Dulcimer": advanced_instruments.Dulcimer,
    "Hang": advanced_instruments.Hang,
    "CrystalBow": advanced_instruments.CrystalBow,
    "WarmPad": advanced_instruments.WarmPad,
    # Extended winds (10 new instruments).
    "Clarinet": winds_extended_instruments.Clarinet,
    "Oboe": winds_extended_instruments.Oboe,
    "Saxophone": winds_extended_instruments.Saxophone,
    "Trumpet": winds_extended_instruments.Trumpet,
    "Trombone": winds_extended_instruments.Trombone,
    "Harmonica": winds_extended_instruments.Harmonica,
    "Accordion": winds_extended_instruments.Accordion,
    "Shakuhachi": winds_extended_instruments.Shakuhachi,
    "Ocarina": winds_extended_instruments.Ocarina,
    "Panpipes": winds_extended_instruments.Panpipes,
    # Extended strings (7 new instruments, physical modeling).
    "Violin": strings_extended_instruments.Violin,
    "Cello": strings_extended_instruments.Cello,
    "Harp": strings_extended_instruments.Harp,
    "Koto": strings_extended_instruments.Koto,
    "Banjo": strings_extended_instruments.Banjo,
    "Mandolin": strings_extended_instruments.Mandolin,
    "Ukulele": strings_extended_instruments.Ukulele,
    # Extended synthesizers (6 new instruments).
    "VocoderSynth": synth_extended_instruments.VocoderSynth,
    "WavetableSynth": synth_extended_instruments.WavetableSynth,
    "FMSynth": synth_extended_instruments.FMSynth,
    "GranularPad": synth_extended_instruments.GranularPad,
    "SupersawStereo": synth_extended_instruments.SupersawStereo,
    "ShimmerPad": synth_extended_instruments.ShimmerPad,
    # Extended percussion (16 new instruments).
    "Tambourine": drums_extended_instruments.Tambourine,
    "Conga": drums_extended_instruments.Conga,
    "Bongo": drums_extended_instruments.Bongo,
    "Cowbell": drums_extended_instruments.Cowbell,
    "Shaker": drums_extended_instruments.Shaker,
    "Woodblock": drums_extended_instruments.Woodblock,
    "Clave": drums_extended_instruments.Clave,
    "Agogo": drums_extended_instruments.Agogo,
    "Rimshot": drums_extended_instruments.Rimshot,
    "Sidestick": drums_extended_instruments.Sidestick,
    "China": drums_extended_instruments.China,
    "Splash": drums_extended_instruments.Splash,
    "Surdo": drums_extended_instruments.Surdo,
    "Caixa": drums_extended_instruments.Caixa,
    "Cuica": drums_extended_instruments.Cuica,
    "Tamborim": drums_extended_instruments.Tamborim,
}

# Map instrument-role names used in a GenrePreset to the canonical mixer bus.
# Roles not listed here fall back to a heuristic based on their name.
ROLE_TO_BUS: dict[str, str] = {
    "lead": "lead",
    "pad": "pads",
    "pads": "pads",
    "bass": "bass",
    "drums": "drums",
    "drone": "bass",
    "bell": "fx",
    "reverb_heavy": "pads",
    "strings": "lead",
    "brass": "lead",
    "choir": "pads",
    "timpani": "percussion",
    "rhythm": "guitar",
    "guitar": "guitar",
    "organ": "keys",
    "piano": "keys",
    "pluck": "lead",
}

# Saturation presets approximated inline (kept lightweight so the new engine
# remains pure-Python with no external convolution assets). Each entry maps a
# saturation style name from the genre presets to a drive/clip pair.
_SATURATION_PRESETS: dict[str, tuple[float, float]] = {
    "tape": (1.35, 0.72),
    "tube": (1.25, 0.78),
    "analog": (1.30, 0.75),
    "warm": (1.20, 0.80),
    "soft": (1.15, 0.85),
    "tight": (1.40, 0.70),
    "clean": (1.05, 0.92),
}


def _bus_for_role(role: str) -> str:
    """Resolve an instrument-role name to a canonical mixer bus name."""
    role_l = role.lower()
    if role_l in ROLE_TO_BUS and ROLE_TO_BUS[role_l] in MIX_BUS_NAMES:
        return ROLE_TO_BUS[role_l]
    # Heuristic fallbacks so unknown roles still route to a valid bus.
    if "bass" in role_l:
        return "bass"
    if "drum" in role_l or "perc" in role_l:
        return "drums"
    if "pad" in role_l or "choir" in role_l:
        return "pads"
    if "guitar" in role_l or "rhythm" in role_l:
        return "guitar"
    if "key" in role_l or "organ" in role_l or "piano" in role_l:
        return "keys"
    return "lead"


# Map genre instrument-role names to the composition voice they should play.
# The composer produces four voices: "bass", "motif" (melody), "pad" (harmony),
# and "gesture" (event-driven accents). Multiple genre roles can share the same
# voice — e.g. cinematic "strings" and "brass" both play the motif, layered —
# which creates a richer arrangement without requiring per-part composition.
ROLE_VOICE_MAPPING: dict[str, str] = {
    # Bass-type roles → bass voice.
    "bass": "bass",
    "drone": "bass",
    "timpani": "bass",
    "walking_bass": "bass",
    # Lead / melodic roles → motif voice (plus gesture accents).
    "lead": "motif",
    "strings": "motif",
    "brass": "motif",
    "piano": "motif",
    "pluck": "motif",
    "organ": "motif",
    "rhythm": "motif",
    "guitar": "motif",
    # Pad / harmonic roles → pad voice.
    "pad": "pad",
    "pads": "pad",
    "choir": "pad",
    "reverb_heavy": "pad",
    "bell": "pad",
    # Extended voices from composer_extended.
    "counter_melody": "motif",
    "arpeggio": "motif",
    "ostinato": "motif",
    "percussion": "bass",
}


def _voice_for_role(role: str) -> str:
    """Return the composition voice that feeds ``role`` (defaults to motif)."""
    return ROLE_VOICE_MAPPING.get(role.lower(), "motif")

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
FRAME_DIR = OUTPUT_DIR / "_liquid_wire_frames"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

FPS = 30
WIDTH = 1280
HEIGHT = 720
SAMPLE_RATE = 44_100

OBJECT_FAMILIES = (
    "orb",
    "torus",
    "ribbon",
    "double_orb",
    "membrane",
    "comet",
    "shell",
    "knot",
    "hourglass",
    "coral",
    "flow_field",
    "particle_swarm",
    "fluid_surface",
    "coral_growth",
    "crystal_lattice",
    "nebula_cloud",
    # New high-fidelity families.
    "helix",
    "gyroid",
    "mandelbulb",
    "torus_knot",
    "spiral_galaxy",
    "superformula",
    # Extended visual families (20 new).
    "mobius",
    "klein_bottle",
    "julia_set",
    "sierpinski",
    "voronoi_sphere",
    "lissajous_3d",
    "harmonograph",
    "hyperbolic_tiling",
    "smoke_plume",
    "fire_flame",
    "plasma_field",
    "lightning_bolt",
    "ink_in_water",
    "ferrofluid",
    "caustics",
    "dna_helix",
    "aurora",
    "accretion_disk",
    "gravitational_lens",
    "menger_sponge",
)

GENERATOR_HISTORY_LIMIT = 5000
QUALITY_HISTORY_LIMIT = 5000

# Supersampling factor: frames render at SS_FACTOR x resolution then downscale
# to the nominal 1080p output with LANCZOS for crisp anti-aliasing.
# Configurable via LIQUID_WIRE_SS_FACTOR env var so CI (limited 2-vCPU runners)
# can disable supersampling (SS=1) to fit the job timeout while local/dev
# machines keep SS=2 for maximum quality. Default is 2 to preserve the
# original behaviour for `make generate-short` and manual local runs.
SS_FACTOR = int(os.environ.get("LIQUID_WIRE_SS_FACTOR", "2"))


def _dimensions_for_preset(preset: str) -> tuple[int, int]:
    # 1080p: 9:16 short (1080x1920) or 16:9 long/live-test (1920x1080).
    return (1080, 1920) if preset == "short" else (1920, 1080)


# Families rendered through the dedicated special path instead of the mesh
# `_surface()` pipeline. They draw 2D particles/branches/fields directly.
SPECIAL_FAMILIES = frozenset({"flow_field", "particle_swarm", "coral_growth", "nebula_cloud"})


def _history_file() -> Path:
    return data_dir() / "generator_history.json"


def _record_quality(profile: dict, report: QualityReport) -> None:
    path = data_dir() / "quality_history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with state_lock(path):
        try:
            history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except (OSError, json.JSONDecodeError):
            history = []
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "created_at": datetime.now(UTC).isoformat(),
                "seed": profile["seed"],
                "signature": profile["signature"],
                "family": profile["family"],
                "engine_version": profile.get("engine_version"),
                **report.to_dict(),
            }
        )
        path.write_text(json.dumps(history[-QUALITY_HISTORY_LIMIT:], ensure_ascii=False, indent=2), encoding="utf-8")


def _recent_quality_fingerprints(limit: int = 96) -> list[tuple[float, ...]]:
    path = data_dir() / "quality_history.json"
    # Read under the same lock used by _record_quality to avoid a TOCTOU race
    # where a concurrent writer truncates the file mid-read (which would make
    # json.loads raise and silently disable near-duplicate detection).
    try:
        with state_lock(path):
            history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, json.JSONDecodeError):
        return []
    fingerprints: list[tuple[float, ...]] = []
    for item in history[-limit:] if isinstance(history, list) else []:
        if isinstance(item, dict) and not item.get("passed", True):
            continue
        values = item.get("fingerprint") if isinstance(item, dict) else None
        if isinstance(values, list) and values:
            fingerprints.append(tuple(float(value) for value in values))
    return fingerprints


# ---------------------------------------------------------------------------
# Style drift: a rotating subset of 3-4 genres that evolves weekly. The
# current subset is persisted in ``_data/style_drift.json`` so every video in
# a given week draws from the same family of genres, then the subset rotates
# to a new set of genres every 7 days. This keeps the channel's sound
# evolving slowly without ever jumping to a completely random genre per video.
# ---------------------------------------------------------------------------

_STYLE_DRIFT_FILE = "style_drift.json"
_STYLE_DRIFT_ROTATION_DAYS = 7
_STYLE_DRIFT_SUBSET_SIZE = 4


def _style_drift_path() -> Path:
    return data_dir() / _STYLE_DRIFT_FILE


def _today_date() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _days_between(start: str, end: str) -> int:
    try:
        a = datetime.strptime(start, "%Y-%m-%d").toordinal()
        b = datetime.strptime(end, "%Y-%m-%d").toordinal()
    except ValueError:
        return 0
    return abs(b - a)


def _load_style_drift() -> dict:
    """Load the persisted style-drift state, creating it if absent.

    Returns a dict with ``current_genres`` (list of genre names),
    ``week_start`` (ISO date string) and ``rotation`` (int counter).
    If the file does not exist (or is corrupt), a fresh state seeded from all
    registered genres is written and returned.
    """
    path = _style_drift_path()
    all_genres = sorted(GENRES.keys())
    fallback = {
        "current_genres": all_genres[: _STYLE_DRIFT_SUBSET_SIZE],
        "week_start": _today_date(),
        "rotation": 0,
    }
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("current_genres"), list):
                # Only keep genres that still exist in the registry.
                data["current_genres"] = [g for g in data["current_genres"] if g in GENRES]
                if not data["current_genres"]:
                    data = dict(fallback)
                return data
    except (OSError, json.JSONDecodeError):
        pass
    # Persist the fallback so subsequent calls are stable. Wrapped in a lock to
    # avoid a concurrent first-run race where two processes write the fallback
    # simultaneously and truncate each other's output.
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with state_lock(path):
            if not path.exists():
                path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return fallback


def _update_style_drift(force: bool = False) -> dict:
    """Rotate the genre subset if 7+ days have passed since ``week_start``.

    When ``force`` is True the rotation happens regardless of the elapsed
    time (used by tests). The new subset is chosen deterministically from the
    full genre list using the rotation counter as a seed so the rotation is
    reproducible across processes.
    """
    path = _style_drift_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with state_lock(path):
        data = _load_style_drift()
        today = _today_date()
        week_start = str(data.get("week_start", today))
        rotation = int(data.get("rotation", 0))
        elapsed = _days_between(week_start, today)
        if force or elapsed >= _STYLE_DRIFT_ROTATION_DAYS:
            rotation += 1
            rng = np.random.default_rng(rotation * 9973)
            all_genres = sorted(GENRES.keys())
            # Pick 3-4 new genres. Ensure at least one differs from the
            # previous subset so the rotation is always perceptible.
            size = min(_STYLE_DRIFT_SUBSET_SIZE, len(all_genres))
            previous = set(data.get("current_genres", []))
            for _ in range(8):
                subset = [str(g) for g in rng.choice(all_genres, size=size, replace=False)]
                if set(subset) != previous:
                    break
            data = {
                "current_genres": subset,
                "week_start": today,
                "rotation": rotation,
            }
            try:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
        return data


def _current_genres() -> list[str]:
    """Return the active style-drift genre subset (rotating as needed)."""
    data = _update_style_drift()
    genres = [g for g in data.get("current_genres", []) if g in GENRES]
    if not genres:
        genres = sorted(GENRES.keys())[:_STYLE_DRIFT_SUBSET_SIZE]
    return genres


def _pick_genre_for_seed(seed: int) -> str:
    """Deterministically select a genre from the current style-drift subset."""
    subset = _current_genres()
    if not subset:
        subset = sorted(GENRES.keys())
    rng = np.random.default_rng(seed ^ 0x5354594C45)
    return str(rng.choice(subset))


def _profile(seed: int, preset: str) -> dict:
    rng = np.random.default_rng(seed)
    family = str(rng.choice(OBJECT_FAMILIES))
    genre_name = _pick_genre_for_seed(seed)
    return {
        "family": family,
        "seed": seed,
        "preset": preset,
        "genre": genre_name,
        "phase": float(rng.uniform(0, 2 * np.pi)),
        "palette": {
            "base_hue": float(rng.uniform(0.0, 1.0)),
            "hue_span": float(rng.uniform(0.18, 0.72)),
            "hue_warp": float(rng.uniform(0.04, 0.28)),
            "hue_speed": float(rng.uniform(-0.025, 0.025)),
            "sat_a": float(rng.uniform(0.58, 0.96)),
            "sat_b": float(rng.uniform(0.04, 0.22)),
            "val_a": float(rng.uniform(0.74, 1.0)),
            "val_b": float(rng.uniform(0.04, 0.20)),
            "phase_r": float(rng.uniform(0, 2 * np.pi)),
            "phase_g": float(rng.uniform(0, 2 * np.pi)),
            "phase_b": float(rng.uniform(0, 2 * np.pi)),
        },
        "folds_theta": int(rng.integers(3, 9)),
        "folds_phi": int(rng.integers(3, 8)),
        "melt_rate": float(rng.uniform(0.18, 0.72)),
        "breath_rate": float(rng.uniform(0.35, 0.95)),
        "twist": float(rng.uniform(-0.75, 0.75)),
        "strand_count": int(rng.integers(7, 17)),
        "line_step": int(rng.integers(1, 4)),
        "material": {
            "glow_stride": int(rng.integers(3, 8)),
            "glow_radius": float(rng.uniform(4.0, 11.0)),
            "strand_width": int(rng.integers(1, 3)),
            "opacity": int(rng.integers(145, 216)),
        },
        "camera_yaw": float(rng.uniform(0.07, 0.22)),
        "camera_roll": float(rng.uniform(0.08, 0.30)),
        "music": {
            "key_shift": int(rng.integers(-6, 7)),
            "beat_seconds": float(rng.uniform(0.72, 1.12)),
            "meter": int(rng.choice((3, 4, 5))),
            "density": float(rng.uniform(0.55, 1.0)),
        },
        "flow_scale": float(rng.uniform(90.0, 160.0)),
        "fluid_speed": float(rng.uniform(0.35, 0.6)),
        "fluid_amp": float(rng.uniform(0.14, 0.26)),
        "growth_iterations": int(rng.integers(4, 7)),
        "post": {
            "bloom": {"enabled": True, "intensity": float(rng.uniform(0.4, 0.8))},
            "depth_of_field": {"enabled": True, "intensity": float(rng.uniform(0.3, 0.7))},
            "film_grain": {"enabled": True, "intensity": float(rng.uniform(0.5, 1.0))},
            "chromatic_aberration": {"enabled": True, "intensity": float(rng.uniform(0.3, 0.9))},
            "vignette": {"enabled": True, "intensity": float(rng.uniform(0.4, 0.9))},
            "hdr_tone_map": {"enabled": True, "intensity": float(rng.uniform(0.2, 0.5))},
            "depth_fog": {"enabled": True, "intensity": float(rng.uniform(0.2, 0.6))},
            "motion_blur": {
                "enabled": bool(rng.random() > 0.5),
                "intensity": float(rng.uniform(0.2, 0.6)),
                "angle": float(rng.uniform(0, 360)),
            },
        },
    }


def _signature(profile: dict) -> str:
    payload = json.dumps(profile, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _load_history() -> list[dict]:
    path = _history_file()
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _materially_distinct(profile: dict, history: list[dict]) -> bool:
    """Reject recent profiles that would read as the same work at a glance."""
    recent = [item for item in history[-48:] if isinstance(item, dict)]
    if any(item.get("family") == profile["family"] for item in recent[-2:]):
        return False
    hue = float(profile["palette"]["base_hue"])
    for item in recent:
        vector = item.get("creative_vector")
        if not isinstance(vector, dict) or item.get("family") != profile["family"]:
            continue
        old_hue = float(vector.get("hue", -1.0))
        hue_distance = min(abs(hue - old_hue), 1.0 - abs(hue - old_hue))
        same_topology = (
            int(vector.get("folds_theta", -99)) == int(profile["folds_theta"])
            and int(vector.get("folds_phi", -99)) == int(profile["folds_phi"])
        )
        similar_motion = abs(float(vector.get("melt_rate", -9.0)) - float(profile["melt_rate"])) < 0.10
        if hue_distance < 0.10 and (same_topology or similar_motion):
            return False
    return True


def _reserve_profile(preset: str, requested_seed: int | None) -> dict:
    path = _history_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with state_lock(path):
        history = _load_history()
        used_seeds = {int(item.get("seed", -1)) for item in history if isinstance(item, dict)}
        used_signatures = {str(item.get("signature", "")) for item in history if isinstance(item, dict)}
        for attempt in range(100):
            seed = requested_seed if requested_seed is not None and attempt == 0 else secrets.randbits(63)
            profile = _profile(seed, preset)
            signature = _signature(profile)
            if seed in used_seeds or signature in used_signatures or not _materially_distinct(profile, history):
                # If the caller asked for a specific seed and it already exists in
                # the history, fall through to a random seed on the next loop
                # iteration instead of failing hard. A collision means the
                # profile was already reserved (either the render succeeded and
                # was published, or it failed after reservation and the seed
                # was never released). Either way the caller wants a *new*
                # render now, so reproducing the exact same seed is not
                # useful; a fresh random seed gives a materially distinct
                # video. Previously this raised ValueError, which broke
                # scheduled long-form runs whose deterministic slot seed
                # collided with an earlier short in the same UTC hour, and
                # also broke manual dispatches after any prior ad-hoc render.
                continue
            profile["signature"] = signature
            history.append(
                {
                    "seed": seed,
                    "signature": signature,
                    "family": profile["family"],
                    "preset": preset,
                    "creative_vector": {
                        "hue": profile["palette"]["base_hue"],
                        "folds_theta": profile["folds_theta"],
                        "folds_phi": profile["folds_phi"],
                        "melt_rate": profile["melt_rate"],
                        "music": profile["music"],
                    },
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            if len(history) > GENERATOR_HISTORY_LIMIT:
                history = history[-GENERATOR_HISTORY_LIMIT:]
            path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            return profile
    raise RuntimeError("Could not reserve a unique Liquid Wire generator profile.")


def _deform_radius(
    theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list[CreativeEvent]
) -> np.ndarray:
    phase = float(profile["phase"])
    folds_theta = int(profile["folds_theta"])
    folds_phi = int(profile["folds_phi"])
    melt_rate = float(profile["melt_rate"])
    breath_rate = float(profile["breath_rate"])
    breath = 0.14 * np.sin(breath_rate * t + phase)
    fold_a = 0.22 * np.sin(folds_theta * theta + 2.2 * np.sin(phi * 3 + t * 0.55 + phase))
    fold_b = 0.13 * np.cos(folds_phi * phi - 0.75 * t + np.sin(theta * 2 + phase))
    melt = 0.11 * np.sin((folds_theta + 3) * theta + (folds_phi + 1) * phi + t * melt_rate)
    slow_pull = 0.08 * np.cos(2 * theta - 3 * phi + t * 0.18 + phase)
    state = visual_state(t, events)
    directional = np.cos(theta - math.atan2(state["direction_y"], state["direction_x"] + 1e-9))
    bloom = state["bloom"] * (0.22 + 0.10 * np.sin(3 * phi))
    compression = -state["compression"] * (0.18 + 0.08 * directional)
    rupture = state["rupture"] * 0.24 * np.sign(np.sin((folds_theta + 1) * theta + phase))
    tide = state["tide"] * 0.18 * np.sin(phi * 2 + theta + t * 0.35)
    stillness = max(0.25, 1.0 - state["stillness"] * 0.72)
    return 1.0 + stillness * (breath + fold_a + fold_b + melt + slow_pull) + bloom + compression + rupture + tide


def _rotate(points: np.ndarray, ax: float, ay: float, az: float) -> np.ndarray:
    sx, cx = math.sin(ax), math.cos(ax)
    sy, cy = math.sin(ay), math.cos(ay)
    sz, cz = math.sin(az), math.cos(az)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return points @ (rz @ ry @ rx).T


def _surface(
    t: float, profile: dict, events: list[CreativeEvent], n_theta: int = 86, n_phi: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    theta = np.linspace(0, 2 * np.pi, n_theta)
    phi = np.linspace(0.06, np.pi - 0.06, n_phi)
    th, ph = np.meshgrid(theta, phi)
    radius = _deform_radius(th, ph, t, profile, events)
    family = str(profile["family"])
    twist = float(profile["twist"])
    if family == "torus":
        tube = 0.38 + 0.08 * np.sin(5 * th + t)
        ring = 1.0 + 0.18 * np.sin(3 * ph + t * 0.4)
        x = (ring + tube * radius * np.cos(ph)) * np.cos(th + twist * np.sin(ph + t * 0.1))
        y = (ring + tube * radius * np.cos(ph)) * np.sin(th + twist * np.sin(ph + t * 0.1))
        z = tube * radius * np.sin(ph)
    elif family == "ribbon":
        band = np.sin(ph)
        x = radius * (1.4 + 0.2 * np.sin(3 * th + t)) * np.cos(th)
        y = 0.42 * radius * np.cos(ph + twist * np.sin(th + t * 0.2))
        z = radius * band * np.sin(th + twist * np.cos(ph))
    elif family == "double_orb":
        shift = 0.55 * np.sign(np.cos(th))
        x = radius * np.sin(ph) * np.cos(th) + shift
        y = radius * np.sin(ph) * np.sin(th) * 0.86
        z = radius * np.cos(ph)
    elif family == "membrane":
        x = 1.35 * np.cos(th) * np.sin(ph)
        y = 0.55 * radius * np.sin(2 * ph + twist * np.sin(th + t * 0.25))
        z = 1.05 * np.sin(th) * np.sin(ph)
    elif family == "comet":
        tail = 1.0 + 0.95 * (np.cos(th) > 0) * np.sin(ph) ** 2
        x = tail * radius * np.sin(ph) * np.cos(th)
        y = radius * np.sin(ph) * np.sin(th) * (0.75 + 0.15 * np.sin(t))
        z = radius * np.cos(ph)
    elif family == "shell":
        spiral = 0.34 + 0.18 * th / (2 * np.pi)
        chamber = 0.72 + 0.30 * np.sin(ph)
        x = chamber * radius * np.cos(th) + spiral * np.cos(th * 2.0)
        y = chamber * radius * np.sin(th) + spiral * np.sin(th * 2.0)
        z = 1.15 * np.cos(ph) + 0.22 * th / np.pi
    elif family == "knot":
        knot = 1.0 + 0.24 * np.cos(3 * th + twist * np.sin(ph))
        x = knot * np.cos(2 * th) + 0.26 * radius * np.sin(ph) * np.cos(th)
        y = knot * np.sin(2 * th) + 0.26 * radius * np.sin(ph) * np.sin(th)
        z = 0.72 * np.sin(3 * th) + 0.30 * radius * np.cos(ph)
    elif family == "hourglass":
        waist = 0.38 + 0.75 * np.abs(np.cos(ph)) ** 1.6
        x = waist * radius * np.cos(th)
        y = waist * radius * np.sin(th)
        z = 1.35 * np.cos(ph) + 0.12 * np.sin(4 * th + t * 0.3)
    elif family == "coral":
        branches = 1.0 + 0.25 * np.sin(5 * th + 3 * ph) + 0.16 * np.sin(9 * th - 2 * ph + t * 0.2)
        x = branches * radius * np.sin(ph) * np.cos(th)
        y = branches * radius * np.sin(ph) * np.sin(th)
        z = 1.15 * radius * np.cos(ph) + 0.18 * np.sin(6 * th)
    elif family == "fluid_surface":
        # Wave-deformed sphere: apply the ripple field as a radial displacement
        # so the mesh reads as a liquid surface rippling around the form.
        dtheta, dphi = fluid_deform(th, ph, t, profile, events)
        ang_th = th + dtheta
        ang_ph = ph + dphi
        ripple = 0.30 * np.sin(6 * ang_th + 3 * ang_ph + t * 1.1)
        x = (radius + ripple) * np.sin(ang_ph) * np.cos(ang_th)
        y = (radius + ripple) * np.sin(ang_ph) * np.sin(ang_th)
        z = (radius + ripple) * np.cos(ang_ph)
    elif family == "crystal_lattice":
        # Faceted lattice with a refraction-like colour split: the radial
        # displacement is quantised to flat facets and a secondary offset layer
        # produces the prismatic double-edge effect.
        facet = np.round(radius * 4.0) / 4.0
        x = facet * np.sin(ph) * np.cos(th)
        y = facet * np.sin(ph) * np.sin(th)
        z = facet * np.cos(ph)
    elif family == "helix":
        # Double helix: two intertwined spirals around a central axis.
        turns = 3.0 + twist * 2.0
        helix_angle = th * turns + t * 0.5
        r_helix = 0.55 + 0.12 * np.sin(th * 2 + t * 0.8)
        strand = np.sign(np.cos(th * turns * 0.5))
        x = r_helix * radius * np.cos(helix_angle) * np.sin(ph)
        y = radius * np.cos(ph) * 0.9
        z = r_helix * radius * np.sin(helix_angle) * np.sin(ph) + 0.3 * strand * np.sin(ph)
    elif family == "gyroid":
        # Gyroid minimal surface approximation: triply periodic surface.
        # Used as a radial displacement on a sphere for an organic lattice.
        u = th * 2 + t * 0.3
        v = ph * 3 - t * 0.2
        w_param = (th + ph) * 1.5 + t * 0.15
        gyroid = np.sin(u) * np.cos(v) + np.sin(v) * np.cos(w_param) + np.sin(w_param) * np.cos(u)
        r_g = radius * (0.85 + 0.25 * np.tanh(gyroid * 0.8))
        x = r_g * np.sin(ph) * np.cos(th)
        y = r_g * np.sin(ph) * np.sin(th)
        z = r_g * np.cos(ph)
    elif family == "mandelbulb":
        # Mandelbulb-inspired fractal surface (low-order approximation).
        # Uses a power-2 iteration as a radial displacement for performance.
        nx = np.sin(ph) * np.cos(th)
        ny = np.sin(ph) * np.sin(th)
        nz = np.cos(ph)
        # 3 iterations of the mandelbulb formula (vectorized).
        zx, zy, zz = nx, ny, nz
        for _ in range(3):
            r_mag = np.sqrt(zx**2 + zy**2 + zz**2 + 1e-12)
            theta_m = np.arccos(np.clip(zz / r_mag, -1.0, 1.0))
            phi_m = np.arctan2(zy, zx)
            new_r = r_mag**2
            zx = new_r * np.sin(theta_m * 2) * np.cos(phi_m * 2) + nx * 0.7
            zy = new_r * np.sin(theta_m * 2) * np.sin(phi_m * 2) + ny * 0.7
            zz = new_r * np.cos(theta_m * 2) + nz * 0.7
        r_mb = np.sqrt(zx**2 + zy**2 + zz**2)
        r_mb = np.clip(r_mb, 0.3, 2.0) * radius
        x = r_mb * np.sin(ph) * np.cos(th)
        y = r_mb * np.sin(ph) * np.sin(th)
        z = r_mb * np.cos(ph)
    elif family == "torus_knot":
        # Torus knot (p,q)=(3,2): a single closed loop woven through a torus.
        p, q = 3.0, 2.0
        knot_t = th * 2 * np.pi
        knot_r = 1.0 + 0.4 * np.cos(p * knot_t + t * 0.4)
        knot_s = 0.3 + 0.15 * np.sin(q * knot_t + t * 0.6)
        x = (knot_r + knot_s * radius * np.cos(ph)) * np.cos(q * knot_t)
        y = (knot_r + knot_s * radius * np.cos(ph)) * np.sin(q * knot_t)
        z = knot_s * radius * np.sin(ph)
    elif family == "spiral_galaxy":
        # Spiral galaxy: logarithmic spiral arms with radial brightness.
        arms = 3
        arm_angle = th + 0.5 * np.log(0.3 + ph + t * 0.05) * arms
        r_gal = (0.3 + 0.9 * ph / np.pi) * radius
        x = r_gal * np.cos(arm_angle + t * 0.15)
        y = r_gal * np.sin(arm_angle + t * 0.15) * 0.5
        z = r_gal * np.sin(ph * 4 + t * 0.3) * 0.3
    elif family == "superformula":
        # Gielis superformula: generates natural-looking shapes (starfish,
        # flowers, etc.) from a compact parametric form.
        m = 6.0 + 2.0 * np.sin(t * 0.3)
        n1 = 0.3 * radius
        n2 = 1.7
        n3 = 1.7
        sf_theta = th * m / 2.0 + t * 0.2
        r_sf = (np.abs(np.cos(sf_theta))**n2 + np.abs(np.sin(sf_theta))**n3) ** (-1.0 / n1)
        r_sf = np.clip(r_sf, 0.3, 2.0)
        x = r_sf * np.sin(ph) * np.cos(th)
        y = r_sf * np.sin(ph) * np.sin(th)
        z = r_sf * np.cos(ph)
    else:
        x = radius * np.sin(ph) * np.cos(th)
        y = radius * np.sin(ph) * np.sin(th)
        z = radius * np.cos(ph)
    pts = np.stack([x, y, z], axis=-1).reshape(-1, 3)
    pts = _rotate(
        pts,
        0.42 + 0.08 * np.sin(t * 0.4 + float(profile["phase"])),
        float(profile["camera_yaw"]) * t,
        float(profile["camera_roll"]) * np.cos(t * 0.23),
    )
    x, y, z = pts[:, 0].reshape(ph.shape), pts[:, 1].reshape(ph.shape), pts[:, 2].reshape(ph.shape)
    scale = 1.72 / (4.4 - z)
    sx = WIDTH * 0.5 + x * scale * WIDTH * 0.40
    sy = HEIGHT * 0.5 + y * scale * HEIGHT * 0.50
    return sx, sy


def _rgb(value: float, t: float, palette: dict) -> tuple[int, int, int, int]:
    warped = value + float(palette["hue_warp"]) * math.sin(value * 2 * math.pi + t * 0.15)
    hue = (float(palette["base_hue"]) + warped * float(palette["hue_span"]) + t * float(palette["hue_speed"])) % 1.0
    sat = float(palette["sat_a"]) + float(palette["sat_b"]) * math.sin(
        value * 8.1 + t * 0.37 + float(palette["phase_r"])
    )
    val = float(palette["val_a"]) + float(palette["val_b"]) * math.sin(
        value * 5.7 - t * 0.23 + float(palette["phase_g"])
    )
    r, g, b = colorsys.hsv_to_rgb(hue, max(0.35, min(1.0, sat)), max(0.45, min(1.0, val)))
    # A tiny RGB shimmer adds the "thousand colors mixed" feel without relying on named palettes.
    shimmer = 0.08 * math.sin(value * 17.0 + t * 0.91 + float(palette["phase_b"]))
    return (
        int(max(0, min(255, (r + shimmer) * 255))),
        int(max(0, min(255, (g - shimmer * 0.5) * 255))),
        int(max(0, min(255, (b + shimmer * 0.25) * 255))),
        170,
    )


def _rupture_visibility(cols: int, state: dict[str, float]) -> np.ndarray:
    """Open directional cracks in mesh connectivity during rupture events."""
    rupture = min(1.0, max(0.0, state["rupture"]))
    if rupture < 0.02:
        return np.ones(cols, dtype=bool)
    center = (math.atan2(state["direction_y"], state["direction_x"] + 1e-9) / (2 * np.pi)) % 1.0
    positions = np.arange(cols, dtype=np.float64) / max(1, cols - 1)
    primary = np.minimum(np.abs(positions - center), 1.0 - np.abs(positions - center))
    opposite = (center + 0.5) % 1.0
    secondary = np.minimum(np.abs(positions - opposite), 1.0 - np.abs(positions - opposite))
    return (primary > 0.012 + rupture * 0.072) & (secondary > max(0.0, rupture - 0.45) * 0.032)


def _draw_visible_polyline(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    visible: np.ndarray,
    fill: tuple[int, int, int, int],
    width: int,
) -> None:
    for index in range(len(points) - 1):
        if visible[index] and visible[index + 1]:
            draw.line((points[index], points[index + 1]), fill=fill, width=width)


def _draw_frame_special(
    index: int, frame_count: int, profile: dict, events: list[CreativeEvent], frame_dir: Path
) -> Path:
    """Render non-mesh families (flow field, particle swarm, coral, nebula)."""
    t = index / FPS
    palette = profile["palette"]
    family = str(profile["family"])
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), "#000000ff")
    lines = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(lines)
    glow_draw = ImageDraw.Draw(glow)

    if family == "flow_field":
        # Constrain the field to a central margin so trails never reach the
        # frame border (the quality gate rejects objects touching the edge).
        margin = 0.10
        fw = WIDTH * (1.0 - 2.0 * margin)
        fh = HEIGHT * (1.0 - 2.0 * margin)
        ox, oy = WIDTH * margin, HEIGHT * margin
        field = FlowField(int(profile["seed"]), float(fw), float(fh), float(profile.get("flow_scale", 120.0)))
        trails = render_flow_particles(field, t, num_particles=240, trail_length=22)
        for ti, trail in enumerate(trails):
            color = _rgb(ti / max(1, len(trails)), t, palette)[:3] + (170,)
            glow_color = _rgb(ti / max(1, len(trails)), t, palette)[:3] + (60,)
            shifted = [(ox + px, oy + py) for px, py in trail]
            draw.line(shifted, fill=color, width=2, joint="curve")
            glow_draw.line(shifted, fill=glow_color, width=5, joint="curve")

    elif family == "particle_swarm":
        margin = 0.08
        fw = WIDTH * (1.0 - 2.0 * margin)
        fh = HEIGHT * (1.0 - 2.0 * margin)
        ox, oy = WIDTH * margin, HEIGHT * margin
        system = ParticleSystem(int(profile["seed"]), 380, float(fw), float(fh))
        # Warm the system forward to the current frame so motion is continuous.
        steps = max(1, int(t / 0.033))
        for step in range(steps):
            system.update(dt=0.033, t=step * 0.033)
        psx, psy = render_particles(system, profile, t, int(fw), int(fh))
        for i in range(system.num_particles):
            color = _rgb(i / system.num_particles, t, palette)[:3] + (210,)
            glow_color = _rgb(i / system.num_particles, t, palette)[:3] + (80,)
            x, y = float(psx[i]) + ox, float(psy[i]) + oy
            dot_r = 3
            draw.ellipse((x - dot_r, y - dot_r, x + dot_r, y + dot_r), fill=color)
            gr = 8
            glow_draw.ellipse((x - gr, y - gr, x + gr, y + gr), fill=glow_color)

    elif family == "coral_growth":
        iterations = int(profile.get("growth_iterations", 5))
        growth = OrganicGrowth(int(profile["seed"]), iterations, angle_range=0.62, length_decay=0.74)
        branches = growth.grow()
        bsx, bsy = render_branches(branches, t, profile, WIDTH, HEIGHT)
        n = len(branches)
        for bi in range(n):
            x0, y0 = float(bsx[bi * 2]), float(bsy[bi * 2])
            x1, y1 = float(bsx[bi * 2 + 1]), float(bsy[bi * 2 + 1])
            color = _rgb(bi / max(1, n), t, palette)[:3] + (210,)
            glow_color = _rgb(bi / max(1, n), t, palette)[:3] + (75,)
            width_px = max(2, int(2.5 * branches[bi].thickness))
            draw.line((x0, y0, x1, y1), fill=color, width=width_px, joint="curve")
            glow_draw.line((x0, y0, x1, y1), fill=glow_color, width=width_px + 6, joint="curve")

    elif family == "nebula_cloud":
        # Soft glowing particle cloud: many low-alpha blobs composited with a
        # gaussian to simulate a cosmic nebula drifting in the void.
        rng = np.random.default_rng(int(profile["seed"]))
        count = 260
        margin = 0.10
        cx, cy = WIDTH * 0.5, HEIGHT * 0.5
        radii = rng.uniform(0.0, min(WIDTH, HEIGHT) * 0.24, size=count)
        angles = rng.uniform(0.0, 2.0 * math.pi, size=count)
        per_speed = rng.uniform(0.5, 1.6, size=count)
        # Faster per-particle drift plus radial pulsing keeps the cloud moving.
        drift = 0.5 * t * per_speed
        pulse = 0.10 * math.sin(t * 0.9)
        radii_t = radii * (1.0 + pulse)
        xs = cx + radii_t * np.cos(angles + drift)
        ys = cy + radii_t * np.sin(angles + drift) * 0.72
        sizes = rng.uniform(20.0, 70.0, size=count) * (1.0 + 0.15 * np.sin(t * 1.4 + angles))
        for i in range(count):
            color = _rgb(i / count, t, palette)[:3] + (30,)
            x, y, radius = float(xs[i]), float(ys[i]), float(max(6.0, sizes[i]))
            glow_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)

    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18.0)))
    canvas.alpha_composite(lines)
    out = frame_dir / f"frame_{index:05d}.png"
    canvas.convert("RGB").save(out, quality=92)
    return out


def _draw_frame(
    index: int, frame_count: int, profile: dict, events: list[CreativeEvent], frame_dir: Path
) -> Path:
    family = str(profile["family"])
    try:
        if family in SPECIAL_FAMILIES:
            frame_path = _draw_frame_special(index, frame_count, profile, events, frame_dir)
        else:
            frame_path = _draw_frame_mesh(index, frame_count, profile, events, frame_dir)
    except Exception:
        # Graceful degradation: if a new family crashes (e.g. numerical
        # instability in a fractal), fall back to the simple orb family so
        # the render completes rather than producing a corrupt video.
        fallback_profile = dict(profile)
        fallback_profile["family"] = "orb"
        frame_path = _draw_frame_mesh(index, frame_count, fallback_profile, events, frame_dir)
    # Post-processing (applied per frame, after drawing and before final save).
    if frame_path is not None and isinstance(profile.get("post"), dict):
        with Image.open(frame_path) as raw:
            img = raw.convert("RGB")
            try:
                processed = apply_post(img, profile)
            except Exception:
                processed = img
            processed.save(frame_path, quality=92)
    return frame_path


def _draw_frame_mesh(
    index: int, frame_count: int, profile: dict, events: list[CreativeEvent], frame_dir: Path
) -> Path:
    t = index / FPS
    sx, sy = _surface(t, profile, events)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), "#000000ff")
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    lines = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    draw = ImageDraw.Draw(lines)
    rows, cols = sx.shape

    palette = profile["palette"]
    material = profile["material"]
    state = visual_state(t, events)
    visible = _rupture_visibility(cols, state)
    for i in range(rows):
        pts = [(float(sx[i, j]), float(sy[i, j])) for j in range(cols)]
        color = _rgb(i / rows, t, palette)[:3] + (int(material["opacity"]),)
        _draw_visible_polyline(draw, pts, visible, color, 1)
        if i % int(material["glow_stride"]) == 0:
            _draw_visible_polyline(glow_draw, pts, visible, color[:3] + (55,), 4)

    for j in range(0, cols, int(profile["line_step"])):
        if not visible[j]:
            continue
        pts = [(float(sx[i, j]), float(sy[i, j])) for i in range(rows)]
        draw.line(pts, fill=_rgb(j / cols + 0.4, t, palette)[:3] + (95,), width=1, joint="curve")

    for strand in range(int(profile["strand_count"])):
        strand_count = int(profile["strand_count"])
        col = int((strand * cols / strand_count + index * 0.07) % cols)
        if not visible[col]:
            continue
        wobble = 14 * np.sin(np.linspace(0, 2 * np.pi, rows) + t * 0.6 + strand)
        pts = [(float(sx[i, col]), float(sy[i, col] + wobble[i])) for i in range(rows)]
        draw.line(
            pts,
            fill=_rgb(strand / strand_count + 0.72, t, palette)[:3] + (115,),
            width=int(material["strand_width"]),
            joint="curve",
        )
        glow_draw.line(pts, fill=_rgb(strand / strand_count + 0.72, t, palette)[:3] + (50,), width=6, joint="curve")

    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(float(material["glow_radius"]))))
    canvas.alpha_composite(lines)
    out = frame_dir / f"frame_{index:05d}.png"
    canvas.convert("RGB").save(out, quality=92)
    return out


def _synth_audio_lofi(
    path: Path,
    duration: float,
    seed: int,
    profile: dict,
    events: list[CreativeEvent] | None = None,
    composition: CompositionPlan | None = None,
) -> None:
    """Backwards-compatible lo-fi piano synth (the original _synth_audio).

    Kept as a dedicated function so the well-tuned ``lofi_ambient`` genre keeps
    producing the exact same output that already passes the quality gate, while
    every other genre routes through the new universal instrument/mixer engine.
    """
    rng = np.random.default_rng(seed)
    _warn_audio_memory(duration, SAMPLE_RATE)
    count = int(duration * SAMPLE_RATE)
    t = np.linspace(0, duration, count, endpoint=False)
    signal = np.zeros(count, dtype=np.float64)

    # Seeded neo-soul progressions keep every piece original while preserving
    # the warm, suspended harmony associated with instrumental lo-fi.
    music = profile["music"]
    events = events or build_timeline(seed, duration, music)
    composition = composition or build_composition(seed, duration, music, events)
    scale = MODES[composition.mode]
    roots = np.array(
        [composition.tonic + scale[degree % len(scale)] for degree in composition.progression], dtype=int
    )
    chord_shapes = ([0, 3, 7, 10], [0, 4, 7, 11], [0, 3, 7, 10, 14], [0, 5, 7, 10])
    beat_seconds = float(music["beat_seconds"])
    meter = int(music["meter"])
    density = float(music["density"])
    chord_seconds = beat_seconds * meter

    def midi_hz(note: float) -> float:
        return 440.0 * 2 ** ((note - 69.0) / 12.0)

    def add_piano(note: int, start: float, length: float, gain: float) -> None:
        start_i = max(0, int(start * SAMPLE_RATE))
        end_i = min(count, start_i + int(length * SAMPLE_RATE))
        if end_i <= start_i:
            return
        local_t = np.arange(end_i - start_i, dtype=np.float64) / SAMPLE_RATE
        freq = midi_hz(note + float(rng.normal(0, 0.025)))
        attack = np.minimum(1.0, local_t / 0.012)
        decay = np.exp(-local_t * float(rng.uniform(1.7, 2.25)))
        body = (
            np.sin(2 * np.pi * freq * local_t)
            + 0.42 * np.sin(2 * np.pi * freq * 2.01 * local_t + 0.3)
            + 0.18 * np.sin(2 * np.pi * freq * 3.98 * local_t + 0.9)
        )
        hammer = 0.08 * rng.normal(0, 1, len(local_t)) * np.exp(-local_t * 24.0)
        signal[start_i:end_i] += gain * attack * decay * (body + hammer)

    for note in composition.notes:
        add_piano(note.note, note.start, note.duration, note.velocity)

    chord_index = 0
    for chord_start in np.arange(0.0, duration + chord_seconds, chord_seconds):
        root = int(roots[chord_index % len(roots)])
        shape = chord_shapes[int(rng.integers(0, len(chord_shapes)))]
        velocity = float(rng.uniform(0.075, 0.105))
        for position, interval in enumerate(shape):
            humanize = float(rng.uniform(-0.028, 0.045)) + position * 0.018
            add_piano(root + 12 + interval, chord_start + humanize, chord_seconds * 1.55, velocity)
        # A small answering note makes the loop feel performed rather than tiled.
        if rng.random() < density:
            answer_at = beat_seconds * float(rng.uniform(1.4, max(1.5, meter - 0.35)))
            add_piano(root + 24 + int(rng.choice(shape)), chord_start + answer_at, beat_seconds, 0.045)
        chord_index += 1

    # Soft bass, kick and brushed snare follow the same clock as the chords.
    for beat, beat_start in enumerate(np.arange(0.0, duration, beat_seconds)):
        root = int(roots[(beat // meter) % len(roots)])
        start_i = int(beat_start * SAMPLE_RATE)
        end_i = min(count, start_i + int(beat_seconds * SAMPLE_RATE))
        local_t = np.arange(end_i - start_i, dtype=np.float64) / SAMPLE_RATE
        bass = np.sin(2 * np.pi * midi_hz(root - 12) * local_t) * np.exp(-local_t * 2.8)
        signal[start_i:end_i] += 0.055 * bass
        position = beat % meter
        if position in {0, max(1, meter // 2)}:
            kick = np.sin(2 * np.pi * (62 * local_t - 22 * local_t**2)) * np.exp(-local_t * 18)
            signal[start_i:end_i] += 0.075 * kick
        if position == max(1, meter // 2):
            brush = rng.normal(0, 1, len(local_t)) * np.exp(-local_t * 15)
            signal[start_i:end_i] += 0.022 * brush

    # The dramatic score is shared with the geometry: every visual event gets
    # a restrained musical gesture and a matching dynamic envelope.
    dynamics = np.ones(count, dtype=np.float64)
    for event in events:
        envelope = np.asarray(event_envelope(t, event), dtype=np.float64)
        if event.kind == "stillness":
            dynamics *= 1.0 - envelope * 0.48 * event.intensity
        elif event.kind in {"bloom", "rupture"}:
            dynamics *= 1.0 + envelope * 0.14 * event.intensity
    signal *= dynamics

    # Tape hiss, slow wow and gentle saturation finish the lo-fi texture.
    hiss = rng.normal(0, 1, count)
    hiss = np.convolve(hiss, np.ones(7) / 7, mode="same")
    wow = 0.96 + 0.04 * np.sin(2 * np.pi * float(rng.uniform(0.08, 0.16)) * t + rng.uniform(0, 2 * np.pi))
    signal = np.tanh((signal * wow + 0.008 * hiss) * 1.35) * 0.72
    fade = min(count // 8, SAMPLE_RATE * 3)
    ramp = np.linspace(0, 1, fade)
    signal[:fade] *= ramp
    signal[-fade:] *= ramp[::-1]
    signal = np.clip(signal, -0.85, 0.85)
    # A restrained decorrelated stereo field gives the piano space without
    # relying on convolution impulses or any external audio asset.
    delay = max(1, int(SAMPLE_RATE * 0.013))
    delayed = np.zeros_like(signal)
    delayed[delay:] = signal[:-delay]
    left = np.clip(signal * 0.92 + delayed * 0.08, -0.85, 0.85)
    right = np.clip(signal * 0.84 + delayed * 0.16, -0.85, 0.85)
    samples = (np.column_stack((left, right)) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(samples.tobytes())


def _event_dynamics_envelope(duration: float, events: list[CreativeEvent]) -> np.ndarray:
    """Build the audio-visual sync dynamics envelope from creative events.

    This is the same envelope the original lo-fi path applied inline: stillness
    ducks the music, bloom/rupture swell it. Returned as a mono float64 array
    of length ``duration * SAMPLE_RATE`` so it can be multiplied onto the
    mixed master bus of the new engine.
    """
    count = int(duration * SAMPLE_RATE)
    t = np.linspace(0, duration, count, endpoint=False)
    dynamics = np.ones(count, dtype=np.float64)
    for event in events:
        envelope = np.asarray(event_envelope(t, event), dtype=np.float64)
        if event.kind == "stillness":
            dynamics *= 1.0 - envelope * 0.48 * event.intensity
        elif event.kind in {"bloom", "rupture"}:
            dynamics *= 1.0 + envelope * 0.14 * event.intensity
    return dynamics


def _render_instrument_role(
    role: str,
    instrument_name: str,
    notes: list,
    seed: int,
    sample_rate: int,
    n: int,
) -> np.ndarray:
    """Render the composition voice assigned to ``role`` through its instrument.

    ``notes`` are :class:`utils.liquid_wire_composer.NoteEvent` instances. The
    voice played is determined by :func:`_voice_for_role` so multiple genre
    roles (e.g. "strings" and "brass") can layer the same voice on different
    instruments. Returns a mono float64 buffer of length ``n``.
    """
    cls = INSTRUMENT_REGISTRY.get(instrument_name)
    if cls is None:
        return np.zeros(n, dtype=np.float64)
    # All registered instrument subclasses accept a ``seed`` keyword, but the
    # base ``Instrument`` class does not declare it, so cast for the type checker.
    instrument: Instrument = cls(seed=seed)  # type: ignore[call-arg]
    voice = _voice_for_role(role)
    role_notes = [ne for ne in notes if ne.voice == voice]
    if not role_notes:
        return np.zeros(n, dtype=np.float64)
    buffer = np.zeros(n, dtype=np.float64)
    max_start = duration_of_buffer(n, sample_rate)
    for ne in role_notes:
        if ne.start >= max_start:
            continue
        note_event = InstrumentNoteEvent(
            note=int(ne.note),
            start=float(ne.start),
            duration=float(max(ne.duration, 0.05)),
            velocity=float(max(ne.velocity, 0.01)),
        )
        rendered = instrument.render(note_event, sample_rate)
        start_i = int(note_event.start * sample_rate)
        end_i = min(n, start_i + rendered.size)
        if end_i <= start_i:
            continue
        buffer[start_i:end_i] += rendered[: end_i - start_i]
    return buffer


def duration_of_buffer(n: int, sample_rate: int) -> float:
    """Return the duration in seconds represented by ``n`` samples."""
    return float(n) / float(sample_rate)


_AUDIO_MEM_WARN_MB = 500
# Durations above this threshold render the lofi piano path in float32 instead
# of float64 to halve memory usage on long videos (900s can exceed 600 MB in
# float64 across the signal, dynamics and stereo buffers).
_AUDIO_FLOAT32_THRESHOLD_S = 300.0


def _warn_audio_memory(duration: float, sr: int) -> None:
    """Log a warning when the projected audio buffer exceeds a safe threshold.

    Full-length audio is rendered in memory as numpy arrays. For long videos
    (e.g. 900s at 44.1kHz stereo float64), the master bus alone is ~317 MB
    and the full mixer (8 buses + reverb tails) can exceed 1 GB. This helper
    estimates the master-bus footprint and warns early so OOM on
    memory-constrained runners is diagnosed rather than silent.
    """
    n = int(duration * sr)
    # float64 stereo = 16 bytes/sample; float32 = 8 bytes/sample.
    bytes_per_sample = 8 if duration > _AUDIO_FLOAT32_THRESHOLD_S else 16
    master_mb = (n * bytes_per_sample) / (1024 * 1024)
    if master_mb > _AUDIO_MEM_WARN_MB:
        log.warning(
            "Audio buffer for %.0fs video ~%.0f MB (master bus). "
            "Long videos may exceed runner memory; consider --preset live-test.",
            duration,
            master_mb,
        )


def _configure_mixer_from_genre(mixer: Mixer, mix_config: dict, n: int, sr: int) -> None:
    """Apply bus EQ/gain/reverb/sidechain/master settings from the genre preset."""
    bus_configs = mix_config.get("buses", {})
    for bus_name, params in bus_configs.items():
        if bus_name not in MIX_BUS_NAMES:
            continue
        kwargs = {
            k: v
            for k, v in params.items()
            if k in {"gain", "pan", "eq_low", "eq_mid", "eq_high", "reverb_send"}
        }
        mixer.configure_bus(bus_name, **kwargs)

    reverb_cfg = mix_config.get("reverb", {})
    if reverb_cfg:
        mixer.configure_reverb(**reverb_cfg)

    master_cfg = mix_config.get("master", {})
    if "gain" in master_cfg:
        mixer.configure_master(gain=float(master_cfg["gain"]))

    sidechain_cfg = mix_config.get("sidechain")
    if sidechain_cfg:
        target_bus = str(sidechain_cfg.get("target", "bass"))
        duck = SideChainDuck(
            source=np.zeros(n, dtype=np.float64),
            target=np.zeros(n, dtype=np.float64),
            threshold=float(sidechain_cfg.get("threshold", -30.0)),
            ratio=float(sidechain_cfg.get("ratio", 6.0)),
            attack_ms=float(sidechain_cfg.get("attack_ms", 3.0)),
            release_ms=float(sidechain_cfg.get("release_ms", 120.0)),
            sample_rate=sr,
        )
        if target_bus in MIX_BUS_NAMES:
            mixer.configure_bus(target_bus, sidechain=duck)


def _render_instruments(mixer: Mixer, genre_preset, composition: CompositionPlan, seed: int, sr: int, n: int) -> None:
    """Render each non-drum instrument role and add it to the mixer."""
    all_notes = list(composition.notes)
    for role, instrument_name in genre_preset.instruments.items():
        if role == "drums":
            continue
        rendered = _render_instrument_role(role, instrument_name, all_notes, seed, sr, n)
        if np.max(np.abs(rendered)) > 1e-12:
            bus_name = _bus_for_role(role)
            mixer.add_track(f"{role}_{instrument_name}", rendered, bus_name)


def _render_drums(
    mixer: Mixer, genre_preset, composition: CompositionPlan, duration: float, sr: int, n: int
) -> None:
    """Render the drum pattern via DrumSequencer and add it to the mixer."""
    bpm = float(composition.tempo_map[0][1]) if composition.tempo_map else float(np.mean(genre_preset.tempo_range))
    beat_seconds = 60.0 / bpm
    bar_seconds = 4.0 * beat_seconds
    bars = max(1, int(math.ceil(duration / bar_seconds)))
    sequencer = DrumSequencer(genre_preset.drum_pattern, swing=float(genre_preset.swing))
    drums_rendered = sequencer.render(bpm, bars, sr)
    if drums_rendered.size > n:
        drums_rendered = drums_rendered[:n]
    elif drums_rendered.size < n:
        drums_rendered = np.pad(drums_rendered, (0, n - drums_rendered.size))
    if np.max(np.abs(drums_rendered)) > 1e-12:
        mixer.add_track("drums", drums_rendered, "drums")


def _apply_master_processing(
    left: np.ndarray, right: np.ndarray, mix_config: dict, events: list[CreativeEvent], duration: float, sr: int
) -> tuple[np.ndarray, np.ndarray]:
    """Apply event dynamics, Haas decorrelation, saturation, mastering and fade to the stereo bus."""
    from utils.dsp.mastering import HarmonicExciter, MultibandCompressor, StereoWidener, TapeSim

    dynamics = _event_dynamics_envelope(duration, events)
    left = left * dynamics
    right = right * dynamics

    haas_delay = max(1, int(sr * 0.013))
    if haas_delay > 0 and haas_delay < left.size:
        delayed_right = np.zeros_like(right)
        delayed_right[haas_delay:] = right[: -haas_delay]
        right = right * 0.84 + delayed_right * 0.16

    saturation_style = str(mix_config.get("saturation", "soft"))
    drive, ceiling = _SATURATION_PRESETS.get(saturation_style, (1.15, 0.85))
    left = np.tanh(left * drive) * ceiling
    right = np.tanh(right * drive) * ceiling

    # Multiband mastering compressor for tight low end and airy highs.
    mb = MultibandCompressor(crossover_low_hz=180.0, crossover_high_hz=5000.0, sample_rate=sr)
    left = mb.process(left)
    right = mb.process(right)

    # Harmonic exciter for presence and air (applied to each channel).
    exciter = HarmonicExciter(crossover_hz=4000.0, drive=0.5, mix=0.18, sample_rate=sr)
    left = exciter.process(left)
    right = exciter.process(right)

    # Tape saturation for warmth and glue.
    tape = TapeSim(saturation=0.3, hf_loss_hz=14000.0, wow_depth=0.0015, flutter_depth=0.0006, sample_rate=sr)
    left = tape.process(left)
    right = tape.process(right)

    # Stereo widening via mid/side.
    stereo = np.stack([left, right], axis=0)
    stereo = StereoWidener(width=1.25).process(stereo)
    left, right = stereo[0], stereo[1]

    fade = min(left.size // 8, sr * 3)
    ramp = np.linspace(0, 1, fade)
    left[:fade] *= ramp
    left[-fade:] *= ramp[::-1]
    right[:fade] *= ramp
    right[-fade:] *= ramp[::-1]

    left = np.clip(left, -0.99, 0.99)
    right = np.clip(right, -0.99, 0.99)
    return left, right


def _write_stereo_wav(path: Path, left: np.ndarray, right: np.ndarray, sr: int) -> None:
    """Write a 16-bit stereo PCM WAV file."""
    samples = (np.column_stack((left, right)) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sr)
        wav.writeframes(samples.tobytes())


def _synth_audio_universal(
    path: Path,
    duration: float,
    seed: int,
    profile: dict,
    events: list[CreativeEvent] | None,
    composition: CompositionPlan | None,
) -> None:
    """Universal genre-driven audio synthesis via the instrument/mixer engine."""
    genre_name = str(profile.get("genre") or "lofi_ambient")
    genre_preset = get_genre(genre_name)
    music = profile["music"]
    events = events or build_timeline(seed, duration, music)
    composition = composition or build_composition_for_genre(seed, duration, genre_preset)

    sr = SAMPLE_RATE
    _warn_audio_memory(duration, sr)
    n = int(duration * sr)
    mix_config = genre_preset.mix_config

    mixer = Mixer(sample_rate=sr)
    _configure_mixer_from_genre(mixer, mix_config, n, sr)
    _render_instruments(mixer, genre_preset, composition, seed, sr, n)
    _render_drums(mixer, genre_preset, composition, duration, sr, n)

    stereo = mixer.render(sr)
    if stereo.ndim != 2 or stereo.shape[0] != 2:
        stereo = np.stack([stereo.ravel(), stereo.ravel()], axis=0)
    mix_len = stereo.shape[1]
    if mix_len < n:
        stereo = np.pad(stereo, ((0, 0), (0, n - mix_len)))
    elif mix_len > n:
        stereo = stereo[:, :n]

    left, right = _apply_master_processing(stereo[0], stereo[1], mix_config, events, duration, sr)
    _write_stereo_wav(path, left, right, sr)


def _synth_audio(
    path: Path,
    duration: float,
    seed: int,
    profile: dict,
    events: list[CreativeEvent] | None = None,
    composition: CompositionPlan | None = None,
) -> None:
    """Synthesize the Liquid Wire soundtrack.

    Dispatches to the backwards-compatible lo-fi piano path for the
    ``lofi_ambient`` genre (preserving the exact, quality-gate-tuned output)
    and to the universal instrument/mixer engine for every other genre. The
    signature is unchanged so the rest of the pipeline continues to work.
    """
    genre_name = str(profile.get("genre") or "lofi_ambient")
    if genre_name == "lofi_ambient":
        _synth_audio_lofi(path, duration, seed, profile, events, composition)
    else:
        _synth_audio_universal(path, duration, seed, profile, events, composition)


def _run_ffmpeg(frame_dir: Path, audio_path: Path, output: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        str(frame_dir / "frame_%05d.png"),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "48000",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-shortest",
        str(output),
    ]
    # Timeout prevents a stalled ffmpeg from hanging the job until the GHA
    # runner limit kills it. 15 minutes is generous for a 30-180s video at
    # 1080p on a 2-vCPU runner; if ffmpeg hasn't finished by then it's stuck.
    try:
        subprocess.run(cmd, check=True, timeout=900, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        # Fallback: retry with a faster preset and higher CRF to salvage the
        # render rather than failing the entire pipeline.
        log.warning("ffmpeg timed out with preset=medium; retrying with preset=fast")
        fallback_cmd = cmd.copy()
        idx = fallback_cmd.index("medium")
        fallback_cmd[idx] = "fast"
        fallback_cmd[fallback_cmd.index("18")] = "22"
        try:
            subprocess.run(fallback_cmd, check=True, timeout=600, capture_output=True, text=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            raise RuntimeError(f"ffmpeg failed after fallback: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        # Log the ffmpeg stderr for diagnosis, then try a minimal fallback.
        log.error("ffmpeg failed (rc=%d): %s", exc.returncode, (exc.stderr or "")[:500])
        fallback_cmd = [
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", str(frame_dir / "frame_%05d.png"),
            "-i", str(audio_path),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", str(output),
        ]
        try:
            subprocess.run(fallback_cmd, check=True, timeout=600, capture_output=True, text=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc2:
            raise RuntimeError(f"ffmpeg failed: {exc2}") from exc2


def _events_to_dicts(events: list[CreativeEvent]) -> list[dict]:
    return [event.to_dict() for event in events]


def _events_from_dicts(payload: list[dict]) -> list[CreativeEvent]:
    return [CreativeEvent(**item) for item in payload]


def _render_frame_worker(args: tuple) -> str:
    """Top-level (picklable) worker that renders one frame.

    args = (index, frame_count, profile, events_dict, frame_dir, width, height)
    Renders at the supersampled resolution (caller sets WIDTH/HEIGHT globals),
    then downscales to (width, height) with LANCZOS before saving.
    """
    index, frame_count, profile, events_dict, frame_dir, width, height = args
    events = _events_from_dicts(events_dict)
    # The special/mesh draw paths use module-level WIDTH/HEIGHT. In a worker
    # process those globals default to the import-time values, so set them
    # explicitly to the supersampled render size carried in the profile.
    render_w = int(profile.get("_render_w", width))
    render_h = int(profile.get("_render_h", height))
    global WIDTH, HEIGHT
    WIDTH, HEIGHT = render_w, render_h
    out = _draw_frame(index, frame_count, profile, events, Path(frame_dir))
    # Downscale to the nominal output size when supersampling.
    if (render_w, render_h) != (width, height):
        with Image.open(out) as img:
            down = img.convert("RGB").resize((width, height), Image.LANCZOS)
            down.save(out, quality=92)
    return str(out)


def _worker_count() -> int:
    return min(cpu_count() or 1, 8)


def _render_frames_parallel(
    frame_count: int, profile: dict, events: list[CreativeEvent], frame_dir: Path, width: int, height: int
) -> list[str]:
    """Render all frames in parallel using a multiprocessing pool."""
    events_dict = _events_to_dicts(events)
    args = [
        (i, frame_count, profile, events_dict, str(frame_dir), width, height) for i in range(frame_count)
    ]
    workers = _worker_count()
    if workers <= 1 or frame_count <= 1:
        return [_render_frame_worker(arg) for arg in args]
    with Pool(processes=workers) as pool:
        return pool.map(_render_frame_worker, args)


def _metadata(output: Path, thumbnail: Path, duration: float, preset: str, profile: dict) -> dict:
    fallback_titles = {
        "short": "Color Learns to Breathe | Liquid Wire #Shorts",
        "long": "A Shape Dreaming in Color | Original Lo-Fi Piano",
        "live-test": "Liquid Wire Live | Forms in Slow Motion",
    }
    title = fallback_titles[preset]
    description = (
        "A living wireframe drifts through a black void while an original lo-fi piano piece unfolds.\n\n"
        "Every shape, color and note was generated from code for this Liquid Wire session."
    )
    timeline = profile.get("timeline") or [
        event.to_dict() for event in build_timeline(int(profile["seed"]), duration, profile["music"])
    ]
    prompt = (
        "Create YouTube metadata for an original Liquid Wire video. Return JSON with exactly "
        "two string fields: title and description. The visual is one soft, living multicolor "
        f"wireframe object in a pure black void. Object family: {profile['family']}. Format: {preset}. "
        f"Its dramatic arc is: {', '.join(event['kind'] for event in timeline)}. "
        f"The score uses {profile.get('composition', {}).get('mode', 'a modal')} harmony in four sections. "
        "The soundtrack is original procedural lo-fi piano made in Python. Title: evocative, human, "
        "specific, maximum 70 characters; no dates, episode numbers, technical jargon, clickbait or emoji. "
        "For a short, end the title with #Shorts. Description: 2 brief paragraphs, natural English, "
        "mention that visuals and music are original code-generated work, no marketing claims."
    )
    generated = ai_text(
        prompt,
        system=(
            "You are the editorial voice of Liquid Wire, an art and lo-fi music channel. "
            "Write restrained, poetic, clear English. Output valid JSON only."
        ),
        json_mode=True,
        task="liquid_wire_metadata",
    )
    if generated:
        try:
            value = json.loads(generated)
            candidate_title = str(value.get("title", "")).strip()
            candidate_description = str(value.get("description", "")).strip()
            if candidate_title and candidate_description:
                title = candidate_title[:100]
                description = candidate_description[:5000]
        except (json.JSONDecodeError, AttributeError):
            pass
    description = prepend_chapters(description, duration, [CreativeEvent(**item) for item in timeline])
    return {
        "title": title,
        "description": description,
        "hashtags": [
            "#LiquidWire",
            "#GenerativeArt",
            "#AmbientVisuals",
            "#NoStockFootage",
            *(["#Shorts"] if preset == "short" else []),
        ],
        "scene": f"liquid wire {profile['family']} procedural palette",
        "mood": "ambient",
        "kind": preset,
        "lang": "en",
        "category_id": "10",
        "thumbnail": str(thumbnail),
        "duration": duration,
        "seed": profile["seed"],
        "generator_profile": profile,
        "generated_at": datetime.now(UTC).isoformat(),
        "visual_source": "procedural_python",
        "audio_source": "synthetic_python",
        "video_path": str(output),
        "production_slot": os.environ.get("LIQUID_WIRE_SLOT", "").strip() or None,
    }


def generate(duration: float, preset: str, seed: int | None = None) -> Path:
    global WIDTH, HEIGHT
    width, height = _dimensions_for_preset(preset)
    # Supersampling: render at SS_FACTOR x then downscale to the nominal size.
    render_w, render_h = width * SS_FACTOR, height * SS_FACTOR
    WIDTH, HEIGHT = render_w, render_h
    OUTPUT_DIR.mkdir(exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    if FRAME_DIR.exists():
        shutil.rmtree(FRAME_DIR)
    FRAME_DIR.mkdir(parents=True)
    stem = f"liquid_wire_{preset}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    frame_count = max(1, int(duration * FPS))
    profile = _reserve_profile(preset, seed)
    events = build_timeline(int(profile["seed"]), duration, profile["music"])
    genre_name = str(profile.get("genre") or "lofi_ambient")
    if genre_name == "lofi_ambient":
        composition = build_composition(int(profile["seed"]), duration, profile["music"], events)
    else:
        composition = build_composition_for_genre(
            int(profile["seed"]), duration, get_genre(genre_name)
        )
    profile["engine_version"] = "3.0"
    profile["timeline"] = [event.to_dict() for event in events]
    profile["composition"] = composition.to_dict()
    # Carry the supersampled render size in the profile for the worker.
    profile["_render_w"] = render_w
    profile["_render_h"] = render_h
    _render_frames_parallel(frame_count, profile, events, FRAME_DIR, width, height)
    thumb_index = min(frame_count - 1, FPS * 2)
    thumb_frame = FRAME_DIR / f"frame_{thumb_index:05d}.png"
    audio_path = OUTPUT_DIR / f"{stem}.wav"
    output = OUTPUT_DIR / f"{stem}.mp4"
    _synth_audio(audio_path, duration, int(profile["seed"]), profile, events, composition)
    _run_ffmpeg(FRAME_DIR, audio_path, output)
    # The quality gate expects the nominal output dimensions. The minimum
    # score is configurable per slot (Frente E): morning hours require a
    # higher score, late night is more lenient.
    min_score = min_quality_score_for_slot(current_brt_hour())
    quality = assess_video(output, (width, height), events, _recent_quality_fingerprints(), min_score=min_score)
    _record_quality(profile, quality)
    if not quality.passed:
        output.unlink(missing_ok=True)
        audio_path.unlink(missing_ok=True)
        shutil.rmtree(FRAME_DIR, ignore_errors=True)
        raise QualityGateError(
            f"Render rejected with score {quality.score:.4f}: {', '.join(quality.issues) or 'score_below_threshold'}"
        )
    thumbnail = THUMB_DIR / f"{stem}.jpg"
    Image.open(thumb_frame).save(thumbnail, quality=94)
    meta = _metadata(output, thumbnail, duration, preset, profile)
    meta["quality_report"] = quality.to_dict()
    output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    audio_path.unlink(missing_ok=True)
    shutil.rmtree(FRAME_DIR, ignore_errors=True)
    return output


def _record_dead_letter(slot: str, seed: int, error: str, profile: dict) -> None:
    """Record a failed render in the dead-letter queue and send alert."""
    from utils.notifier import send_alert
    path = data_dir() / "dead_letter_queue.json"
    with state_lock(path):
        try:
            queue = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except (OSError, json.JSONDecodeError):
            queue = []
        queue.append({
            "slot": slot,
            "seed": seed,
            "error": error,
            "family": profile.get("family", ""),
            "genre": profile.get("genre", ""),
            "timestamp": datetime.now(UTC).isoformat(),
        })
        # Keep last 100 entries
        queue = queue[-100:]
        path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    send_alert(
        f"Liquid Wire dead-letter: slot={slot} seed={seed} error={error}",
        level="error",
    )


def _slot_seed() -> int:
    """Derive a deterministic seed for the current production slot.

    Uses the ``LIQUID_WIRE_SLOT`` env var when set (so a scheduled slot always
    gets the same duration within that slot), otherwise hashes the current
    UTC date + hour so the duration is stable for the hour but varies across
    hours.
    """
    slot = os.environ.get("LIQUID_WIRE_SLOT", "").strip()
    if slot:
        return int(hashlib.sha256(f"slot:{slot}".encode()).hexdigest(), 16) % (2**32)
    now = datetime.now(UTC)
    key = now.strftime("%Y-%m-%d %H")
    return int(hashlib.sha256(f"hour:{key}".encode()).hexdigest(), 16) % (2**32)


def _short_duration_for_slot() -> float:
    """Pick a deterministic short duration in [27, 60]s for the current slot."""
    import random as _random

    rng = _random.Random(_slot_seed())
    return float(rng.uniform(27.0, 60.0))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Liquid Wire procedural videos")
    parser.add_argument("--preset", choices=["short", "long", "live-test"], default="short")
    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--attempts", type=int, default=5, help="Maximum quality-gated render attempts")
    args = parser.parse_args()
    # Shorts now vary in duration between 27-60s, deterministic per slot so a
    # given scheduled slot always produces the same duration.
    if args.duration is not None:
        duration = args.duration
    elif args.preset == "short":
        duration = _short_duration_for_slot()
    else:
        duration = {"long": 180.0, "live-test": 120.0}[args.preset]
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    output: Path | None = None
    slot = os.environ.get("LIQUID_WIRE_SLOT", "").strip() or "adhoc"
    # Deterministic seed per scheduled slot: a retry/recovery run for the same
    # slot reproduces the same video instead of burning a new random seed.
    # Manual runs (no LIQUID_WIRE_SLOT) or --seed overrides stay explicit.
    effective_seed = args.seed if args.seed is not None else _slot_seed()
    last_profile: dict = {}
    last_error = ""
    for attempt in range(1, args.attempts + 1):
        if args.seed is not None or attempt == 1:
            attempt_seed = effective_seed
        else:
            # Deterministically vary seed on retries so subsequent attempts generate distinct variations
            seed_entropy = int(hashlib.sha256(f"attempt:{attempt}:{slot}".encode()).hexdigest(), 16)
            attempt_seed = (effective_seed + attempt * 10007 + seed_entropy) % (2**32)
        try:
            output = generate(duration=duration, preset=args.preset, seed=attempt_seed)
            break
        except QualityGateError as exc:
            print(f"Quality attempt {attempt}/{args.attempts} failed: {exc}")
            last_error = str(exc)
            try:
                history = _load_history()
                if history:
                    last = history[-1]
                    last_profile = {
                        "family": last.get("family", ""),
                        "genre": _pick_genre_for_seed(attempt_seed),
                    }
            except Exception:
                pass
            if args.seed is not None or attempt == args.attempts:
                _record_dead_letter(slot, attempt_seed, last_error, last_profile)
                raise
    if output is None:  # pragma: no cover - defensive invariant
        raise RuntimeError("No render was produced.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
