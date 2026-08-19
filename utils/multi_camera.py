"""Multi-camera shot planning with transitions.

Instead of a single continuous orbit, the video alternates between different
camera angles/shots with transitions (cut, fade, whip). Shots change every 3-8
seconds and creative events (bloom, rupture, stillness) trigger camera changes
with appropriate transition styles.

Pure-numpy, no external deps. Integrates with utils.liquid_wire_timeline for
event-driven camera decisions and utils.camera for view/projection matrices.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from utils.liquid_wire_timeline import CreativeEvent

# Transition styles supported by CameraShot.transition_in / transition_out.
TRANSITION_KINDS = ("cut", "fade", "whip")

# Default world origin (the scene is centered here).
_ORIGIN = [0.0, 0.0, 0.0]


@dataclass
class CameraShot:
    """A single camera shot with a fixed eye/target/fov and transition styles.

    Attributes:
        name: Human-readable identifier (e.g. "orbital_close_0").
        start: Start time in seconds within the video timeline.
        duration: Length of the shot in seconds.
        eye: Camera position [x, y, z] at shot start (world space).
        target: Look-at target [x, y, z] at shot start.
        fov: Horizontal field of view in degrees.
        transition_in: How this shot begins ("cut"|"fade"|"whip").
        transition_out: How this shot ends ("cut"|"fade"|"whip").

    The eye/target may drift slightly during the shot (slow orbital motion)
    so the shot feels alive rather than frozen. camera_state_at interpolates
    the actual eye/target/fov for a given time t within the shot.
    """

    name: str
    start: float
    duration: float
    eye: list[float]
    target: list[float]
    fov: float
    transition_in: str = "cut"
    transition_out: str = "cut"

    def end(self) -> float:
        return self.start + self.duration

    def contains(self, t: float) -> bool:
        return self.start <= t < self.end()

    def phase(self, t: float) -> float:
        """Normalized local time [0,1] within the shot at time t."""
        if self.duration <= 1e-9:
            return 0.0
        return float(np.clip((t - self.start) / self.duration, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

PRESET_SHOTS: dict[str, dict] = {
    "orbital_close": {
        "eye": [3.2, 2.0, 3.2],
        "target": [0.0, 0.0, 0.0],
        "fov": 38.0,
        "orbit": 1.0,
        "orbit_radius": 4.4,
    },
    "orbital_wide": {
        "eye": [7.5, 4.5, 7.5],
        "target": [0.0, 0.0, 0.0],
        "fov": 60.0,
        "orbit": 1.0,
        "orbit_radius": 10.6,
    },
    "top_down": {
        "eye": [0.0, 9.5, 0.001],
        "target": [0.0, 0.0, 0.0],
        "fov": 50.0,
        "orbit": 0.0,
        "orbit_radius": 9.5,
    },
    "side_view": {
        "eye": [9.0, 1.6, 0.4],
        "target": [0.0, 0.4, 0.0],
        "fov": 42.0,
        "orbit": 0.5,
        "orbit_radius": 9.0,
    },
    "low_angle": {
        "eye": [4.5, -2.2, 4.5],
        "target": [0.0, 1.8, 0.0],
        "fov": 34.0,
        "orbit": 1.0,
        "orbit_radius": 6.4,
    },
    "dramatic_zoom": {
        "eye": [2.0, 1.2, 2.0],
        "target": [0.0, 0.0, 0.0],
        "fov": 24.0,
        "orbit": 0.25,
        "orbit_radius": 2.83,
    },
}

# Ordered list of preset names used to cycle through angles.
_PRESET_ORDER = [
    "orbital_wide",
    "orbital_close",
    "side_view",
    "low_angle",
    "top_down",
    "dramatic_zoom",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _preset_eye(name: str, angle: float) -> list[float]:
    """Return an eye position for a preset at a given orbit angle (radians).).

    If the preset has orbit enabled, the eye is rotated around the Y axis by
    `angle` at the preset's radius, preserving its height. Non-orbiting presets
    return a slightly jittered base eye.
    """
    p = PRESET_SHOTS[name]
    base = np.asarray(p["eye"], dtype=np.float64)
    if p.get("orbit", 0.0) > 0.0:
        r = float(np.sqrt(base[0] ** 2 + base[2] ** 2)) or p.get("orbit_radius", 8.0)
        h = float(base[1])
        return [float(r * np.cos(angle)), h, float(r * np.sin(angle))]
    return [float(base[0]), float(base[1]), float(base[2])]


def _transition_for_event(kind: str) -> tuple[str, str]:
    """Return (transition_in, transition_out) appropriate for an event kind."""
    if kind in ("bloom", "rupture"):
        return ("whip", "cut")
    if kind == "stillness":
        return ("fade", "fade")
    return ("cut", "cut")


def _shot_at(shots: list[CameraShot], t: float) -> CameraShot | None:
    for s in shots:
        if s.contains(t):
            return s
    if shots:
        if t < shots[0].start:
            return shots[0]
        return shots[-1]
    return None


def _index_at(shots: list[CameraShot], t: float) -> int:
    for i, s in enumerate(shots):
        if s.contains(t):
            return i
    if t < shots[0].start:
        return 0
    return len(shots) - 1


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def plan_camera_shots(
    duration: float,
    events: list[CreativeEvent],
    ai_plan: dict | None = None,
) -> list[CameraShot]:
    """Plan a list of CameraShot covering `duration` seconds.

    Strategy:
      1. If ai_plan contains "camera_suggestions", use them directly (validated).
      2. Otherwise, generate 4-8 shots. Shots last 3-8s and cycle through the
         preset angles. Creative events override the upcoming shot's preset
         and transition style:
            - bloom / rupture -> "whip" transition_in
            - stillness       -> "fade" transitions + longer shot
      3. Shots are snapped so an event boundary aligns with a shot boundary
         when possible (the event triggers the camera change).

    Returns a non-empty list of shots covering [0, duration].
    """
    if duration <= 0.0:
        return []

    # --- 1. AI-suggested camera plan --------------------------------------
    suggestions = None
    if ai_plan and isinstance(ai_plan, dict):
        sug = ai_plan.get("camera_suggestions")
        if isinstance(sug, list) and sug:
            suggestions = sug

    if suggestions:
        shots = _shots_from_suggestions(suggestions, duration)
        if shots:
            return _finalize(shots, duration)

    # --- 2. Procedural plan ----------------------------------------------
    rng = np.random.default_rng(int(duration * 1000) ^ 0x43414D)

    # Sort events by start time for boundary alignment.
    sorted_events = sorted(events, key=lambda e: e.start)

    # Decide shot boundaries. Start with evenly spaced boundaries then snap
    # them to nearby creative events so a camera change coincides with the
    # event. Keep shots within [3, 8] seconds.
    target_count = int(np.clip(round(duration / 5.5), 4, 8))
    raw_bounds = list(np.linspace(0.0, duration, target_count + 1))
    bounds: list[float] = [raw_bounds[0]]
    for b in raw_bounds[1:-1]:
        # Snap to nearest event start within +/- 1.2s.
        snapped = b
        best_d = 1.2
        for ev in sorted_events:
            d = abs(ev.start - b)
            if d < best_d:
                best_d = d
                snapped = ev.start
        # Enforce min spacing from previous bound.
        if snapped - bounds[-1] < 3.0:
            snapped = bounds[-1] + 3.0
        bounds.append(min(snapped, duration - 3.0))
    bounds.append(duration)
    # Final spacing sanity pass: enforce [3, 8].
    bounds = _enforce_spacing(bounds, 3.0, 8.0, duration)

    cam_shots: list[CameraShot] = []
    angle_offset = float(rng.uniform(0.0, 2.0 * np.pi))
    prev_preset = ""
    for i in range(len(bounds) - 1):
        start = float(bounds[i])
        end = float(bounds[i + 1])
        shot_dur = max(3.0, end - start)

        # Choose preset, avoiding immediate repeat.
        preset = _PRESET_ORDER[i % len(_PRESET_ORDER)]
        if preset == prev_preset:
            preset = _PRESET_ORDER[(i + 1) % len(_PRESET_ORDER)]
        prev_preset = preset

        # Find the dominant event within this shot's window to influence
        # transitions and possibly the preset.
        dom_kind = ""
        dom_energy = 0.0
        for ev in sorted_events:
            ev_end = ev.start + ev.duration
            if ev_end < start or ev.start > end:
                continue
            overlap = min(ev_end, end) - max(ev.start, start)
            if overlap <= 0.0:
                continue
            energy = overlap * ev.intensity
            if energy > dom_energy:
                dom_energy = energy
                dom_kind = ev.kind

        t_in, t_out = _transition_for_event(dom_kind)

        # Stillness -> prefer top_down or side_view for a calm, stable frame.
        if dom_kind == "stillness" and preset in ("orbital_close", "low_angle"):
            preset = "top_down" if preset != "top_down" else "side_view"

        # bloom / rupture -> prefer dramatic zoom or low angle for impact.
        if dom_kind in ("bloom", "rupture") and preset == "orbital_wide":
            preset = "dramatic_zoom"

        # Longer shots for stillness, shorter for bloom/rupture.
        if dom_kind == "stillness":
            shot_dur = min(8.0, shot_dur * 1.25)
        elif dom_kind in ("bloom", "rupture"):
            shot_dur = max(3.0, shot_dur * 0.7)

        # Orbit angle drifts between shots so the same preset doesn't repeat
        # the exact same framing.
        orbit_angle = angle_offset + i * (2.0 * np.pi / len(_PRESET_ORDER)) * 0.37
        eye = _preset_eye(preset, orbit_angle)
        p = PRESET_SHOTS[preset]
        target = list(p["target"])
        fov = float(p["fov"])

        cam_shots.append(
            CameraShot(
                name=f"{preset}_{i}",
                start=start,
                duration=shot_dur,
                eye=eye,
                target=target,
                fov=fov,
                transition_in=t_in,
                transition_out=t_out,
            )
        )

    return _finalize(cam_shots, duration)


def _shots_from_suggestions(suggestions: list, duration: float) -> list[CameraShot]:
    """Build shots from an AI-provided camera_suggestions list.

    Each suggestion may contain: start_fraction, duration_fraction, preset,
    eye, target, fov, transition_in, transition_out. Missing fields are filled
    from the named preset (if any) or sane defaults.
    """
    shots: list[CameraShot] = []
    for i, sug in enumerate(suggestions):
        if not isinstance(sug, dict):
            continue
        try:
            start = float(sug.get("start_fraction", i * 0.15)) * duration
            shot_dur = float(sug.get("duration_fraction", 0.12)) * duration
        except (TypeError, ValueError):
            continue
        if shot_dur <= 0.5:
            shot_dur = 5.0
        start = max(0.0, min(start, duration - 1.0))

        preset = str(sug.get("preset", ""))
        p = PRESET_SHOTS.get(preset, PRESET_SHOTS["orbital_wide"])

        eye = sug.get("eye")
        if not isinstance(eye, list) or len(eye) != 3:
            eye = list(p["eye"])
        eye = [float(v) for v in eye]

        target = sug.get("target")
        if not isinstance(target, list) or len(target) != 3:
            target = list(p["target"])
        target = [float(v) for v in target]

        fov = float(sug.get("fov", p["fov"]))
        t_in = str(sug.get("transition_in", "cut"))
        t_out = str(sug.get("transition_out", "cut"))
        if t_in not in TRANSITION_KINDS:
            t_in = "cut"
        if t_out not in TRANSITION_KINDS:
            t_out = "cut"

        shots.append(
            CameraShot(
                name=f"{preset or 'shot'}_{i}",
                start=start,
                duration=shot_dur,
                eye=eye,
                target=target,
                fov=fov,
                transition_in=t_in,
                transition_out=t_out,
            )
        )
    if not shots:
        return []
    shots.sort(key=lambda s: s.start)
    # Patch gaps and overlaps so the timeline is contiguous.
    for i in range(len(shots) - 1):
        end_i = shots[i].start + shots[i].duration
        if end_i < shots[i + 1].start:
            shots[i].duration = shots[i + 1].start - shots[i].start
        elif end_i > shots[i + 1].start:
            shots[i + 1].start = end_i
    return shots


def _enforce_spacing(
    bounds: list[float], lo: float, hi: float, duration: float
) -> list[float]:
    """Adjust boundary list so each segment is within [lo, hi] seconds."""
    if len(bounds) < 2:
        return bounds
    out = [float(bounds[0])]
    for b in bounds[1:]:
        b = float(b)
        if b - out[-1] < lo:
            b = out[-1] + lo
        elif b - out[-1] > hi:
            b = out[-1] + hi
        out.append(b)
    # Clamp to duration and re-fix the last segment.
    out[-1] = duration
    if out[-1] - out[-2] < lo and len(out) >= 2:
        out[-2] = out[-1] - lo
    return out


def _finalize(shots: list[CameraShot], duration: float) -> list[CameraShot]:
    """Ensure shots cover [0, duration] contiguously with no gaps/overlaps."""
    if not shots:
        return shots
    shots.sort(key=lambda s: s.start)
    # First shot starts at 0.
    shots[0].start = 0.0
    # Make contiguous.
    for i in range(len(shots) - 1):
        end_i = shots[i].start + shots[i].duration
        if end_i < shots[i + 1].start:
            shots[i].duration = shots[i + 1].start - shots[i].start
        elif end_i > shots[i + 1].start:
            shots[i + 1].start = end_i
    # Last shot ends at duration.
    last_end = shots[-1].start + shots[-1].duration
    if last_end < duration:
        shots[-1].duration = duration - shots[-1].start
    elif last_end > duration:
        shots[-1].duration = max(1.0, duration - shots[-1].start)
    return shots


# ---------------------------------------------------------------------------
# State evaluation
# ---------------------------------------------------------------------------

def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_vec(a: list[float], b: list[float], t: float) -> list[float]:
    return [float(_lerp(a[i], b[i], t)) for i in range(3)]


def _fade_blend(
    prev: CameraShot,
    cur: CameraShot,
    t: float,
    fade_len: float,
) -> tuple[list[float], list[float], float]:
    """Smoothly fade eye/target/fov between prev and cur over fade_len seconds
    measured from cur.start.
    """
    if fade_len <= 1e-6:
        return _eval_shot(cur, t)
    u = float(np.clip((t - cur.start) / fade_len, 0.0, 1.0))
    # Ease (smoothstep) so the fade is not linear.
    u = u * u * (3.0 - 2.0 * u)
    pe, pt, pf = _eval_shot(prev, t)
    ce, ct, cf = _eval_shot(cur, t)
    return (
        _lerp_vec(pe, ce, u),
        _lerp_vec(pt, ct, u),
        float(_lerp(pf, cf, u)),
    )


def _whip_shake(
    eye: list[float],
    target: list[float],
    fov: float,
    t: float,
    cur: CameraShot,
    shake_len: float,
) -> tuple[list[float], list[float], float]:
    """Apply a brief directional shake at the start of a whip-pan transition."""
    if shake_len <= 1e-6:
        return eye, target, fov
    u = float(np.clip((t - cur.start) / shake_len, 0.0, 1.0))
    # Decaying impulse: strong at u=0, gone by u=1.
    amp = (1.0 - u) * (1.0 - u) * 0.9
    rng = np.random.default_rng(int(cur.start * 1000) & 0xFFFFFFFF)
    # Tangent direction of the orbit at cur.start for a believable whip.
    dx = float(rng.uniform(-1.0, 1.0)) * amp
    dy = float(rng.uniform(-0.4, 0.4)) * amp
    dz = float(rng.uniform(-1.0, 1.0)) * amp
    eye = [eye[i] + [dx, dy, dz][i] for i in range(3)]
    # FOV briefly widens then snaps back.
    fov = float(fov + 6.0 * amp)
    return eye, target, fov


def _eval_shot(shot: CameraShot, t: float) -> tuple[list[float], list[float], float]:
    """Evaluate eye/target/fov at time t for a single shot, including the
    shot's internal slow drift (orbit / dolly) so the frame is never frozen.
    """
    p = shot.phase(t)
    preset = _preset_name_from_shot(shot)
    pdef = PRESET_SHOTS.get(preset, {})
    orbit = float(pdef.get("orbit", 0.0))
    base_eye = np.asarray(shot.eye, dtype=np.float64)
    base_target = np.asarray(shot.target, dtype=np.float64)

    if orbit > 0.0:
        # Slow continuous orbit within the shot: rotate up to ~60deg.
        r = float(np.sqrt(base_eye[0] ** 2 + base_eye[2] ** 2)) or float(
            pdef.get("orbit_radius", 8.0)
        )
        h = float(base_eye[1])
        start_angle = float(np.arctan2(base_eye[2], base_eye[0]))
        sweep = orbit * np.radians(60.0) * p
        angle = start_angle + sweep
        eye = [float(r * np.cos(angle)), h, float(r * np.sin(angle))]
    else:
        # Subtle dolly-in for non-orbit presets (e.g. top_down, dramatic_zoom).
        dolly = 0.03 * p
        direction = base_eye - base_target
        norm = float(np.linalg.norm(direction)) or 1.0
        eye = (base_eye - direction / norm * dolly).tolist()

    # Target stays essentially fixed; tiny bob for organic feel.
    target = base_target + np.array(
        [0.0, 0.02 * np.sin(2.0 * np.pi * p), 0.0], dtype=np.float64
    )

    fov = float(shot.fov)
    # dramatic_zoom slowly pushes FOV tighter.
    if preset == "dramatic_zoom":
        fov = float(shot.fov - 4.0 * p)

    return [float(eye[0]), float(eye[1]), float(eye[2])], target.tolist(), fov


def _preset_name_from_shot(shot: CameraShot) -> str:
    """Recover the preset name from a shot name like "orbital_close_3"."""
    name = shot.name or ""
    for key in PRESET_SHOTS:
        if name.startswith(key):
            return key
    return ""


def camera_state_at(
    t: float, shots: list[CameraShot]
) -> tuple[list[float], list[float], float]:
    """Return (eye, target, fov) for time t given a shot list.

    - Within a shot: evaluate that shot (with internal drift).
    - On a "cut" boundary: switch instantly.
    - On a "fade" boundary: interpolate smoothly between prev and cur over a
      short fade window (default 0.6s).
    - On a "whip" boundary: cut instantly then apply a brief decaying shake.
    """
    if not shots:
        return [0.0, 0.0, 8.0], [0.0, 0.0, 0.0], 60.0

    shots = sorted(shots, key=lambda s: s.start)
    idx = _index_at(shots, t)
    cur = shots[idx]

    # Before the first shot starts: hold the first shot's initial state.
    if t < cur.start:
        return _eval_shot(cur, cur.start)

    # Determine if we are inside a transition window at cur.start.
    trans_in = cur.transition_in
    fade_len = 0.6
    whip_len = 0.35

    if t < cur.start + max(fade_len, whip_len) and idx > 0 and trans_in != "cut":
        prev = shots[idx - 1]
        if trans_in == "fade" and t < cur.start + fade_len:
            return _fade_blend(prev, cur, t, fade_len)
        if trans_in == "whip" and t < cur.start + whip_len:
            eye, target, fov = _eval_shot(cur, t)
            return _whip_shake(eye, target, fov, t, cur, whip_len)

    # Also handle fade-out at the end of a shot into the next shot's fade-in
    # (only when both shots agree on fade).
    if idx + 1 < len(shots):
        nxt = shots[idx + 1]
        end = cur.end()
        out_fade = 0.4
        if (
            cur.transition_out == "fade"
            and nxt.transition_in == "fade"
            and end - out_fade <= t < end
        ):
            u = float(np.clip((t - (end - out_fade)) / out_fade, 0.0, 1.0))
            u = u * u * (3.0 - 2.0 * u)
            ce, ct, cf = _eval_shot(cur, t)
            ne, nt, nf = _eval_shot(nxt, nxt.start)
            return (
                _lerp_vec(ce, ne, u),
                _lerp_vec(ct, nt, u),
                float(_lerp(cf, nf, u)),
            )

    return _eval_shot(cur, t)
