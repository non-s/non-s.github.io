from __future__ import annotations

import numpy as np

from utils.dsp.effects import Bitcrusher, Chorus, Delay, Distortion, Phaser
from utils.dsp.oscillators import noise_white, sine

SR = 44100


def test_delay_length() -> None:
    x = sine(440.0, 0.5, SR)
    d = Delay(100.0, feedback=0.3, mix=0.25, sample_rate=SR)
    y = d.process(x)
    assert y.shape == x.shape


def test_delay_produces_echo() -> None:
    x = np.zeros(int(0.3 * SR), dtype=np.float64)
    x[0] = 1.0
    d = Delay(50.0, feedback=0.5, mix=1.0, sample_rate=SR)
    y = d.process(x)
    # Expect a non-zero sample around the delay time.
    delay_idx = int(0.05 * SR)
    assert abs(y[delay_idx]) > 1e-6


def test_delay_determinism() -> None:
    x = sine(440.0, 0.3, SR)
    a = Delay(100.0, sample_rate=SR).process(x)
    b = Delay(100.0, sample_rate=SR).process(x)
    assert np.allclose(a, b)


def test_chorus_length() -> None:
    x = sine(440.0, 0.5, SR)
    c = Chorus(rate_hz=0.5, depth=0.3, voices=3, sample_rate=SR)
    y = c.process(x)
    assert y.shape == x.shape


def test_chorus_changes_signal() -> None:
    x = sine(440.0, 0.5, SR)
    c = Chorus(rate_hz=1.0, depth=0.5, voices=3, sample_rate=SR)
    y = c.process(x)
    assert not np.allclose(y, x)


def test_chorus_determinism() -> None:
    x = sine(440.0, 0.3, SR)
    a = Chorus(sample_rate=SR).process(x)
    b = Chorus(sample_rate=SR).process(x)
    assert np.allclose(a, b)


def test_phaser_length() -> None:
    x = sine(440.0, 0.5, SR)
    p = Phaser(rate_hz=0.5, depth=0.5, stages=4, sample_rate=SR)
    y = p.process(x)
    assert y.shape == x.shape


def test_phaser_changes_signal() -> None:
    x = sine(440.0, 0.5, SR)
    p = Phaser(rate_hz=1.0, depth=0.8, stages=4, sample_rate=SR)
    y = p.process(x)
    assert not np.allclose(y, x)


def test_phaser_determinism() -> None:
    x = sine(440.0, 0.3, SR)
    a = Phaser(sample_rate=SR).process(x)
    b = Phaser(sample_rate=SR).process(x)
    assert np.allclose(a, b)


def test_distortion_length() -> None:
    x = sine(440.0, 0.5, SR) * 0.5
    d = Distortion(drive=0.7, tone=0.5, sample_rate=SR)
    y = d.process(x)
    assert y.shape == x.shape


def test_distortion_adds_harmonics() -> None:
    x = sine(440.0, 0.5, SR) * 0.5
    d = Distortion(drive=0.9, tone=0.5, sample_rate=SR)
    y = d.process(x)
    in_spec = np.abs(np.fft.rfft(x))
    out_spec = np.abs(np.fft.rfft(y))
    # 2nd harmonic bin.
    bin_880 = int(880.0 * (in_spec.size - 1) / (SR / 2.0))
    assert out_spec[bin_880] > in_spec[bin_880]


def test_distortion_determinism() -> None:
    x = sine(440.0, 0.3, SR) * 0.5
    a = Distortion(sample_rate=SR).process(x)
    b = Distortion(sample_rate=SR).process(x)
    assert np.allclose(a, b)


def test_bitcrusher_length() -> None:
    x = sine(440.0, 0.5, SR)
    b = Bitcrusher(bits=8, sample_rate=SR)
    y = b.process(x)
    assert y.shape == x.shape


def test_bitcrusher_quantises() -> None:
    x = sine(440.0, 0.2, SR)
    b = Bitcrusher(bits=4, sample_rate=SR)
    y = b.process(x)
    levels = 2.0 ** 4
    # Every output sample should lie on the quantisation grid.
    q = np.round(y * levels) / levels
    assert np.allclose(y, q, atol=1e-9)


def test_bitcrusher_determinism() -> None:
    x = noise_white(0.3, SR, seed=1)
    a = Bitcrusher(bits=6, sample_rate=SR).process(x)
    b = Bitcrusher(bits=6, sample_rate=SR).process(x)
    assert np.array_equal(a, b)
