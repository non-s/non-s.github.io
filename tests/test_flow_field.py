from __future__ import annotations

import math

import numpy as np

from utils.flow_field import FlowField, render_flow_particles


def test_field_at_returns_valid_vectors() -> None:
    field = FlowField(seed=42, width=640, height=480, scale=120.0)
    vx, vy = field.field_at(100.0, 100.0, 0.5)
    assert isinstance(vx, float)
    assert isinstance(vy, float)
    assert math.isfinite(vx)
    assert math.isfinite(vy)
    # Vectors are bounded since each octave is amp-weighted noise in ~[-1,1].
    assert -2.0 <= vx <= 2.0
    assert -2.0 <= vy <= 2.0


def test_field_varies_in_space_and_time() -> None:
    field = FlowField(seed=7, width=320, height=320)
    a = field.field_at(10.0, 10.0, 0.0)
    b = field.field_at(200.0, 150.0, 0.0)
    c = field.field_at(10.0, 10.0, 5.0)
    assert a != b
    assert a != c


def test_render_flow_particles_returns_valid_trails() -> None:
    field = FlowField(seed=99, width=512, height=512)
    trails = render_flow_particles(field, t=1.0, num_particles=12, trail_length=8)
    assert len(trails) == 12
    for trail in trails:
        assert len(trail) == 8
        for x, y in trail:
            assert 0.0 <= x <= field.width
            assert 0.0 <= y <= field.height


def test_determinism_same_seed_same_output() -> None:
    field_a = FlowField(seed=123, width=256, height=256)
    field_b = FlowField(seed=123, width=256, height=256)
    assert field_a.field_at(50.0, 50.0, 0.3) == field_b.field_at(50.0, 50.0, 0.3)
    trails_a = render_flow_particles(field_a, t=0.5, num_particles=5, trail_length=4)
    trails_b = render_flow_particles(field_b, t=0.5, num_particles=5, trail_length=4)
    assert trails_a == trails_b


def test_different_seed_different_output() -> None:
    field_a = FlowField(seed=1, width=256, height=256)
    field_b = FlowField(seed=2, width=256, height=256)
    assert field_a.field_at(50.0, 50.0, 0.3) != field_b.field_at(50.0, 50.0, 0.3)


def test_vectorized_matches_scalar() -> None:
    field = FlowField(seed=5, width=300, height=300)
    xs = np.array([10.0, 100.0, 200.0])
    ys = np.array([20.0, 80.0, 150.0])
    vx_v, vy_v = field._field_v(xs, ys, 0.4)
    for i in range(len(xs)):
        sx, sy = field.field_at(float(xs[i]), float(ys[i]), 0.4)
        assert abs(sx - vx_v[i]) < 1e-9
        assert abs(sy - vy_v[i]) < 1e-9
