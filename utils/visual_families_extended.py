"""Extended parametric visual families for the Liquid Wire engine.

Each family is a pure function ``family_name(theta, phi, t, profile, events)``
that returns ``(x, y, z)`` numpy arrays of world-space coordinates over a
parametric grid. The grid is produced by the caller via ``np.meshgrid`` so the
shapes of ``theta`` and ``phi`` are preserved. Creative events are injected
through :func:`utils.liquid_wire_timeline.visual_state` and generator
parameters are read from ``profile`` (palette, melt_rate, breath_rate, ...).
"""

from __future__ import annotations

import numpy as np

from utils.liquid_wire_timeline import visual_state


def _event_modulation(
    theta: np.ndarray,
    phi: np.ndarray,
    t: float,
    profile: dict,
    events: list,
) -> tuple[dict, np.ndarray]:
    """Shared event/parameter-driven radial displacement for all families."""
    state = visual_state(t, events)
    phase = float(profile.get("phase", 0.0))
    breath_rate = float(profile.get("breath_rate", 0.6))
    melt_rate = float(profile.get("melt_rate", 0.4))
    breath = 0.12 * np.sin(breath_rate * t + phase)
    melt = 0.10 * np.sin(4.0 * theta + 2.0 * phi + t * melt_rate)
    bloom = state["bloom"] * 0.22 * np.sin(3.0 * phi)
    compression = -state["compression"] * 0.18 * np.cos(2.0 * theta)
    rupture = state["rupture"] * 0.20 * np.sign(np.sin(5.0 * theta + phase))
    tide = state["tide"] * 0.16 * np.sin(phi * 2.0 + theta + t * 0.35)
    stillness = max(0.25, 1.0 - state["stillness"] * 0.72)
    radial = 1.0 + stillness * (breath + melt) + bloom + compression + rupture + tide
    return state, radial.astype(np.float64)


def _palette_phase(profile: dict, t: float) -> float:
    palette = profile.get("palette", {}) if isinstance(profile, dict) else {}
    return (
        float(palette.get("base_hue", 0.0)) * 2.0 * np.pi
        + float(palette.get("hue_speed", 0.0)) * t
    )


def mobius(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Mobius strip: single-sided band with a half-twist over [0, 4*pi]."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    twist = float(profile.get("twist", 0.5)) * 0.25 * np.sin(t * 0.4)
    w = np.clip(phi, -1.0, 1.0) * 0.5
    half = theta * 0.5 + twist
    r = 1.0 + w * np.cos(half)
    x = r * np.cos(theta) * radial
    y = r * np.sin(theta) * radial
    z = w * np.sin(half) * radial + 0.05 * state["bloom"] * np.sin(3.0 * theta)
    return x, y, z


def klein_bottle(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Klein bottle (figure-8 immersion): non-orientable closed surface."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    R = 1.0
    r = 0.5 + 0.05 * np.sin(t * 0.6)
    u = theta + 0.15 * state["tide"] * np.sin(phi * 2.0)
    v = phi + 0.10 * state["bloom"] * np.sin(theta * 3.0)
    base = R + r * (np.cos(u * 0.5) * np.sin(v) - np.sin(u * 0.5) * np.sin(2.0 * v))
    x = base * np.cos(u) * radial
    y = base * np.sin(u) * radial
    z = (r * np.sin(u * 0.5) * np.sin(v) + r * np.cos(u * 0.5) * np.sin(2.0 * v)) * radial
    return x, y, z


def julia_set(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Julia set 3D: map (theta, phi) to the complex plane and iterate z = z^2 + c."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    seed = int(profile.get("seed", 0))
    rng = np.random.default_rng(seed)
    cx = 0.7885 * np.cos(t * 0.2 + rng.uniform(0.0, 0.5))
    cy = 0.7885 * np.sin(t * 0.2 + rng.uniform(0.0, 0.5))
    zx = 1.6 * (theta / (2.0 * np.pi) - 0.5)
    zy = 1.6 * (phi / np.pi - 0.5)
    iters = np.zeros_like(zx, dtype=np.float64)
    for _ in range(24):
        inside = zx * zx + zy * zy < 4.0
        nx = zx * zx - zy * zy + cx
        ny = 2.0 * zx * zy + cy
        zx = np.where(inside, nx, zx)
        zy = np.where(inside, ny, zy)
        iters = np.where(inside, iters + 1.0, iters)
    depth = iters / 24.0
    r = (0.6 + 0.8 * depth) * radial
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.sin(phi) * np.sin(theta)
    z = r * np.cos(phi) + 0.10 * state["rupture"] * (depth - 0.5)
    return x, y, z


def sierpinski(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Sierpinski tetrahedron via iterative barycentric contraction."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    verts = np.array(
        [
            [1.0, 1.0, 1.0],
            [-1.0, -1.0, 1.0],
            [-1.0, 1.0, -1.0],
            [1.0, -1.0, -1.0],
        ],
        dtype=np.float64,
    )
    px = np.tan(theta) * np.cos(phi)
    py = np.tan(theta) * np.sin(phi)
    pz = np.cos(phi)
    pts = np.stack([px, py, pz], axis=-1)
    depth = int(profile.get("growth_iterations", 5))
    for _ in range(depth):
        diffs = pts[..., None, :] - verts[None, None, :, :]
        dist = np.sum(diffs * diffs, axis=-1)
        nearest = np.argmin(dist, axis=-1)
        verts_t = verts[nearest]
        pts = 0.5 * (pts + verts_t)
    scale = (0.55 + 0.20 * np.sin(t * 0.5)) * radial
    x = pts[..., 0] * scale
    y = pts[..., 1] * scale
    z = pts[..., 2] * scale + 0.08 * state["bloom"] * np.sin(4.0 * theta)
    return x, y, z


def voronoi_sphere(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Sphere tessellated into Voronoi cells; cell distance modulates the radius."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    seed = int(profile.get("seed", 0))
    n_seeds = 12
    rng = np.random.default_rng(seed ^ 0x564F52)
    sx = rng.standard_normal(n_seeds)
    sy = rng.standard_normal(n_seeds)
    sz = rng.standard_normal(n_seeds)
    norm = np.sqrt(sx * sx + sy * sy + sz * sz) + 1e-9
    sx, sy, sz = sx / norm, sy / norm, sz / norm
    spin = t * 0.15
    cs, sn = np.cos(spin), np.sin(spin)
    sxr = sx * cs - sy * sn
    syr = sx * sn + sy * cs
    px = np.sin(phi) * np.cos(theta)
    py = np.sin(phi) * np.sin(theta)
    pz = np.cos(phi)
    d2 = (
        (px[..., None] - sxr) ** 2
        + (py[..., None] - syr) ** 2
        + (pz[..., None] - sz) ** 2
    )
    nearest = np.min(d2, axis=-1)
    second = np.partition(d2, 1, axis=-1)[..., 1]
    edge = np.clip(1.0 - (second - nearest) * 6.0, 0.0, 1.0)
    r = (0.9 + 0.30 * edge + 0.10 * np.sin(nearest * 30.0 + t)) * radial
    x = r * px
    y = r * py
    z = r * pz + 0.06 * state["compression"] * edge
    return x, y, z


def lissajous_3d(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """3D Lissajous curve swept into a tube surface."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    a, b, c = 3.0, 2.0, 5.0
    delta = float(profile.get("phase", 0.0))
    s = theta / (2.0 * np.pi)
    cx = np.sin(a * s * 2.0 * np.pi + delta + t * 0.5)
    cy = np.sin(b * s * 2.0 * np.pi + t * 0.3)
    cz = np.sin(c * s * 2.0 * np.pi + t * 0.7)
    tube = 0.18 + 0.06 * state["bloom"]
    bx = np.cos(phi) * tube
    by = np.sin(phi) * tube
    x = (cx + bx * np.cos(theta * 3.0)) * radial
    y = (cy + by) * radial
    z = (cz + bx * np.sin(theta * 3.0)) * radial
    return x, y, z


def harmonograph(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Harmonograph: four damped pendulums summed into a 3D trail."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    s = theta / (2.0 * np.pi)
    decay = np.exp(-0.15 * s)
    f1, f2, f3, f4 = 3.0, 2.0, 5.0, 4.0
    ph = float(profile.get("phase", 0.0))
    hx = (np.sin(f1 * s * 2.0 * np.pi + ph + t * 0.2) + np.sin(f2 * s * 2.0 * np.pi + t * 0.1)) * decay
    hy = (np.sin(f3 * s * 2.0 * np.pi + t * 0.3) + np.sin(f4 * s * 2.0 * np.pi + ph)) * decay
    hz = (np.cos(f1 * s * 2.0 * np.pi + t * 0.15) + np.cos(f3 * s * 2.0 * np.pi)) * decay
    tube = 0.16 + 0.05 * state["tide"]
    x = (hx + tube * np.cos(phi) * np.cos(theta * 4.0)) * radial
    y = (hy + tube * np.sin(phi)) * radial
    z = (hz + tube * np.cos(phi) * np.sin(theta * 4.0)) * radial
    return x, y, z


def hyperbolic_tiling(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Hyperbolic tiling (Poincare disk) mapped onto a sphere."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    u = np.cos(theta) * np.sin(phi)
    v = np.sin(theta) * np.sin(phi)
    r_disk = np.sqrt(u * u + v * v) + 1e-9
    r_norm = np.clip(r_disk, 0.0, 0.95)
    angle = np.arctan2(v, u)
    p = 7
    q = 3
    k = np.floor(p * angle / (2.0 * np.pi) + t * 0.1)
    sector = angle - (2.0 * np.pi / p) * k
    ref = np.pi / p
    folded = np.abs(np.mod(sector + ref, 2.0 * np.pi / p) - ref)
    hyper_r = np.tanh(r_norm * 2.5) * 0.9
    grid = np.sin(q * folded * p + hyper_r * 6.0 - t * 0.4)
    edge = np.abs(np.cos(q * folded * p))
    z_disp = 0.35 * grid * edge * (1.0 - r_norm)
    x = np.sin(phi) * np.cos(theta) * radial
    y = np.sin(phi) * np.sin(theta) * radial
    z = (np.cos(phi) + z_disp + 0.10 * state["bloom"] * edge) * radial
    return x, y, z


def smoke_plume(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Smoke plume: particles rising with turbulent sine noise, radius expanding."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    height = phi / np.pi
    swirl = theta + 0.6 * height + t * 0.3
    radius = 0.25 + 0.55 * height + 0.08 * np.sin(4.0 * theta + t * 0.7)
    turb = (
        0.12 * np.sin(5.0 * theta + 3.0 * height + t * 0.5)
        + 0.08 * np.sin(9.0 * theta - 2.0 * height + t * 0.8)
        + 0.05 * state["bloom"] * np.sin(7.0 * theta + t)
    )
    x = (radius + turb) * np.cos(swirl) * radial
    y = (radius + turb) * np.sin(swirl) * radial
    z = (2.0 * height - 1.0) * radial
    return x, y, z


def fire_flame(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Flame: wide base, narrow tip, vertical sine oscillation and flicker."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    height = (phi / np.pi) ** 1.2
    base = 0.9 * (1.0 - height) + 0.05
    flicker = 0.12 * np.sin(8.0 * theta + 12.0 * height + t * 6.0)
    wobble = 0.06 * np.sin(3.0 * theta + t * 2.0) * height
    r = (base + flicker + wobble) * (1.0 + 0.20 * state["bloom"])
    x = r * np.cos(theta + 0.4 * height * np.sin(t * 0.5)) * radial
    y = r * np.sin(theta + 0.4 * height * np.sin(t * 0.5)) * radial
    z = (2.2 * height - 1.0) * radial + 0.08 * state["rupture"] * np.sin(6.0 * theta)
    return x, y, z


def plasma_field(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Plasma field: multiple interfering sines ripple the surface."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    s1 = np.sin(3.0 * theta + 2.0 * phi + t * 0.8)
    s2 = np.sin(5.0 * theta - 3.0 * phi + t * 1.2)
    s3 = np.sin(4.0 * theta * phi + t * 0.6)
    s4 = np.sin(np.sqrt(theta * theta + phi * phi) * 4.0 - t * 0.9)
    plasma = 0.30 * (s1 + s2 + s3 + s4) + 0.20 * state["bloom"]
    r = (0.8 + plasma) * radial
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.sin(phi) * np.sin(theta)
    z = r * np.cos(phi) + 0.05 * state["tide"] * s1
    return x, y, z


def lightning_bolt(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Lightning: fractal midpoint-displacement bolt with branches, z = distance."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    seed = int(profile.get("seed", 0))
    rng = np.random.default_rng(seed ^ 0x4C49474854)
    n_pts = 33
    s = np.linspace(0.0, 1.0, n_pts)
    bx = np.zeros(n_pts)
    bz = np.linspace(-1.0, 1.0, n_pts)
    for level in range(5):
        step = 2 ** (4 - level)
        amp = 0.3 / (2.0 ** level)
        for i in range(step, n_pts - 1, 2 * step):
            lo = i - step
            hi = i + step
            if hi >= n_pts:
                continue
            bx[i] = 0.5 * (bx[lo] + bx[hi]) + float(rng.standard_normal()) * amp
    bx = bx + 0.30 * np.sin(t * 3.0 + s * 6.0)
    bx_s = np.interp(theta / (2.0 * np.pi), s, bx)
    bz_s = np.interp(theta / (2.0 * np.pi), s, bz)
    dx = np.cos(phi) - bx_s
    dz = np.sin(phi) - bz_s
    dist = np.sqrt(dx * dx + dz * dz)
    glow = np.exp(-dist * 8.0) * (1.0 + 0.5 * state["rupture"])
    branch = 0.20 * np.exp(-dist * 4.0) * np.sin(theta * 10.0 + t * 5.0)
    x = (bx_s + 0.10 * np.cos(phi) + branch) * radial
    y = (0.30 + 0.25 * glow) * np.sin(theta * 2.0) * radial
    z = (bz_s + 0.10 * np.sin(phi) + branch) * radial
    return x, y, z


def ink_in_water(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Ink in water: turbulent radial blobs with translucency-driven displacement."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    seed = int(profile.get("seed", 0))
    rng = np.random.default_rng(seed ^ 0x494E4B)
    n_blobs = 6
    bx = rng.uniform(-0.6, 0.6, n_blobs)
    by = rng.uniform(-0.6, 0.6, n_blobs)
    freq = rng.uniform(2.0, 5.0, n_blobs)
    phase_b = rng.uniform(0.0, 2.0 * np.pi, n_blobs)
    u = np.cos(theta) * np.sin(phi)
    v = np.sin(theta) * np.sin(phi)
    field = np.zeros_like(u)
    for i in range(n_blobs):
        cx = bx[i] + 0.20 * np.sin(t * freq[i] + phase_b[i])
        cy = by[i] + 0.20 * np.cos(t * freq[i] * 0.7 + phase_b[i])
        r2 = (u - cx) ** 2 + (v - cy) ** 2
        field += np.exp(-r2 * 3.0) * (0.5 + 0.5 * np.sin(t * freq[i] + phase_b[i]))
    r = (0.7 + 0.45 * field + 0.15 * state["bloom"]) * radial
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.sin(phi) * np.sin(theta)
    z = r * np.cos(phi) + 0.10 * field * np.sin(4.0 * theta + t)
    return x, y, z


def ferrofluid(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Ferrofluid: sharp axial spikes whose height tracks the magnetic field."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    field = 0.5 + 0.5 * np.sin(t * 1.5) + 0.20 * state["compression"]
    cos_t = np.cos(theta)
    spike = 1.0 / (np.abs(cos_t) + 0.08)
    spike = np.clip(spike, 0.0, 6.0)
    height = field * (spike - 1.0) * 0.20
    r = (0.8 + height) * radial
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.sin(phi) * np.sin(theta)
    z = (r * np.cos(phi) + 0.15 * height * np.sign(cos_t)) * (1.0 + 0.10 * state["bloom"])
    return x, y, z


def caustics(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Caustics: interfering 2D sines form focused light patterns, z = intensity."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    u = theta * 2.0
    v = phi * 2.0
    c1 = np.sin(u * 3.0 + t * 0.7) + np.sin(v * 3.0 - t * 0.5)
    c2 = np.sin(u * 5.0 - v * 2.0 + t * 1.1)
    c3 = np.sin(np.sqrt((u - np.pi) ** 2 + (v - np.pi) ** 2) * 4.0 - t * 0.9)
    intensity = 0.5 + 0.25 * (c1 + c2 + c3) / 3.0 + 0.15 * state["tide"]
    scale = 1.6
    x = (u / np.pi - 1.0) * scale * radial
    y = (v / np.pi - 0.5) * scale * radial
    z = (intensity - 0.5) * scale * radial
    return x, y, z


def dna_helix(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Double DNA helix: two strands 180 degrees apart with connecting rungs."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    turns = 3.0 + float(profile.get("twist", 0.5)) * 2.0
    s = theta / (2.0 * np.pi)
    strand = np.sign(np.cos(phi))
    helix_a = s * turns * 2.0 * np.pi + t * 0.5
    helix_b = helix_a + np.pi
    r_helix = 0.55 + 0.05 * np.sin(s * 10.0 + t)
    rung = np.abs(np.cos(phi * 6.0)) * 0.20 * (1.0 - np.abs(strand) * 0.3)
    cos_a = r_helix * np.cos(helix_a)
    cos_b = r_helix * np.cos(helix_b)
    x = (cos_a * (strand > 0) + cos_b * (strand <= 0) + rung * np.cos(helix_a)) * radial
    y = (s * 2.0 - 1.0 + 0.05 * state["bloom"]) * radial
    sin_a = r_helix * np.sin(helix_a)
    sin_b = r_helix * np.sin(helix_b)
    z = (sin_a * (strand > 0) + sin_b * (strand <= 0) + rung * np.sin(helix_a)) * radial
    return x, y, z


def aurora(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Aurora borealis: undulating curtains, low frequency in x, high in z."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    height = phi / np.pi
    curtain = np.sin(2.0 * theta + t * 0.4) * np.sin(6.0 * height + t * 0.8)
    shimmer = 0.30 * np.sin(14.0 * theta + 20.0 * height + t * 1.5)
    brightness = 0.5 + 0.5 * (curtain + shimmer) + 0.25 * state["bloom"]
    r = (0.7 + 0.40 * brightness) * radial
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.sin(phi) * np.sin(theta)
    z = (r * np.cos(phi) + 0.25 * curtain * (1.0 - height)) * (1.0 + 0.08 * state["tide"])
    return x, y, z


def accretion_disk(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Accretion disk: flattened, rotating, bright inner edge, diffuse outer."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    r_disk = 0.4 + 1.2 * (phi / np.pi)
    swirl = theta + 2.0 * np.log(r_disk + 0.1) + t * 0.8
    inner = np.exp(-(r_disk - 0.4) * 6.0)
    outer = np.exp(-(2.0 - r_disk) * 1.2)
    thickness = 0.08 * (inner + 0.3 * outer) + 0.03 * np.sin(5.0 * theta + t * 1.5)
    r = r_disk * radial
    x = r * np.cos(swirl)
    y = r * np.sin(swirl)
    z = thickness * (1.0 + 0.40 * state["compression"]) + 0.05 * state["bloom"] * inner
    return x, y, z


def gravitational_lens(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Gravitational lens: concentric Einstein rings distorted by central mass."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    mass = 0.6 + 0.20 * np.sin(t * 0.3) + 0.15 * state["compression"]
    u = np.cos(theta) * np.sin(phi)
    v = np.sin(theta) * np.sin(phi)
    r0 = np.sqrt(u * u + v * v) + 1e-3
    bend = mass / (r0 + 0.2)
    rings = np.sin(r0 * 12.0 - t * 0.5)
    distortion = 0.20 * np.sin(4.0 * theta + 3.0 * r0 * np.pi + t * 0.4)
    r = (0.6 + 0.50 * rings * np.exp(-r0 * 2.0) + bend * 0.15 + distortion) * radial
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.sin(phi) * np.sin(theta)
    z = (r * np.cos(phi) + 0.10 * state["bloom"] * rings) * (1.0 + 0.05 * bend)
    return x, y, z


def menger_sponge(theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Menger sponge: iterative 3D subdivision simplified to a surface field."""
    state, radial = _event_modulation(theta, phi, t, profile, events)
    px = np.sin(phi) * np.cos(theta)
    py = np.sin(phi) * np.sin(theta)
    pz = np.cos(phi)
    level = int(profile.get("growth_iterations", 4))
    for _ in range(level):
        cx = np.abs(px * 3.0 - np.round(px * 3.0))
        cy = np.abs(py * 3.0 - np.round(py * 3.0))
        cz = np.abs(pz * 3.0 - np.round(pz * 3.0))
        m = np.maximum(np.maximum(cx, cy), cz)
        hole = ((cx > 0.5) & (cy > 0.5)) | ((cx > 0.5) & (cz > 0.5)) | ((cy > 0.5) & (cz > 0.5))
        px = np.where(hole, px + 0.05 * np.sign(px), px)
        py = np.where(hole, py + 0.05 * np.sign(py), py)
        pz = np.where(hole, pz + 0.05 * np.sign(pz), pz)
        px = (px * 3.0 - np.round(px * 3.0)) / 3.0
        py = (py * 3.0 - np.round(py * 3.0)) / 3.0
        pz = (pz * 3.0 - np.round(pz * 3.0)) / 3.0
    density = 1.0 - m
    r = (0.7 + 0.45 * density + 0.15 * state["bloom"]) * radial
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.sin(phi) * np.sin(theta)
    z = r * np.cos(phi)
    return x, y, z


VISUAL_FAMILIES_EXTENDED = (
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


def dispatch(name: str, theta: np.ndarray, phi: np.ndarray, t: float, profile: dict, events: list):
    """Resolve a family name to its (x, y, z) coordinate arrays."""
    fn = globals().get(name)
    if not callable(fn):
        raise KeyError(f"unknown visual family: {name}")
    return fn(theta, phi, t, profile, events)
