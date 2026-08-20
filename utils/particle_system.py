"""Physics-based particle system with attraction, repulsion and damping.

Particles carry position, velocity, mass and charge. Nearby particles interact
through a spring force plus a charge-dependent attraction/repulsion term, while
a global damping coefficient bleeds energy so the swarm settles into structures.
All randomness is driven by a single numpy Generator for reproducibility.
"""

from __future__ import annotations

import math

import numpy as np


class ParticleSystem:
    """A 2D physics particle swarm with spring + electrostatic-style forces.

    Parameters
    ----------
    seed:
        Deterministic seed for initial positions/velocities/charges.
    num_particles:
        Number of particles in the system.
    width, height:
        Bounds of the simulation area; particles reflect softly at the edges.
    """

    def __init__(self, seed: int, num_particles: int, width: float, height: float) -> None:
        self.seed = int(seed)
        self.num_particles = int(num_particles)
        self.width = float(width)
        self.height = float(height)
        rng = np.random.default_rng(self.seed)
        self.pos = rng.uniform([0.0, 0.0], [width, height], size=(self.num_particles, 2)).astype(np.float64)
        self.vel = rng.normal(0.0, 8.0, size=(self.num_particles, 2)).astype(np.float64)
        self.mass = rng.uniform(0.8, 1.6, size=self.num_particles).astype(np.float64)
        self.charge = rng.choice([-1.0, 1.0], size=self.num_particles).astype(np.float64)
        # Tunable physics constants (kept as attributes for experimentation).
        self.spring_k = 0.6
        self.rest_length = 90.0
        self.coulomb_k = 1200.0
        self.damping = 0.92
        self.interaction_radius = 140.0
        self._max_speed = 320.0
        self._initial_pos = self.pos.copy()
        self._initial_vel = self.vel.copy()

    def update(self, dt: float, t: float) -> None:
        """Advance the physics by ``dt`` seconds. ``t`` is available for forcing."""
        pos = self.pos
        # Pairwise displacement vectors (n, n, 2).
        diff = pos[None, :, :] - pos[:, None, :]
        dist2 = (diff[..., 0] ** 2 + diff[..., 1] ** 2) + 1e-6
        dist = np.sqrt(dist2)
        np.fill_diagonal(dist, 1.0)  # avoid self-interaction
        # Spring force: pulls neighbours toward rest_length when within radius.
        within = (dist < self.interaction_radius) & (dist > 0.0)
        spring_mag = np.where(within, self.spring_k * (dist - self.rest_length), 0.0)
        spring_vec = spring_mag[..., None] * (diff / dist[..., None])
        # Coulomb-style attraction/repulsion based on charge sign product.
        q_prod = self.charge[:, None] * self.charge[None, :]
        # Opposite charges attract (negative q_prod) -> pull together; like charges repel.
        coulomb_mag = np.where(within, -self.coulomb_k * q_prod / dist2, 0.0)
        coulomb_vec = coulomb_mag[..., None] * (diff / dist[..., None])
        # Sum forces per particle.
        force = (spring_vec + coulomb_vec).sum(axis=1)
        # Soft centring force grows toward the edges so the swarm stays on screen.
        centre = np.array([self.width * 0.5, self.height * 0.5])
        pull = (centre - pos) * 0.02
        force += pull
        # Gentle time-varying swirl to keep the field alive at long times.
        swirl = 0.04 * np.sin(t * 0.7 + self.charge * 2.0)
        force[:, 0] += -swirl * (pos[:, 1] - centre[1])
        force[:, 1] += swirl * (pos[:, 0] - centre[0])
        acc = force / self.mass[:, None]
        self.vel = (self.vel + acc * dt) * self.damping
        speed = np.linalg.norm(self.vel, axis=1, keepdims=True)
        too_fast = speed > self._max_speed
        self.vel = np.where(too_fast, self.vel / speed * self._max_speed, self.vel)
        self.pos = self.pos + self.vel * dt
        # Soft reflection at the bounds.
        for axis, limit in enumerate((self.width, self.height)):
            below = self.pos[:, axis] < 0.0
            above = self.pos[:, axis] > limit
            self.pos[below, axis] = -self.pos[below, axis]
            self.pos[above, axis] = 2.0 * limit - self.pos[above, axis]
            self.vel[below, axis] = np.abs(self.vel[below, axis])
            self.vel[above, axis] = -np.abs(self.vel[above, axis])
        # Clamp to keep numerical drift from escaping the frame.
        self.pos[:, 0] = np.clip(self.pos[:, 0], 0.0, self.width)
        self.pos[:, 1] = np.clip(self.pos[:, 1], 0.0, self.height)

    def positions(self) -> np.ndarray:
        """Return a copy of current particle positions as (n, 2) array."""
        return self.pos.copy()

    def positions_at(self, t: float) -> np.ndarray:
        """Evaluate a bounded swarm trajectory in O(n), independently per frame.

        The old renderer replayed every 33 ms physics step from time zero for
        every frame. That made a long render quadratic in duration. This
        closed-form orbit retains deterministic charge, mass, velocity and
        multi-frequency motion without accumulating state between workers.
        """
        seconds = max(0.0, float(t))
        centre = np.asarray([self.width * 0.5, self.height * 0.5], dtype=np.float64)
        relative = self._initial_pos - centre
        indices = np.arange(self.num_particles, dtype=np.float64)
        angle = self.charge * (0.10 + 0.035 / self.mass) * seconds
        angle += 0.11 * np.sin(seconds * 0.31 + indices * 0.17)
        cosine, sine = np.cos(angle), np.sin(angle)
        rotated = np.column_stack(
            (
                relative[:, 0] * cosine - relative[:, 1] * sine,
                relative[:, 0] * sine + relative[:, 1] * cosine,
            )
        )
        phase = indices * 0.37 + self.charge
        scale = 1.0 + 0.12 * (np.sin(seconds * 0.43 + phase) - np.sin(phase))
        # The scalar damping integral broadcasts over the initial velocity.
        drift_scale = (1.0 - math.exp(-seconds * 0.35)) / 0.35
        drift = self._initial_vel * drift_scale
        wave = np.column_stack(
            (
                np.sin(seconds * 0.73 + phase) - np.sin(phase),
                np.cos(seconds * 0.59 + phase) - np.cos(phase),
            )
        ) * np.minimum(self.width, self.height) * 0.035
        result = centre + rotated * scale[:, None] + drift + wave
        result[:, 0] = np.clip(result[:, 0], 0.0, self.width)
        result[:, 1] = np.clip(result[:, 1], 0.0, self.height)
        return result


def render(state: ParticleSystem, profile: dict, t: float, width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (sx, sy) screen coordinates for drawing the swarm.

    ``profile`` may carry a ``palette`` for hue cycling; this helper only maps
    simulation coordinates to pixel space so the renderer stays decoupled.
    """
    pos = state.positions_at(t)
    sx = (pos[:, 0] / state.width) * width
    sy = (pos[:, 1] / state.height) * height
    return sx, sy
