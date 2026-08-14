from __future__ import annotations

import numpy as np

from utils.fluid_deform import fluid_deform
from utils.liquid_wire_timeline import build_timeline


def _mesh() -> tuple[np.ndarray, np.ndarray]:
    theta = np.linspace(0, 2 * np.pi, 24)
    phi = np.linspace(0.1, np.pi - 0.1, 12)
    return np.meshgrid(theta, phi)


def _events() -> list:
    return build_timeline(1, 10.0, {"beat_seconds": 0.8, "meter": 4})


def test_deformation_produces_valid_coordinates() -> None:
    th, ph = _mesh()
    profile = {"seed": 1, "fluid_speed": 0.5, "fluid_amp": 0.18}
    dtheta, dphi = fluid_deform(th, ph, 1.0, profile, _events())
    assert dtheta.shape == th.shape
    assert dphi.shape == ph.shape
    assert np.all(np.isfinite(dtheta))
    assert np.all(np.isfinite(dphi))


def test_determinism() -> None:
    th, ph = _mesh()
    profile = {"seed": 1, "fluid_speed": 0.5, "fluid_amp": 0.18}
    events = _events()
    a = fluid_deform(th, ph, 1.0, profile, events)
    b = fluid_deform(th, ph, 1.0, profile, events)
    assert np.allclose(a[0], b[0])
    assert np.allclose(a[1], b[1])


def test_different_time_different_deformation() -> None:
    th, ph = _mesh()
    profile = {"seed": 2, "fluid_speed": 0.5, "fluid_amp": 0.2}
    events = _events()
    a = fluid_deform(th, ph, 4.0, profile, events)
    b = fluid_deform(th, ph, 8.0, profile, events)
    assert not np.allclose(a[0], b[0])


def test_events_change_deformation() -> None:
    th, ph = _mesh()
    profile = {"seed": 3, "fluid_speed": 0.5, "fluid_amp": 0.2}
    with_events = fluid_deform(th, ph, 8.0, profile, _events())
    without_events = fluid_deform(th, ph, 8.0, profile, [])
    assert not np.allclose(with_events[0], without_events[0])
