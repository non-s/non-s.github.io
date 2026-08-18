
import numpy as np


def crossfade(points_a: np.ndarray, points_b: np.ndarray, alpha: float) -> np.ndarray:
    a = np.asarray(points_a, dtype=np.float64)
    b = np.asarray(points_b, dtype=np.float64)
    n = max(len(a), len(b))
    if len(a) < n:
        idx = np.random.RandomState(0).choice(len(a), size=n, replace=True)
        a = a[idx]
    if len(b) < n:
        idx = np.random.RandomState(0).choice(len(b), size=n, replace=True)
        b = b[idx]
    return (1.0 - alpha) * a + alpha * b


def morph_with_correspondence(
    points_a: np.ndarray,
    points_b: np.ndarray,
    alpha: float,
    method: str = "linear",
) -> np.ndarray:
    a = np.asarray(points_a, dtype=np.float64)
    b = np.asarray(points_b, dtype=np.float64)
    n = min(len(a), len(b))
    a_used, b_used = a[:n], b[:n]
    if len(a) > len(b):
        tree_b = b_used
        dists = np.linalg.norm(a[n:, None, :] - tree_b[None, :, :], axis=2)
        nn = np.argmin(dists, axis=1)
        a_extra = a[n:]
        b_extra = tree_b[nn]
        a_used = np.concatenate([a_used, a_extra], axis=0)
        b_used = np.concatenate([b_used, b_extra], axis=0)
    elif len(b) > len(a):
        tree_a = a_used
        dists = np.linalg.norm(b[n:, None, :] - tree_a[None, :, :], axis=2)
        nn = np.argmin(dists, axis=1)
        a_extra = tree_a[nn]
        b_extra = b[n:]
        a_used = np.concatenate([a_used, a_extra], axis=0)
        b_used = np.concatenate([b_used, b_extra], axis=0)

    if method == "spherical":
        norm_a = np.linalg.norm(a_used, axis=1, keepdims=True)
        norm_b = np.linalg.norm(b_used, axis=1, keepdims=True)
        norm_a = np.where(norm_a == 0, 1e-9, norm_a)
        norm_b = np.where(norm_b == 0, 1e-9, norm_b)
        dir_a = a_used / norm_a
        dir_b = b_used / norm_b
        dot = np.sum(dir_a * dir_b, axis=1, keepdims=True)
        dot = np.clip(dot, -1.0, 1.0)
        omega = np.arccos(dot)
        sin_omega = np.sin(omega)
        sin_omega = np.where(sin_omega == 0, 1e-9, sin_omega)
        sa = np.sin((1.0 - alpha) * omega) / sin_omega
        sb = np.sin(alpha * omega) / sin_omega
        direction = sa * dir_a + sb * dir_b
        magnitude = (1.0 - alpha) * norm_a + alpha * norm_b
        return direction * magnitude
    return (1.0 - alpha) * a_used + alpha * b_used


def dissolve(
    points_a: np.ndarray,
    points_b: np.ndarray,
    alpha: float,
    noise_threshold: float = 0.5,
    seed: int = 0,
) -> np.ndarray:
    a = np.asarray(points_a, dtype=np.float64)
    b = np.asarray(points_b, dtype=np.float64)
    n = max(len(a), len(b))
    rng = np.random.RandomState(seed)
    if len(a) < n:
        idx = rng.choice(len(a), size=n, replace=True)
        a = a[idx]
    if len(b) < n:
        idx = rng.choice(len(b), size=n, replace=True)
        b = b[idx]
    noise = rng.rand(n)
    mask_a = noise > alpha - noise_threshold
    result = np.where(mask_a[:, None], a, b)
    return result


def wipe_transition(
    points_a: np.ndarray,
    points_b: np.ndarray,
    alpha: float,
    direction: tuple | np.ndarray = (1, 0, 0),
) -> np.ndarray:
    a = np.asarray(points_a, dtype=np.float64)
    b = np.asarray(points_b, dtype=np.float64)
    direction = np.asarray(direction, dtype=np.float64)
    norm = np.linalg.norm(direction)
    if norm == 0:
        return a
    direction = direction / norm

    all_points = np.concatenate([a, b], axis=0)
    projections = all_points @ direction
    pmin, pmax = projections.min(), projections.max()
    prange = pmax - pmin
    if prange == 0:
        return (1.0 - alpha) * a + alpha * b
    threshold = pmin + alpha * prange
    labels = np.concatenate([np.zeros(len(a)), np.ones(len(b))])
    use_b = (projections <= threshold) & (labels == 1)
    use_a = (projections > threshold) & (labels == 0)
    mask = use_b | use_a
    return all_points[mask]


def glitch_transition(
    points_a: np.ndarray,
    points_b: np.ndarray,
    alpha: float,
    seed: int = 0,
    block_size: float = 0.3,
) -> np.ndarray:
    a = np.asarray(points_a, dtype=np.float64)
    b = np.asarray(points_b, dtype=np.float64)
    n = max(len(a), len(b))
    rng = np.random.RandomState(seed)
    if len(a) < n:
        idx = rng.choice(len(a), size=n, replace=True)
        a = a[idx]
    if len(b) < n:
        idx = rng.choice(len(b), size=n, replace=True)
        b = b[idx]
    mins = np.minimum(a.min(axis=0), b.min(axis=0))
    maxs = np.maximum(a.max(axis=0), b.max(axis=0))
    span = np.where(maxs - mins == 0, 1e-9, maxs - mins)
    cells = ((a - mins) / span * (1.0 / block_size)).astype(int)
    cell_ids = cells[:, 0] * 73856093 ^ cells[:, 1] * 19349663 ^ cells[:, 2] * 83492791
    unique_cells = np.unique(cell_ids)
    rng2 = np.random.RandomState(seed + 1)
    cell_alpha = rng2.rand(len(unique_cells))
    cell_map = dict(zip(unique_cells.tolist(), cell_alpha.tolist(), strict=True))
    point_alpha = np.array([cell_map[c] for c in cell_ids.tolist()])
    mask_b = point_alpha < alpha
    result = np.where(mask_b[:, None], b, a)
    return result


def match_cut(
    points_a: np.ndarray,
    points_b: np.ndarray,
    alpha: float,
    center: tuple | np.ndarray = (0, 0, 0),
    radius: float = 1.0,
) -> np.ndarray:
    a = np.asarray(points_a, dtype=np.float64)
    b = np.asarray(points_b, dtype=np.float64)
    center = np.asarray(center, dtype=np.float64)
    n = max(len(a), len(b))
    rng = np.random.RandomState(0)
    if len(a) < n:
        idx = rng.choice(len(a), size=n, replace=True)
        a = a[idx]
    if len(b) < n:
        idx = rng.choice(len(b), size=n, replace=True)
        b = b[idx]
    dists = np.linalg.norm(a - center, axis=1)
    max_dist = dists.max() if dists.size > 0 else radius
    effective_radius = max(radius, max_dist)
    normalized = dists / effective_radius
    mask_b = normalized < alpha
    result = np.where(mask_b[:, None], b, a)
    return result


class SceneTransition:
    def __init__(self) -> None:
        self.scenes: list = []
        self._time = 0.0

    def add_scene(self, points: np.ndarray, duration: float) -> None:
        points = np.asarray(points, dtype=np.float64)
        self.scenes.append({"points": points, "duration": float(duration)})

    def render(self, t: float) -> np.ndarray:
        if not self.scenes:
            return np.zeros((0, 3), dtype=np.float64)
        if len(self.scenes) == 1:
            return self.scenes[0]["points"]
        cumulative = np.cumsum([s["duration"] for s in self.scenes])
        if t <= cumulative[0]:
            return self.scenes[0]["points"]
        if t >= cumulative[-1]:
            return self.scenes[-1]["points"]
        idx = int(np.searchsorted(cumulative, t))
        if idx <= 0:
            return self.scenes[0]["points"]
        prev_end = cumulative[idx - 1]
        local_t = (t - prev_end) / self.scenes[idx]["duration"]
        local_t = float(np.clip(local_t, 0.0, 1.0))
        return crossfade(self.scenes[idx - 1]["points"], self.scenes[idx]["points"], local_t)
