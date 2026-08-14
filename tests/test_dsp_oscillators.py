from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc

SR = 44100


def _freq_of(signal: np.ndarray, sr: int) -> float:
    """Estimate the dominant frequency of a signal via zero crossings."""
    sign = np.sign(signal)
    crossings = np.where(np.diff(sign) != 0)[0]
    if crossings.size < 2:
        return 0.0
    periods = np.diff(crossings) * 2
    median_period = float(np.median(periods))
    if median_period <= 0:
        return 0.0
    return sr / median_period


def test_sine_length() -> None:
    y = osc.sine(440.0, 0.1, SR)
    assert y.shape == (int(0.1 * SR),)


def test_sine_in_range() -> None:
    y = osc.sine(440.0, 0.5, SR)
    assert y.dtype == np.float64
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_sine_frequency() -> None:
    y = osc.sine(440.0, 1.0, SR)
    f = _freq_of(y, SR)
    assert abs(f - 440.0) < 10.0


def test_sawtooth_in_range() -> None:
    y = osc.sawtooth(220.0, 0.5, SR)
    assert y.dtype == np.float64
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_square_in_range() -> None:
    y = osc.square(220.0, 0.5, SR)
    assert y.dtype == np.float64
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_triangle_in_range() -> None:
    y = osc.triangle(220.0, 0.5, SR)
    assert y.dtype == np.float64
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_pulse_in_range() -> None:
    y = osc.pulse(220.0, 0.5, SR, pulse_width=0.25)
    assert y.dtype == np.float64
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_supersaw_length_and_range() -> None:
    y = osc.supersaw(220.0, 0.3, SR, detune=0.12, voices=7)
    assert y.shape == (int(0.3 * SR),)
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_noise_white_determinism() -> None:
    a = osc.noise_white(0.2, SR, seed=42)
    b = osc.noise_white(0.2, SR, seed=42)
    c = osc.noise_white(0.2, SR, seed=43)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_noise_pink_in_range() -> None:
    y = osc.noise_pink(0.5, SR, seed=1)
    assert y.dtype == np.float64
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_noise_brown_in_range() -> None:
    y = osc.noise_brown(0.5, SR, seed=1)
    assert y.dtype == np.float64
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_fm_length_and_range() -> None:
    y = osc.fm(440.0, 110.0, 0.5, SR, mod_index=2.0)
    assert y.shape == (int(0.5 * SR),)
    assert np.all(np.abs(y) <= 1.0 + 1e-9)


def test_fm_determinism() -> None:
    a = osc.fm(440.0, 110.0, 0.2, SR, mod_index=1.5)
    b = osc.fm(440.0, 110.0, 0.2, SR, mod_index=1.5)
    assert np.array_equal(a, b)


def test_sine_determinism() -> None:
    a = osc.sine(440.0, 0.2, SR, phase=0.5)
    b = osc.sine(440.0, 0.2, SR, phase=0.5)
    assert np.array_equal(a, b)


def test_white_noise_is_white() -> None:
    # White noise should have a roughly flat spectrum: compare low vs high band energy.
    y = osc.noise_white(1.0, SR, seed=7)
    spec = np.abs(np.fft.rfft(y))
    low = spec[: spec.size // 4].mean()
    high = spec[3 * spec.size // 4 :].mean()
    # Allow a generous ratio; white noise is stochastic.
    assert 0.25 < low / high < 4.0
