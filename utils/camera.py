"""Virtual 3D camera with perspective projection and Bezier path animation.

Provides a pure-numpy camera with look-at view matrices, perspective
projection (scalar and vectorized), keyframed cubic-Bezier camera paths
and procedural multi-octave sinusoidal camera shake. No external deps.
"""

from __future__ import annotations

import numpy as np


def look_at(eye, target, up) -> np.ndarray:
    """Build a 4x4 view (world-to-camera) matrix from eye/target/up vectors."""
    eye = np.asarray(eye, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    up = np.asarray(up, dtype=np.float64)
    f = target - eye
    f = f / (np.linalg.norm(f) + 1e-12)
    s = np.cross(f, up)
    s = s / (np.linalg.norm(s) + 1e-12)
    u = np.cross(s, f)
    M = np.eye(4, dtype=np.float64)
    M[0, :3] = s
    M[1, :3] = u
    M[2, :3] = -f
    M[0, 3] = -np.dot(s, eye)
    M[1, 3] = -np.dot(u, eye)
    M[2, 3] = np.dot(f, eye)
    return M


def perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    """Build a 4x4 perspective projection matrix (OpenGL convention, NDC z in [-1,1])."""
    fov_rad = np.radians(float(fov_deg))
    f = 1.0 / np.tan(fov_rad * 0.5)
    nf = 1.0 / (near - far)
    M = np.zeros((4, 4), dtype=np.float64)
    M[0, 0] = f / aspect
    M[1, 1] = f
    M[2, 2] = (far + near) * nf
    M[2, 3] = 2.0 * far * near * nf
    M[3, 2] = -1.0
    return M


def project_point(point_3d, camera: Camera, width: int, height: int):
    """Project a single 3D point to screen space. Returns (sx, sy, depth)."""
    p = np.asarray(point_3d, dtype=np.float64)
    view = camera.view_matrix()
    proj = camera.projection_matrix(float(width) / float(height))
    ph = np.array([p[0], p[1], p[2], 1.0], dtype=np.float64)
    cam = view @ ph
    clip = proj @ cam
    w = clip[3]
    if abs(w) < 1e-12:
        w = 1e-12
    ndc = clip[:3] / w
    sx = (ndc[0] * 0.5 + 0.5) * width
    sy = (1.0 - (ndc[1] * 0.5 + 0.5)) * height
    depth = cam[2]
    return float(sx), float(sy), float(depth)


def project_points(points_3d_array, camera: Camera, width: int, height: int):
    """Vectorized projection of (N,3) points. Returns (sx[N], sy[N], depth[N])."""
    pts = np.asarray(points_3d_array, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 3)
    n = pts.shape[0]
    view = camera.view_matrix()
    aspect = float(width) / float(height)
    proj = camera.projection_matrix(aspect)
    homog = np.empty((n, 4), dtype=np.float64)
    homog[:, :3] = pts
    homog[:, 3] = 1.0
    cam = (view @ homog.T).T
    clip = (proj @ cam.T).T
    w = clip[:, 3]
    w_safe = np.where(np.abs(w) < 1e-12, 1e-12, w)
    ndc = clip[:, :3] / w_safe[:, None]
    sx = (ndc[:, 0] * 0.5 + 0.5) * width
    sy = (1.0 - (ndc[:, 1] * 0.5 + 0.5)) * height
    depth = cam[:, 2]
    return sx, sy, depth


class Camera:
    """Pinhole perspective camera with position, target, up, fov and clip planes."""

    def __init__(
        self,
        position=(0.0, 0.0, 5.0),
        target=(0.0, 0.0, 0.0),
        up=(0.0, 1.0, 0.0),
        fov: float = 60.0,
        near: float = 0.1,
        far: float = 1000.0,
    ) -> None:
        self.position = np.asarray(position, dtype=np.float64)
        self.target = np.asarray(target, dtype=np.float64)
        self.up = np.asarray(up, dtype=np.float64)
        self.fov = float(fov)
        self.near = float(near)
        self.far = float(far)

    def view_matrix(self) -> np.ndarray:
        return look_at(self.position, self.target, self.up)

    def projection_matrix(self, aspect: float) -> np.ndarray:
        return perspective(self.fov, aspect, self.near, self.far)

    def look_at(self, eye, target, up=None) -> None:
        self.position = np.asarray(eye, dtype=np.float64)
        self.target = np.asarray(target, dtype=np.float64)
        if up is not None:
            self.up = np.asarray(up, dtype=np.float64)


def _cubic_bezier(p0, p1, p2, p3, t):
    """Evaluate cubic Bezier at t given 4 control points (any dimension)."""
    u = 1.0 - t
    return (u * u * u) * p0 + (3.0 * u * u * t) * p1 + (3.0 * u * t * t) * p2 + (t * t * t) * p3


def _catmull_to_bezier(p0, p1, p2, p3):
    """Convert 4 Catmull-Rom points to cubic Bezier control points (smooth spline)."""
    b0 = p1
    b1 = p1 + (p2 - p0) / 6.0
    b2 = p2 - (p3 - p1) / 6.0
    b3 = p2
    return b0, b1, b2, b3


class CameraPath:
    """Keyframed camera path using Catmull-Rom splines sampled as cubic Bezier.

    Each keyframe stores (time, eye, target, fov). Positions/targets/fov are
    interpolated independently via the same spline so motion stays smooth and
    C1-continuous through the keyframes.
    """

    def __init__(self) -> None:
        self.times: list[float] = []
        self.eyes: list[np.ndarray] = []
        self.targets: list[np.ndarray] = []
        self.fovs: list[float] = []

    def add_keyframe(self, time: float, eye, target, fov: float) -> None:
        self.times.append(float(time))
        self.eyes.append(np.asarray(eye, dtype=np.float64))
        self.targets.append(np.asarray(target, dtype=np.float64))
        self.fovs.append(float(fov))

    def _sample_channel(self, times, values, t):
        n = len(times)
        if n == 0:
            raise ValueError("CameraPath has no keyframes.")
        if n == 1:
            return np.array(values[0], dtype=np.float64)
        if t <= times[0]:
            return np.array(values[0], dtype=np.float64)
        if t >= times[-1]:
            return np.array(values[-1], dtype=np.float64)
        seg = np.searchsorted(times, t) - 1
        seg = max(0, min(seg, n - 2))
        t0, t1 = times[seg], times[seg + 1]
        lt = (t - t0) / (t1 - t0 + 1e-12)
        p0 = values[max(0, seg - 1)]
        p1 = values[seg]
        p2 = values[seg + 1]
        p3 = values[min(n - 1, seg + 2)]
        b0, b1, b2, b3 = _catmull_to_bezier(p0, p1, p2, p3)
        return _cubic_bezier(b0, b1, b2, b3, lt)

    def sample(self, t: float):
        """Return (eye, target, fov) interpolated at time t via Catmull-Rom Bezier."""
        times = self.times
        if len(times) == 0:
            raise ValueError("CameraPath has no keyframes.")
        eye = self._sample_channel(times, self.eyes, t)
        target = self._sample_channel(times, self.targets, t)
        fov = self._sample_channel(times, self.fovs, t)
        return eye, target, float(fov)


def procedural_shake(t: float, freq: float = 2.0, amplitude: float = 0.02, seed: int = 0) -> tuple[float, float]:
    """Multi-octave sinusoidal camera shake. Returns (dx, dy) offsets.

    Sums several sine octaves with deterministic phase offsets derived from
    ``seed`` so motion is smooth, periodic-ish and reproducible.
    """
    octaves = 4
    dx = 0.0
    dy = 0.0
    for k in range(octaves):
        fk = freq * (2 ** k)
        ak = amplitude * (0.5 ** k)
        phase_x = (seed * 0.913 + k * 1.731) * 2.0 * np.pi
        phase_y = (seed * 0.727 + k * 2.917) * 2.0 * np.pi
        dx += ak * np.sin(fk * t + phase_x)
        dy += ak * np.cos(fk * t + phase_y)
    norm = 1.0 / (1.0 - 0.5 ** octaves)
    return float(dx * norm * 0.5), float(dy * norm * 0.5)
