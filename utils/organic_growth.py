"""Stochastic L-system / coral branching growth.

Each ``grow()`` run expands a turtle from a root using per-seed stochastic
production rules: branches split into 2-3 sub-branches with angle and length
variation. Determinism is preserved by a single numpy Generator seeded by the
``seed`` argument so identical seeds produce identical branch sets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Branch:
    start: tuple[float, float]
    end: tuple[float, float]
    thickness: float


class OrganicGrowth:
    """Stochastic L-system growth with coral-like branching.

    Parameters
    ----------
    seed:
        Deterministic seed for the stochastic productions.
    iterations:
        Number of branching generations to expand.
    angle_range:
        Half-angle of the spread between sibling branches, in radians.
    length_decay:
        Factor applied to branch length each generation (0, 1).
    """

    def __init__(
        self, seed: int, iterations: int, angle_range: float = 0.55, length_decay: float = 0.72
    ) -> None:
        self.seed = int(seed)
        self.iterations = max(1, int(iterations))
        self.angle_range = float(angle_range)
        self.length_decay = float(length_decay)
        self._rng = np.random.default_rng(self.seed)

    def grow(self) -> list[Branch]:
        rng = self._rng
        branches: list[Branch] = []
        # The turtle starts at the bottom-centre pointing straight up.
        root = (0.0, 0.0)
        root_angle = math.pi * 0.5
        root_length = 1.0
        root_thickness = 1.0
        queue: list[tuple[tuple[float, float], float, float, float, int]] = [
            (root, root_angle, root_length, root_thickness, 0)
        ]
        while queue:
            pos, angle, length, thickness, depth = queue.pop(0)
            x, y = pos
            end_x = x + math.cos(angle) * length
            end_y = y + math.sin(angle) * length
            branches.append(Branch(start=(x, y), end=(end_x, end_y), thickness=thickness))
            if depth >= self.iterations:
                continue
            n_children = int(rng.choice((2, 2, 3)))
            new_length = length * self.length_decay
            new_thickness = thickness * 0.72
            spread = self.angle_range
            for child in range(n_children):
                if n_children == 1:
                    offset = float(rng.uniform(-spread * 0.5, spread * 0.5))
                else:
                    t = (child / (n_children - 1)) * 2.0 - 1.0  # -1..1
                    offset = t * spread + float(rng.uniform(-0.12, 0.12))
                new_angle = angle + offset
                queue.append(((end_x, end_y), new_angle, new_length, new_thickness, depth + 1))
        return branches


def render_branches(
    branches: list[Branch], t: float, profile: dict, width: int, height: int
) -> tuple[np.ndarray, np.ndarray]:
    """Map branch start/end points to screen coordinates (sx, sy) arrays.

    Returns two arrays of shape (len(branches)*2,): x then y endpoints interleaved
    so a renderer can draw line segments with a single polyline batch.
    """
    if not branches:
        return np.zeros((0,), dtype=np.float64), np.zeros((0,), dtype=np.float64)
    xs_all: list[float] = []
    ys_all: list[float] = []
    for branch in branches:
        xs_all.extend((branch.start[0], branch.end[0]))
        ys_all.extend((branch.start[1], branch.end[1]))
    min_x = min(xs_all)
    max_x = max(xs_all)
    min_y = min(ys_all)
    max_y = max(ys_all)
    span_x = max(1e-6, max_x - min_x)
    span_y = max(1e-6, max_y - min_y)
    margin = 0.12
    draw_w = width * (1.0 - 2.0 * margin)
    draw_h = height * (1.0 - 2.0 * margin)
    sx_list: list[float] = []
    sy_list: list[float] = []
    # Per-branch sway indexed by depth so tips move more than the base.
    for bi, branch in enumerate(branches):
        depth_frac = bi / max(1, len(branches) - 1)
        sway = 0.18 * math.sin(t * 1.1 + bi * 0.4) * (0.4 + depth_frac)
        sway_y = 0.12 * math.cos(t * 0.9 + bi * 0.3) * (0.4 + depth_frac)
        for px, py in (branch.start, branch.end):
            nx = (px - min_x) / span_x
            ny = (py - min_y) / span_y
            sx_list.append(margin * width + nx * draw_w + sway * width * 0.06)
            sy_list.append(height - (margin * height + ny * draw_h) + sway_y * height * 0.04)
    return np.asarray(sx_list, dtype=np.float64), np.asarray(sy_list, dtype=np.float64)
