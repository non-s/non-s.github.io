from __future__ import annotations

import numpy as np

from utils.organic_growth import OrganicGrowth, render_branches


def test_grow_returns_branches() -> None:
    growth = OrganicGrowth(seed=1, iterations=3)
    branches = growth.grow()
    assert len(branches) > 0
    for branch in branches:
        assert len(branch.start) == 2
        assert len(branch.end) == 2
        assert branch.thickness > 0.0


def test_more_iterations_more_branches() -> None:
    small = OrganicGrowth(seed=1, iterations=2).grow()
    large = OrganicGrowth(seed=1, iterations=5).grow()
    assert len(large) > len(small)


def test_determinism() -> None:
    a = OrganicGrowth(seed=42, iterations=4).grow()
    b = OrganicGrowth(seed=42, iterations=4).grow()
    assert a == b


def test_different_seed_different_branches() -> None:
    a = OrganicGrowth(seed=1, iterations=3).grow()
    b = OrganicGrowth(seed=2, iterations=3).grow()
    assert a != b


def test_render_branches_maps_to_screen() -> None:
    branches = OrganicGrowth(seed=1, iterations=3).grow()
    sx, sy = render_branches(branches, t=0.0, profile={}, width=1280, height=720)
    assert sx.shape == (len(branches) * 2,)
    assert sy.shape == (len(branches) * 2,)
    assert np.all(sx >= 0) and np.all(sx <= 1280)
    assert np.all(sy >= 0) and np.all(sy <= 720)


def test_render_branches_empty() -> None:
    sx, sy = render_branches([], t=0.0, profile={}, width=1280, height=720)
    assert sx.shape == (0,)
    assert sy.shape == (0,)
