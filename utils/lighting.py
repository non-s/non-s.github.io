"""3D lighting model with Phong shading, Fresnel and approximate AO.

Pure-numpy implementation supporting point, directional and spot lights,
vectorized shading over many points, Fresnel rim term and a cheap
ambient-occlusion approximation driven by an external occlusion field.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Light:
    """Base light: position, rgb color (0-1), intensity and type tag."""

    position: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    color: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=np.float64))
    intensity: float = 1.0
    type: str = "point"


@dataclass
class PointLight(Light):
    """Point light with inverse-distance attenuation."""

    attenuation: float = 0.5
    type: str = "point"

    def __init__(self, position, color, intensity: float, attenuation: float = 0.5) -> None:
        super().__init__(position=np.asarray(position, dtype=np.float64),
                         color=np.asarray(color, dtype=np.float64),
                         intensity=float(intensity), type="point")
        self.attenuation = float(attenuation)


@dataclass
class DirectionalLight(Light):
    """Directional light: direction vector instead of position."""

    direction: np.ndarray = field(default_factory=lambda: np.array([0.0, -1.0, 0.0], dtype=np.float64))
    type: str = "directional"

    def __init__(self, direction, color, intensity: float) -> None:
        d = np.asarray(direction, dtype=np.float64)
        n = np.linalg.norm(d) + 1e-12
        super().__init__(position=np.zeros(3, dtype=np.float64),
                         color=np.asarray(color, dtype=np.float64),
                         intensity=float(intensity), type="directional")
        self.direction = d / n


@dataclass
class SpotLight(Light):
    """Spot light with cone angle and penumbra softness."""

    target: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    cone_angle: float = np.radians(30.0)
    penumbra: float = 0.1
    type: str = "spot"

    def __init__(self, position, target, color, intensity: float,
                 cone_angle: float, penumbra: float = 0.1) -> None:
        super().__init__(position=np.asarray(position, dtype=np.float64),
                         color=np.asarray(color, dtype=np.float64),
                         intensity=float(intensity), type="spot")
        self.target = np.asarray(target, dtype=np.float64)
        self.cone_angle = float(cone_angle)
        self.penumbra = float(penumbra)


def _spot_factor(light: SpotLight, points: np.ndarray, L: np.ndarray) -> np.ndarray:
    """Per-point spot cone falloff in [0,1] for a SpotLight."""
    axis = light.target - light.position
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    cos_cone = np.cos(light.cone_angle)
    penumbra = max(1e-6, light.penumbra)
    cos_theta = L @ axis
    penumbra_cos = np.cos(light.cone_angle + penumbra)
    falloff = np.clip((cos_theta - penumbra_cos) / (cos_cone - penumbra_cos + 1e-12), 0.0, 1.0)
    return np.where(cos_theta >= cos_cone, 1.0, falloff)


def shade_point(point, normal, lights, ambient: float = 0.1, view_dir=None) -> np.ndarray:
    """Phong shading (diffuse + specular) for a single point. Returns rgb in [0,1]."""
    p = np.asarray(point, dtype=np.float64)
    n = np.asarray(normal, dtype=np.float64)
    n = n / (np.linalg.norm(n) + 1e-12)
    if view_dir is None:
        view_dir = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    v = np.asarray(view_dir, dtype=np.float64)
    v = v / (np.linalg.norm(v) + 1e-12)
    rgb = np.zeros(3, dtype=np.float64)
    for light in lights:
        if light.type == "directional":
            L = -light.direction
            atten = 1.0
            spot = 1.0
        else:
            to_light = light.position - p
            dist = np.linalg.norm(to_light) + 1e-12
            L = to_light / dist
            atten = float(1.0 / (1.0 + getattr(light, "attenuation", 0.5) * dist * dist))
            spot = 1.0
            if light.type == "spot":
                spot = float(_spot_factor(light, p.reshape(1, 3), L.reshape(1, 3))[0])
        diffuse = max(0.0, np.dot(n, L))
        h = (L + v)
        h = h / (np.linalg.norm(h) + 1e-12)
        specular = max(0.0, np.dot(n, h)) ** 32.0
        rgb += light.color * light.intensity * atten * spot * (diffuse + 0.3 * specular)
    rgb += ambient
    return np.clip(rgb, 0.0, 1.0)


def shade_points(points, normals, lights, ambient: float = 0.1, view_dir=None) -> np.ndarray:
    """Vectorized Phong shading for (N,3) points/normals. Returns (N,3) rgb."""
    pts = np.asarray(points, dtype=np.float64)
    nrms = np.asarray(normals, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 3)
    if nrms.ndim == 1:
        nrms = nrms.reshape(1, 3)
    n = pts.shape[0]
    nrms = nrms / (np.linalg.norm(nrms, axis=1, keepdims=True) + 1e-12)
    if view_dir is None:
        view_dir = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    v = np.asarray(view_dir, dtype=np.float64)
    v = v / (np.linalg.norm(v) + 1e-12)
    rgb = np.zeros((n, 3), dtype=np.float64)
    for light in lights:
        if light.type == "directional":
            L = np.broadcast_to(-light.direction, (n, 3)).copy()
            atten = np.ones(n, dtype=np.float64)
            spot = np.ones(n, dtype=np.float64)
        else:
            to_light = light.position[None, :] - pts
            dist = np.linalg.norm(to_light, axis=1) + 1e-12
            L = to_light / dist[:, None]
            atten = 1.0 / (1.0 + getattr(light, "attenuation", 0.5) * dist * dist)
            spot = np.ones(n, dtype=np.float64)
            if light.type == "spot":
                spot = _spot_factor(light, pts, L)
        ndotl = np.clip(np.sum(nrms * L, axis=1), 0.0, None)
        h = L + v[None, :]
        h = h / (np.linalg.norm(h, axis=1, keepdims=True) + 1e-12)
        ndoth = np.clip(np.sum(nrms * h, axis=1), 0.0, None) ** 32.0
        contrib = (ndotl[:, None] + 0.3 * ndoth[:, None]) * (light.color[None, :] * light.intensity)
        rgb += contrib * (atten * spot)[:, None]
    rgb += ambient
    return np.clip(rgb, 0.0, 1.0)


def fresnel(view_dir, normal, power: float = 3.0) -> float:
    """Schlick-style Fresnel term for rim/edge lighting. Returns float in [0,1]."""
    v = np.asarray(view_dir, dtype=np.float64)
    n = np.asarray(normal, dtype=np.float64)
    v = v / (np.linalg.norm(v) + 1e-12)
    n = n / (np.linalg.norm(n) + 1e-12)
    cos_theta = np.clip(np.dot(v, n), 0.0, 1.0)
    return float((1.0 - cos_theta) ** power)


def ambient_occlusion_approx(points, normals, occlusion_field) -> np.ndarray:
    """Approximate AO per point given a callable occlusion_field(point)->float.

    The occlusion field is expected to return a scalar in [0,1] where 1 means
    fully occluded. The hemispheric sample integrates a few directions about
    the normal, weighted by the field's occlusion at offset probe positions.
    """
    pts = np.asarray(points, dtype=np.float64)
    nrms = np.asarray(normals, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 3)
    if nrms.ndim == 1:
        nrms = nrms.reshape(1, 3)
    n = pts.shape[0]
    nrms = nrms / (np.linalg.norm(nrms, axis=1, keepdims=True) + 1e-12)
    directions = np.array([
        [1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.7071, 0.7071, 0.0],
        [-0.7071, 0.7071, 0.0],
        [0.7071, -0.7071, 0.0],
        [-0.7071, -0.7071, 0.0],
    ], dtype=np.float64)
    probe_radius = 0.05
    ao = np.zeros(n, dtype=np.float64)
    for d in directions:
        cos_a = nrms @ d
        keep = cos_a > 0.0
        if not np.any(keep):
            continue
        probes = pts[keep] + d[None, :] * probe_radius
        occ = np.array([occlusion_field(probes[i]) for i in range(probes.shape[0])], dtype=np.float64)
        ao[keep] += np.clip(occ, 0.0, 1.0) * cos_a[keep]
    ao = 1.0 - (ao / float(len(directions)))
    return np.clip(ao, 0.0, 1.0)
