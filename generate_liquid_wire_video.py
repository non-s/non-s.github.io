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
import math
import secrets
import shutil
import subprocess
import wave
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from utils.ai_helper import ai_text
from utils.liquid_wire_quality import QualityGateError, assess_video
from utils.liquid_wire_timeline import CreativeEvent, build_timeline, event_envelope, visual_state
from utils.paths import data_dir
from utils.state_lock import state_lock

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
)

GENERATOR_HISTORY_LIMIT = 5000


def _dimensions_for_preset(preset: str) -> tuple[int, int]:
    return (720, 1280) if preset == "short" else (1280, 720)


def _history_file() -> Path:
    return data_dir() / "generator_history.json"

def _profile(seed: int, preset: str) -> dict:
    rng = np.random.default_rng(seed)
    family = str(rng.choice(OBJECT_FAMILIES))
    return {
        "family": family,
        "seed": seed,
        "preset": preset,
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
                if requested_seed is not None:
                    raise ValueError(f"Seed already used: {requested_seed}")
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


def _draw_frame(
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


def _synth_audio(
    path: Path, duration: float, seed: int, profile: dict, events: list[CreativeEvent] | None = None
) -> None:
    rng = np.random.default_rng(seed)
    count = int(duration * SAMPLE_RATE)
    t = np.linspace(0, duration, count, endpoint=False)
    signal = np.zeros(count, dtype=np.float64)

    # Seeded neo-soul progressions keep every piece original while preserving
    # the warm, suspended harmony associated with instrumental lo-fi.
    music = profile["music"]
    roots = np.array([48, 43, 45, 41, 50, 46, 43, 48], dtype=int) + int(music["key_shift"])
    roots = np.roll(roots, int(rng.integers(0, len(roots))))
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
    events = events or build_timeline(seed, duration, music)
    dynamics = np.ones(count, dtype=np.float64)
    for event in events:
        gesture_at = event.start + event.duration * 0.5
        root = int(roots[int(gesture_at // chord_seconds) % len(roots)])
        if event.kind != "stillness":
            add_piano(root + 24 + event.pitch_offset, gesture_at, beat_seconds * 1.8, 0.035 * event.intensity)
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
    subprocess.run(cmd, check=True)


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
    }


def generate(duration: float, preset: str, seed: int | None = None) -> Path:
    global WIDTH, HEIGHT
    WIDTH, HEIGHT = _dimensions_for_preset(preset)
    OUTPUT_DIR.mkdir(exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    if FRAME_DIR.exists():
        shutil.rmtree(FRAME_DIR)
    FRAME_DIR.mkdir(parents=True)
    stem = f"liquid_wire_{preset}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    frame_count = max(1, int(duration * FPS))
    profile = _reserve_profile(preset, seed)
    events = build_timeline(int(profile["seed"]), duration, profile["music"])
    profile["engine_version"] = "2.0"
    profile["timeline"] = [event.to_dict() for event in events]
    thumb_frame = None
    for i in range(frame_count):
        frame = _draw_frame(i, frame_count, profile, events, FRAME_DIR)
        if i == min(frame_count - 1, FPS * 2):
            thumb_frame = frame
    audio_path = OUTPUT_DIR / f"{stem}.wav"
    output = OUTPUT_DIR / f"{stem}.mp4"
    _synth_audio(audio_path, duration, int(profile["seed"]), profile, events)
    _run_ffmpeg(FRAME_DIR, audio_path, output)
    quality = assess_video(output, (WIDTH, HEIGHT), events)
    if not quality.passed:
        output.unlink(missing_ok=True)
        audio_path.unlink(missing_ok=True)
        shutil.rmtree(FRAME_DIR, ignore_errors=True)
        raise QualityGateError(
            f"Render rejected with score {quality.score:.4f}: {', '.join(quality.issues) or 'score_below_threshold'}"
        )
    thumbnail = THUMB_DIR / f"{stem}.jpg"
    Image.open(thumb_frame or FRAME_DIR / "frame_00000.png").save(thumbnail, quality=94)
    meta = _metadata(output, thumbnail, duration, preset, profile)
    meta["quality_report"] = quality.to_dict()
    output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    audio_path.unlink(missing_ok=True)
    shutil.rmtree(FRAME_DIR, ignore_errors=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Liquid Wire procedural videos")
    parser.add_argument("--preset", choices=["short", "long", "live-test"], default="short")
    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--attempts", type=int, default=3, help="Maximum quality-gated render attempts")
    args = parser.parse_args()
    default_durations = {"short": 35.0, "long": 180.0, "live-test": 120.0}
    duration = args.duration if args.duration is not None else default_durations[args.preset]
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    output: Path | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            output = generate(duration=duration, preset=args.preset, seed=args.seed)
            break
        except QualityGateError as exc:
            print(f"Quality attempt {attempt}/{args.attempts} failed: {exc}")
            if args.seed is not None or attempt == args.attempts:
                raise
    if output is None:  # pragma: no cover - defensive invariant
        raise RuntimeError("No render was produced.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
