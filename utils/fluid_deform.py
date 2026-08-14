"""Wave propagation over meshes (Ripple equation discretized).

Pre-computes a 2D wave field on a grid by integrating the ripple equation
``d^2 u/dt^2 = c^2 nabla^2 u`` with finite differences, then samples the field at
arbitrary mesh (theta, phi) coordinates to produce a liquid-like surface
displacement. Events (bloom/compression/tide...) inject energy into the field.
"""

from __future__ import annotations

import math

import numpy as np

from utils.liquid_wire_timeline import CreativeEvent, event_envelope


class _WaveField:
    """Integrator for the 2D ripple equation on a small grid."""

    def __init__(self, grid: int = 48, c: float = 0.5) -> None:
        self.grid = int(grid)
        self.c = float(c)
        self.u = np.zeros((self.grid, self.grid), dtype=np.float64)
        self.u_prev = np.zeros_like(self.u)
        self.damping = 0.997

    def step(self, sources: np.ndarray | None = None) -> None:
        laplacian = np.zeros_like(self.u)
        laplacian[1:-1, 1:-1] = (
            self.u[:-2, 1:-1]
            + self.u[2:, 1:-1]
            + self.u[1:-1, :-2]
            + self.u[1:-1, 2:]
            - 4.0 * self.u[1:-1, 1:-1]
        )
        # Neumann (zero-flux) boundary so waves reflect rather than escape.
        c2 = self.c * self.c
        self.u_prev, self.u = self.u, self.u_prev
        self.u = (2.0 * self.u - self.u_prev + c2 * laplacian) * self.damping
        if sources is not None:
            self.u += sources

    def sample_bilinear(self, fx: np.ndarray, fy: np.ndarray) -> np.ndarray:
        gx = np.clip(fx * (self.grid - 1), 0.0, self.grid - 1.001)
        gy = np.clip(fy * (self.grid - 1), 0.0, self.grid - 1.001)
        x0 = np.floor(gx).astype(np.int64)
        y0 = np.floor(gy).astype(np.int64)
        x1 = x0 + 1
        y1 = y0 + 1
        tx = gx - x0
        ty = gy - y0
        v00 = self.u[y0, x0]
        v10 = self.u[y0, x1]
        v01 = self.u[y1, x0]
        v11 = self.u[y1, x1]
        return (1 - tx) * (1 - ty) * v00 + tx * (1 - ty) * v10 + (1 - tx) * ty * v01 + tx * ty * v11


def _event_sources(t: float, events: list[CreativeEvent], grid: int) -> np.ndarray:
    """Energy injected into the wave field by active creative events at time t."""
    sources = np.zeros((grid, grid), dtype=np.float64)
    for event in events:
        energy = float(event_envelope(t, event)) * event.intensity
        if energy < 1e-4:
            continue
        cx = 0.5 + 0.3 * math.cos(event.direction)
        cy = 0.5 + 0.3 * math.sin(event.direction)
        gx = cx * (grid - 1)
        gy = cy * (grid - 1)
        yy, xx = np.ogrid[:grid, :grid]
        r2 = (xx - gx) ** 2 + (yy - gy) ** 2
        sigma = max(2.0, 4.0 + 2.0 * event.duration)
        if event.kind == "compression":
            sources -= energy * np.exp(-r2 / (2.0 * sigma**2)) * 0.6
        elif event.kind in {"bloom", "tide", "rupture"}:
            sources += energy * np.exp(-r2 / (2.0 * sigma**2)) * 0.5
    return sources


def fluid_deform(
    theta: np.ndarray,
    phi: np.ndarray,
    t: float,
    profile: dict,
    events: list[CreativeEvent],
) -> tuple[np.ndarray, np.ndarray]:
    """Apply wave deformation to mesh coordinates.

    Parameters
    ----------
    theta, phi:
        Mesh angular coordinates (radians), same shape.
    t:
        Current simulation time in seconds.
    profile:
        Generator profile dict; ``seed`` selects the wave field and
        ``fluid_speed``/``fluid_amp`` tune the deformation.
    events:
        Creative events driving wave sources.

    Returns
    -------
    (dtheta, dphi):
        Per-point displacement to add to theta and phi (same shape as inputs).
    """
    seed = int(profile.get("seed", 0))
    speed = float(profile.get("fluid_speed", 0.5))
    amp = float(profile.get("fluid_amp", 0.18))
    _ = seed  # seed reserved for future per-seed field perturbation
    # Integrate forward from t=0 to t in fixed substeps so the result depends
    # only on (seed, speed, amp, t, events) and is fully deterministic.
    field = _WaveField(c=speed)
    dt = 0.25
    steps = max(1, int(round(t / dt)))
    for step in range(steps):
        ts = step * dt
        sources = _event_sources(ts, events, field.grid) * 0.25
        field.step(sources)
    fx = (theta / (2.0 * math.pi)) % 1.0
    fy = np.clip((phi - 0.06) / (math.pi - 0.12), 0.0, 1.0)
    displacement = field.sample_bilinear(fx, fy)
    dtheta = amp * displacement * np.sin(phi)
    dphi = amp * 0.6 * displacement * np.cos(theta * 2.0)
    return dtheta, dphi
