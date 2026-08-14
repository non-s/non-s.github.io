from __future__ import annotations

import numpy as np

from utils.dsp.envelopes import ADSR, LFO, MultiStageEnv
from utils.dsp.oscillators import sine

SR = 44100


def test_adsr_length() -> None:
    env = ADSR(0.01, 0.05, 0.7, 0.1)
    y = env.render(0.5, SR)
    assert y.shape == (int(0.5 * SR),)


def test_adsr_starts_at_zero() -> None:
    env = ADSR(0.01, 0.05, 0.7, 0.1)
    y = env.render(0.5, SR)
    assert y[0] == 0.0


def test_adsr_peak_is_one() -> None:
    env = ADSR(0.01, 0.05, 0.7, 0.1)
    y = env.render(0.5, SR)
    assert np.max(y) <= 1.0 + 1e-9
    assert np.max(y) >= 0.99


def test_adsr_range() -> None:
    env = ADSR(0.01, 0.05, 0.7, 0.1)
    y = env.render(0.5, SR)
    assert np.all(y >= -1e-9) and np.all(y <= 1.0 + 1e-9)


def test_adsr_release_with_release_start() -> None:
    env = ADSR(0.01, 0.05, 0.7, 0.1)
    y = env.render_with_release(0.5, 0.3, SR)
    assert y.shape == (int(0.5 * SR),)
    # After release the envelope should decay to (near) zero.
    assert y[-1] < 0.05


def test_adsr_determinism() -> None:
    env = ADSR(0.01, 0.05, 0.7, 0.1)
    a = env.render(0.3, SR)
    b = env.render(0.3, SR)
    assert np.array_equal(a, b)


def test_multistage_length() -> None:
    env = MultiStageEnv([(1.0, 0.05), (0.5, 0.1), (0.0, 0.2)])
    y = env.render(0.5, SR)
    assert y.shape == (int(0.5 * SR),)


def test_multistage_range() -> None:
    env = MultiStageEnv([(1.0, 0.05), (0.5, 0.1), (0.0, 0.2)])
    y = env.render(0.5, SR)
    assert np.all(y >= -1e-9) and np.all(y <= 1.0 + 1e-9)


def test_multistage_reaches_targets() -> None:
    env = MultiStageEnv([(1.0, 0.05), (0.0, 0.05)])
    y = env.render(0.2, SR)
    # After 0.1s of segments + hold, value should be at the last target (0).
    assert abs(y[-1]) < 1e-6


def test_lfo_length() -> None:
    lfo = LFO(5.0, "sine", 0.5, SR, 0.5)
    y = lfo.render()
    assert y.shape == (int(0.5 * SR),)


def test_lfo_range() -> None:
    for shape in ("sine", "triangle", "saw", "square", "random"):
        lfo = LFO(5.0, shape, 0.5, SR, 0.5)
        y = lfo.render()
        assert np.all(np.abs(y) <= 0.5 + 1e-6), f"shape {shape} out of range"


def test_lfo_apply_amplitude_modulates() -> None:
    x = sine(440.0, 0.5, SR)
    lfo = LFO(5.0, "sine", 0.5, SR, 0.5)
    y = lfo.apply_to(x, target="amplitude")
    assert y.shape == x.shape
    # Modulated signal should differ from the original.
    assert not np.allclose(y, x)


def test_lfo_apply_pitch_returns_signal() -> None:
    x = sine(440.0, 0.5, SR)
    lfo = LFO(5.0, "sine", 0.5, SR, 0.5)
    y = lfo.apply_to(x, target="pitch")
    assert y.shape == x.shape
    assert np.all(np.isfinite(y))


def test_lfo_determinism() -> None:
    a = LFO(5.0, "sine", 0.5, SR, 0.5).render()
    b = LFO(5.0, "sine", 0.5, SR, 0.5).render()
    assert np.array_equal(a, b)
