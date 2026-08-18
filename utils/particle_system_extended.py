from dataclasses import dataclass

import numpy as np


@dataclass
class Particle:
    pos: np.ndarray
    vel: np.ndarray
    age: float
    lifetime: float
    size: float
    color: np.ndarray
    alpha: float
    type: str
    seed: float = 0.0


class Emitter:
    def __init__(
        self,
        position,
        spawn_rate=10.0,
        particle_type="embers",
        initial_velocity=(0, 1, 0),
        lifetime_range=(1.0, 3.0),
        size_range=(0.5, 1.5),
        color_gradient=None,
        seed=0,
    ) -> None:
        self.position = np.asarray(position, dtype=np.float64)
        self.spawn_rate = float(spawn_rate)
        self.particle_type = particle_type
        self.initial_velocity = np.asarray(initial_velocity, dtype=np.float64)
        self.lifetime_range = (float(lifetime_range[0]), float(lifetime_range[1]))
        self.size_range = (float(size_range[0]), float(size_range[1]))
        self.color_gradient = color_gradient
        self._accumulator = 0.0
        self._rng = np.random.RandomState(seed)
        self._seed_counter = 0

    def _random_color(self):
        if self.color_gradient is not None and len(self.color_gradient) >= 2:
            t = self._rng.rand()
            c0 = np.asarray(self.color_gradient[0], dtype=np.float64)
            c1 = np.asarray(self.color_gradient[1], dtype=np.float64)
            if len(self.color_gradient) > 2:
                idx_f = t * (len(self.color_gradient) - 1)
                i0 = int(idx_f)
                i1 = min(i0 + 1, len(self.color_gradient) - 1)
                f = idx_f - i0
                c0 = np.asarray(self.color_gradient[i0], dtype=np.float64)
                c1 = np.asarray(self.color_gradient[i1], dtype=np.float64)
                return (1.0 - f) * c0 + f * c1
            return (1.0 - t) * c0 + t * c1
        return np.array([1.0, 1.0, 1.0], dtype=np.float64)

    def _make_particle(self):
        lt = self._rng.uniform(*self.lifetime_range)
        sz = self._rng.uniform(*self.size_range)
        jitter = self._rng.normal(0.0, 0.05, size=3)
        pos = self.position + jitter
        vel = self.initial_velocity + self._rng.normal(0.0, 0.1, size=3)
        col = self._random_color()
        a = 1.0
        self._seed_counter += 1
        return Particle(
            pos=pos.copy(),
            vel=vel.copy(),
            age=0.0,
            lifetime=lt,
            size=sz,
            color=col,
            alpha=a,
            type=self.particle_type,
            seed=float(self._seed_counter),
        )

    def update(self, dt, t):
        self._accumulator += self.spawn_rate * dt
        new_count = int(self._accumulator)
        self._accumulator -= new_count
        return [self._make_particle() for _ in range(new_count)]


_PRESETS = {
    "embers": {
        "vel": (0.0, 1.5, 0.0),
        "lifetime": (0.8, 1.8),
        "size": (0.3, 0.8),
        "colors": [(1.0, 0.2, 0.0), (1.0, 0.9, 0.2), (1.0, 1.0, 0.6)],
        "rate": 30.0,
    },
    "sparks": {
        "vel": (0.0, 5.0, 0.0),
        "lifetime": (0.3, 0.8),
        "size": (0.1, 0.4),
        "colors": [(1.0, 1.0, 0.8), (1.0, 0.6, 0.2)],
        "rate": 60.0,
    },
    "dust": {
        "vel": (0.0, 0.1, 0.0),
        "lifetime": (4.0, 8.0),
        "size": (0.4, 1.0),
        "colors": [(0.6, 0.6, 0.55), (0.4, 0.4, 0.4)],
        "rate": 8.0,
    },
    "smoke": {
        "vel": (0.0, 0.8, 0.0),
        "lifetime": (3.0, 6.0),
        "size": (0.8, 2.0),
        "colors": [(0.3, 0.3, 0.3), (0.05, 0.05, 0.05)],
        "rate": 15.0,
    },
    "rain": {
        "vel": (0.0, -15.0, 0.0),
        "lifetime": (1.0, 2.0),
        "size": (0.1, 0.2),
        "colors": [(0.6, 0.7, 1.0), (0.4, 0.5, 0.8)],
        "rate": 80.0,
    },
    "snow": {
        "vel": (0.0, -0.8, 0.0),
        "lifetime": (5.0, 10.0),
        "size": (0.5, 1.2),
        "colors": [(1.0, 1.0, 1.0), (0.9, 0.9, 1.0)],
        "rate": 20.0,
    },
    "bubbles": {
        "vel": (0.0, 1.0, 0.0),
        "lifetime": (2.0, 4.0),
        "size": (0.3, 1.0),
        "colors": [(0.7, 0.8, 1.0), (0.5, 0.6, 0.9)],
        "rate": 12.0,
    },
    "fireflies": {
        "vel": (0.0, 0.0, 0.0),
        "lifetime": (3.0, 7.0),
        "size": (0.2, 0.4),
        "colors": [(1.0, 1.0, 0.3), (0.9, 0.8, 0.1)],
        "rate": 5.0,
    },
    "debris": {
        "vel": (0.0, 0.0, 0.0),
        "lifetime": (1.0, 2.5),
        "size": (0.3, 0.9),
        "colors": [(0.6, 0.4, 0.2), (0.3, 0.2, 0.1)],
        "rate": 40.0,
    },
}


def make_emitter(particle_type, position, seed=0, **overrides):
    preset = _PRESETS.get(particle_type, _PRESETS["embers"])
    params = {
        "position": position,
        "spawn_rate": preset["rate"],
        "particle_type": particle_type,
        "initial_velocity": preset["vel"],
        "lifetime_range": preset["lifetime"],
        "size_range": preset["size"],
        "color_gradient": preset["colors"],
        "seed": seed,
    }
    params.update(overrides)
    return Emitter(**params)


class ParticleSystemExtended:
    def __init__(
        self,
        gravity=(0, -9.81, 0),
        wind=(0, 0, 0),
        drag=0.0,
        seed=0,
    ) -> None:
        self.emitters: list[Emitter] = []
        self.particles: list[Particle] = []
        self.gravity = np.asarray(gravity, dtype=np.float64)
        self.wind = np.asarray(wind, dtype=np.float64)
        self.drag = float(drag)
        self._rng = np.random.RandomState(seed)
        self._t = 0.0

    def add_emitter(self, emitter):
        self.emitters.append(emitter)

    def _integrate_particle(self, p, dt, t):
        if p.type == "embers":
            p.vel += self._rng.normal(0, 0.2, 3) * dt
            p.vel += self.gravity * 0.3 * dt
            ratio = p.age / p.lifetime
            if ratio < 0.5:
                p.color = np.array([1.0, 0.2 + 1.4 * ratio, 0.0])
            else:
                r2 = (ratio - 0.5) * 2
                p.color = np.array([1.0, 0.9 - 0.3 * r2, 0.6 - 0.4 * r2])
            p.alpha = max(0.0, 1.0 - ratio)
            p.size *= 1.0 + 0.1 * dt
        elif p.type == "sparks":
            p.vel += self.gravity * dt
            p.vel += self.wind * dt
            ratio = p.age / p.lifetime
            p.alpha = max(0.0, 1.0 - ratio)
            p.color = np.array([1.0, 0.8 - 0.4 * ratio, 0.3 - 0.2 * ratio])
        elif p.type == "dust":
            p.vel += self._rng.normal(0, 0.1, 3) * dt
            p.vel *= 1.0 - 0.5 * dt
            ratio = p.age / p.lifetime
            p.alpha = 0.6 * (1.0 - ratio)
        elif p.type == "smoke":
            p.vel += self._rng.normal(0, 0.05, 3) * dt
            p.vel += np.array([0, 0.3, 0]) * dt
            ratio = p.age / p.lifetime
            p.color = np.array([0.3 * (1 - ratio), 0.3 * (1 - ratio), 0.3 * (1 - ratio)])
            p.alpha = 0.5 * (1.0 - ratio)
            p.size *= 1.0 + 0.3 * dt
        elif p.type == "rain":
            p.vel += self.gravity * 0.5 * dt
            p.vel += self.wind * dt
            ratio = p.age / p.lifetime
            p.alpha = 0.8 * (1.0 - ratio)
        elif p.type == "snow":
            p.vel[0] = 0.5 * np.sin(t * 2.0 + p.seed)
            p.vel += self.gravity * 0.1 * dt
            ratio = p.age / p.lifetime
            p.alpha = 1.0 - 0.5 * ratio
        elif p.type == "bubbles":
            p.vel[0] = 0.5 * np.sin(t * 3.0 + p.seed)
            p.vel[2] = 0.3 * np.cos(t * 3.0 + p.seed)
            p.vel += np.array([0, 0.5, 0]) * dt
            ratio = p.age / p.lifetime
            p.alpha = 0.4 * (1.0 - ratio)
            p.size *= 1.0 + 0.05 * dt
        elif p.type == "fireflies":
            p.vel += self._rng.normal(0, 0.5, 3) * dt
            p.vel *= 1.0 - 0.8 * dt
            blink = 0.5 + 0.5 * np.sin(t * 5.0 + p.seed * 3.0)
            p.alpha = blink
            p.color = np.array([1.0, 1.0, 0.3]) * blink
        elif p.type == "debris":
            p.vel += self.gravity * dt
            p.vel += self.wind * dt
            ratio = p.age / p.lifetime
            p.alpha = max(0.0, 1.0 - ratio)
            p.size *= 1.0 - 0.05 * dt
        else:
            p.vel += self.gravity * dt
            p.vel += self.wind * dt
            ratio = p.age / p.lifetime
            p.alpha = max(0.0, 1.0 - ratio)

        if self.drag > 0:
            p.vel *= max(0.0, 1.0 - self.drag * dt)
        p.pos += p.vel * dt
        p.age += dt

    def update(self, dt, t):
        self._t = t
        for emitter in self.emitters:
            new_parts = emitter.update(dt, t)
            if emitter.particle_type == "debris":
                for p in new_parts:
                    angle = self._rng.uniform(0, 2 * np.pi)
                    elev = self._rng.uniform(-0.5, 0.5)
                    speed = self._rng.uniform(3.0, 8.0)
                    p.vel = np.array([
                        speed * np.cos(angle) * np.cos(elev),
                        speed * np.sin(elev),
                        speed * np.sin(angle) * np.cos(elev),
                    ])
            self.particles.extend(new_parts)
        alive = []
        for p in self.particles:
            self._integrate_particle(p, dt, t)
            if p.age < p.lifetime and p.alpha > 0.001:
                alive.append(p)
        self.particles = alive

    def render(self, width, height, camera=None):
        if not self.particles:
            return (
                np.zeros((0, 2), dtype=np.float64),
                np.zeros((0,), dtype=np.float64),
                np.zeros((0, 3), dtype=np.float64),
                np.zeros((0,), dtype=np.float64),
            )
        positions = np.array([p.pos for p in self.particles], dtype=np.float64)
        sizes = np.array([p.size for p in self.particles], dtype=np.float64)
        colors = np.array([p.color for p in self.particles], dtype=np.float64)
        alphas = np.array([p.alpha for p in self.particles], dtype=np.float64)
        if camera is not None and positions.shape[1] == 3:
            projected = self._project(positions, camera, width, height)
        else:
            projected = positions[:, :2].copy()
            projected[:, 0] = (projected[:, 0] + 1.0) * 0.5 * width
            projected[:, 1] = (1.0 - projected[:, 1]) * 0.5 * height
        return projected, sizes, colors, alphas

    @staticmethod
    def _project(positions, camera, width, height):
        eye = np.asarray(camera.get("eye", [0, 0, 5]), dtype=np.float64)
        target = np.asarray(camera.get("target", [0, 0, 0]), dtype=np.float64)
        up = np.asarray(camera.get("up", [0, 1, 0]), dtype=np.float64)
        fov = float(camera.get("fov", 60.0))
        aspect = float(camera.get("aspect", width / max(height, 1)))

        f = target - eye
        f = f / (np.linalg.norm(f) + 1e-9)
        s = np.cross(f, up)
        s = s / (np.linalg.norm(s) + 1e-9)
        u = np.cross(s, f)
        R = np.stack([s, u, -f], axis=0)
        translated = positions - eye
        cam_coords = translated @ R.T
        near = 0.1
        z = cam_coords[:, 2]
        z = np.where(z >= -near, -near - 1e-3, z)
        fov_rad = np.deg2rad(fov)
        f_len = 1.0 / np.tan(fov_rad / 2.0)
        x = cam_coords[:, 0] * f_len / aspect / (-z)
        y = cam_coords[:, 1] * f_len / (-z)
        sx = (x + 1.0) * 0.5 * width
        sy = (1.0 - y) * 0.5 * height
        return np.stack([sx, sy], axis=1)


class ParticleTrail:
    def __init__(self, length=20, fade=1.0) -> None:
        self.length = int(length)
        self.fade = float(fade)
        self.positions: list[np.ndarray] = []
        self.sizes: list[float] = []
        self.colors: list[np.ndarray] = []
        self.alphas: list[float] = []

    def update(self, particle):
        self.positions.append(particle.pos.copy())
        self.sizes.append(particle.size)
        self.colors.append(particle.color.copy())
        self.alphas.append(particle.alpha)
        if len(self.positions) > self.length:
            self.positions.pop(0)
            self.sizes.pop(0)
            self.colors.pop(0)
            self.alphas.pop(0)

    def render(self, width, height, camera=None):
        if not self.positions:
            return (
                np.zeros((0, 2), dtype=np.float64),
                np.zeros((0,), dtype=np.float64),
                np.zeros((0, 3), dtype=np.float64),
                np.zeros((0,), dtype=np.float64),
            )
        positions = np.array(self.positions, dtype=np.float64)
        sizes = np.array(self.sizes, dtype=np.float64)
        colors = np.array(self.colors, dtype=np.float64)
        alphas = np.array(self.alphas, dtype=np.float64)
        n = len(self.positions)
        fade_factors = np.linspace(0.0, 1.0, n) ** self.fade
        alphas = alphas * fade_factors
        sizes = sizes * fade_factors
        if camera is not None and positions.shape[1] == 3:
            projected = ParticleSystemExtended._project(positions, camera, width, height)
        else:
            projected = positions[:, :2].copy()
            projected[:, 0] = (projected[:, 0] + 1.0) * 0.5 * width
            projected[:, 1] = (1.0 - projected[:, 1]) * 0.5 * height
        return projected, sizes, colors, alphas
