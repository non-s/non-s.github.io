from __future__ import annotations

import numpy as np

from utils.dsp.oscillators import noise_white, sine
from utils.dsp.reverb import Freeverb, PlateReverb

SR = 44100


def test_freeverb_length_mono() -> None:
    x = sine(440.0, 0.5, SR) * 0.5
    rv = Freeverb(sample_rate=SR)
    y = rv.process(x)
    assert y.shape == x.shape


def test_freeverb_length_stereo() -> None:
    x = np.stack([sine(440.0, 0.5, SR) * 0.5, sine(442.0, 0.5, SR) * 0.5], axis=1)
    rv = Freeverb(sample_rate=SR)
    y = rv.process(x)
    assert y.shape == x.shape


def test_freeverb_adds_energy() -> None:
    # An impulse should produce a decaying tail longer than the input.
    x = np.zeros(int(0.2 * SR), dtype=np.float64)
    x[0] = 1.0
    rv = Freeverb(room_size=0.8, wet=1.0, dry=0.0, sample_rate=SR)
    y = rv.process(x)
    # Tail energy after the input ends should be non-zero.
    tail = y[int(0.05 * SR) :]
    assert np.max(np.abs(tail)) > 1e-6


def test_freeverb_determinism() -> None:
    x = sine(440.0, 0.3, SR) * 0.5
    a = Freeverb(sample_rate=SR).process(x)
    b = Freeverb(sample_rate=SR).process(x)
    assert np.allclose(a, b)


def test_plate_length_mono() -> None:
    x = sine(440.0, 0.5, SR) * 0.5
    rv = PlateReverb(sample_rate=SR)
    y = rv.process(x)
    assert y.shape == x.shape


def test_plate_length_stereo() -> None:
    x = np.stack([sine(440.0, 0.5, SR) * 0.5, sine(442.0, 0.5, SR) * 0.5], axis=1)
    rv = PlateReverb(sample_rate=SR)
    y = rv.process(x)
    assert y.shape == x.shape


def test_plate_adds_energy() -> None:
    x = np.zeros(int(0.2 * SR), dtype=np.float64)
    x[0] = 1.0
    rv = PlateReverb(room_size=0.7, wet=1.0, sample_rate=SR)
    y = rv.process(x)
    tail = y[int(0.05 * SR) :]
    assert np.max(np.abs(tail)) > 1e-6


def test_plate_determinism() -> None:
    x = noise_white(0.3, SR, seed=1) * 0.5
    a = PlateReverb(sample_rate=SR).process(x)
    b = PlateReverb(sample_rate=SR).process(x)
    assert np.allclose(a, b)
