"""Flow field simulator using multi-octave Perlin/simplex-like noise.

Particles follow a time-evolving vector field with edge wrapping and trails.
The noise basis is a deterministic hash-gradient interpolation so the field is
fully reproducible per seed without any external asset or dependency.
"""

from __future__ import annotations

import math

import numpy as np

_STEP_DT = 0.05
_STEP_LEN = 40.0


def _hash_angle(seed: int, ix: int, iy: int, iz: int) -> float:
    """Deterministic pseudo-random angle in [0, 2*pi) at an integer lattice node."""
    h = (seed * 374761393 + ix * 668265263 + iy * 2246822519 + iz * 2147483647) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFF) / 0xFFFF * 2.0 * math.pi


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smooth_v(t: np.ndarray) -> np.ndarray:
    return t * t * (3.0 - 2.0 * t)


def _lerp_v(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    return a + (b - a) * t


def _grad(seed: int, ix: int, iy: int, iz: int, dx: float, dy: float) -> float:
    angle = _hash_angle(seed, ix, iy, iz)
    return dx * math.cos(angle) + dy * math.sin(angle)


def _grad_v(seed: int, ix: np.ndarray, iy: np.ndarray, iz: int, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    h = (seed * 374761393 + ix * 668265263 + iy * 2246822519 + iz * 2147483647) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    angle = (h & 0xFFFF).astype(np.float64) / 0xFFFF * 2.0 * math.pi
    return dx * np.cos(angle) + dy * np.sin(angle)


class FlowField:
    """Multi-octave noise flow field with time evolution.

    Parameters
    ----------
    seed:
        Deterministic seed for the field.
    width, height:
        Spatial extent of the field in arbitrary units (particles wrap).
    scale:
        Base noise wavelength scale; smaller values give denser structure.
    """

    def __init__(self, seed: int, width: float, height: float, scale: float = 120.0) -> None:
        self.seed = int(seed)
        self.width = float(width)
        self.height = float(height)
        self.scale = max(1.0, float(scale))
        # Octave tuning: amplitude halves each octave, frequency doubles.
        self._octave_amps = (1.0, 0.5, 0.25, 0.125)
        self._octave_freqs = (1.0, 2.0, 4.0, 8.0)
        self._time_scale = 0.15

    def _noise_scalar(self, x: float, y: float, z: float) -> float:
        """Value-noise with gradients: returns a scalar in roughly [-1, 1]."""
        x0 = math.floor(x)
        y0 = math.floor(y)
        z0 = math.floor(z)
        fx = _smooth(x - x0)
        fy = _smooth(y - y0)
        fz = _smooth(z - z0)
        d000 = _grad(self.seed, x0, y0, z0, x - x0, y - y0)
        d100 = _grad(self.seed, x0 + 1, y0, z0, x - x0 - 1, y - y0)
        d010 = _grad(self.seed, x0, y0 + 1, z0, x - x0, y - y0 - 1)
        d110 = _grad(self.seed, x0 + 1, y0 + 1, z0, x - x0 - 1, y - y0 - 1)
        d001 = _grad(self.seed, x0, y0, z0 + 1, x - x0, y - y0)
        d101 = _grad(self.seed, x0 + 1, y0, z0 + 1, x - x0 - 1, y - y0)
        d011 = _grad(self.seed, x0, y0 + 1, z0 + 1, x - x0, y - y0 - 1)
        d111 = _grad(self.seed, x0 + 1, y0 + 1, z0 + 1, x - x0 - 1, y - y0 - 1)
        x00 = _lerp(d000, d100, fx)
        x10 = _lerp(d010, d110, fx)
        x01 = _lerp(d001, d101, fx)
        x11 = _lerp(d011, d111, fx)
        y0v = _lerp(x00, x10, fy)
        y1v = _lerp(x01, x11, fy)
        return _lerp(y0v, y1v, fz)

    def _noise_v(self, xs: np.ndarray, ys: np.ndarray, z: float) -> np.ndarray:
        """Vectorized value-noise scalar field with deterministic gradients."""
        x0 = np.floor(xs).astype(np.int64)
        y0 = np.floor(ys).astype(np.int64)
        z0 = int(math.floor(z))
        fx = _smooth_v(xs - x0)
        fy = _smooth_v(ys - y0)
        fz = _smooth_v(np.asarray(z - z0, dtype=np.float64))
        d000 = _grad_v(self.seed, x0, y0, z0, xs - x0, ys - y0)
        d100 = _grad_v(self.seed, x0 + 1, y0, z0, xs - x0 - 1, ys - y0)
        d010 = _grad_v(self.seed, x0, y0 + 1, z0, xs - x0, ys - y0 - 1)
        d110 = _grad_v(self.seed, x0 + 1, y0 + 1, z0, xs - x0 - 1, ys - y0 - 1)
        d001 = _grad_v(self.seed, x0, y0, z0 + 1, xs - x0, ys - y0)
        d101 = _grad_v(self.seed, x0 + 1, y0, z0 + 1, xs - x0 - 1, ys - y0)
        d011 = _grad_v(self.seed, x0, y0 + 1, z0 + 1, xs - x0, ys - y0 - 1)
        d111 = _grad_v(self.seed, x0 + 1, y0 + 1, z0 + 1, xs - x0 - 1, ys - y0 - 1)
        x00 = _lerp_v(d000, d100, fx)
        x10 = _lerp_v(d010, d110, fx)
        x01 = _lerp_v(d001, d101, fx)
        x11 = _lerp_v(d011, d111, fx)
        y0v = _lerp_v(x00, x10, fy)
        y1v = _lerp_v(x01, x11, fy)
        return _lerp_v(y0v, y1v, fz)

    def field_at(self, x: float, y: float, t: float) -> tuple[float, float]:
        """Return the (vx, vy) flow vector at position (x, y) at time t."""
        z = t * self._time_scale
        vx = 0.0
        vy = 0.0
        for amp, freq in zip(self._octave_amps, self._octave_freqs, strict=True):
            nx = x / self.scale * freq
            ny = y / self.scale * freq
            # Two offset noise samples per octave form a 2D vector.
            vx += amp * self._noise_scalar(nx, ny, z)
            vy += amp * self._noise_scalar(nx + 31.7, ny - 17.3, z + 5.2)
        return (vx, vy)

    def _field_v(self, xs: np.ndarray, ys: np.ndarray, t: float) -> tuple[np.ndarray, np.ndarray]:
        """Vectorized field evaluation for many points at once."""
        z = t * self._time_scale
        vx = np.zeros_like(xs, dtype=np.float64)
        vy = np.zeros_like(ys, dtype=np.float64)
        for amp, freq in zip(self._octave_amps, self._octave_freqs, strict=True):
            nx = xs / self.scale * freq
            ny = ys / self.scale * freq
            vx += amp * self._noise_v(nx, ny, z)
            vy += amp * self._noise_v(nx + 31.7, ny - 17.3, z + 5.2)
        return vx, vy


def render_flow_particles(
    field: FlowField,
    t: float,
    num_particles: int = 200,
    trail_length: int = 20,
) -> list[list[tuple[float, float]]]:
    """Advance a population of particles through the field and return their trails.

    Each returned trail is a list of (x, y) positions of length ``trail_length``.
    Particles wrap around the field edges so motion is continuous. The trail is a
    streamline of the field snapshot at time ``t``; the head is the most recent
    position. Deterministic for a given field seed.
    """
    rng = np.random.default_rng(field.seed)
    xs = rng.uniform(0.0, field.width, size=num_particles)
    ys = rng.uniform(0.0, field.height, size=num_particles)
    trails: list[list[tuple[float, float]]] = []
    for i in range(num_particles):
        cx = float(xs[i])
        cy = float(ys[i])
        # Build the trail by stepping backward from the head so the last point
        # is the seed position; then reverse so the trail leads into the head.
        back: list[tuple[float, float]] = []
        bx, by = cx, cy
        for _ in range(trail_length - 1):
            # Use the field snapshot at t for a coherent streamline.
            vx, vy = field.field_at(bx, by, t)
            sp = math.hypot(vx, vy) + 1e-9
            # Step backwards along the flow to trace the trail into the head.
            bx = (bx - vx / sp * _STEP_DT * _STEP_LEN) % field.width
            by = (by - vy / sp * _STEP_DT * _STEP_LEN) % field.height
            back.append((bx, by))
        back.reverse()
        back.append((cx, cy))
        trails.append(back)
    return trails
