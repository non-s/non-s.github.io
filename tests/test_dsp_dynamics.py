from __future__ import annotations

import numpy as np

from utils.dsp.dynamics import Compressor, Limiter, SideChainDuck
from utils.dsp.oscillators import noise_white, sine

SR = 44100


def test_compressor_length() -> None:
    x = sine(440.0, 0.5, SR) * 0.9
    comp = Compressor(-20.0, 4.0, 5.0, 50.0, sample_rate=SR)
    y = comp.process(x)
    assert y.shape == x.shape


def test_compressor_reduces_dynamic_range() -> None:
    # Loud signal above threshold should be attenuated.
    x = sine(440.0, 0.5, SR) * 0.9
    comp = Compressor(-20.0, 4.0, 5.0, 50.0, makeup_gain=1.0, sample_rate=SR)
    y = comp.process(x)
    assert np.max(np.abs(y)) < np.max(np.abs(x))


def test_compressor_below_threshold_passthrough() -> None:
    # Quiet signal below threshold should be largely unchanged.
    x = sine(440.0, 0.5, SR) * 0.01
    comp = Compressor(-20.0, 4.0, 5.0, 50.0, makeup_gain=1.0, sample_rate=SR)
    y = comp.process(x)
    assert np.allclose(y, x, atol=1e-2)


def test_compressor_determinism() -> None:
    x = sine(440.0, 0.3, SR) * 0.9
    a = Compressor(-20.0, 4.0, 5.0, 50.0, sample_rate=SR).process(x)
    b = Compressor(-20.0, 4.0, 5.0, 50.0, sample_rate=SR).process(x)
    assert np.allclose(a, b)


def test_limiter_length() -> None:
    x = noise_white(0.5, SR, seed=1) * 2.0
    lim = Limiter(ceiling=0.9, sample_rate=SR)
    y = lim.process(x)
    assert y.shape == x.shape


def test_limiter_respects_ceiling() -> None:
    x = noise_white(0.5, SR, seed=2) * 2.0
    lim = Limiter(ceiling=0.9, sample_rate=SR)
    y = lim.process(x)
    assert np.max(np.abs(y)) <= 0.9 + 1e-9


def test_limiter_determinism() -> None:
    x = noise_white(0.3, SR, seed=5) * 1.5
    a = Limiter(ceiling=0.9, sample_rate=SR).process(x)
    b = Limiter(ceiling=0.9, sample_rate=SR).process(x)
    assert np.allclose(a, b)


def test_sidechain_length() -> None:
    src = sine(80.0, 0.5, SR)
    tgt = sine(200.0, 0.5, SR) * 0.8
    duck = SideChainDuck(src, tgt, -30.0, 4.0, 5.0, 50.0, SR)
    y = duck.process()
    assert y.shape == tgt.shape


def test_sidechain_ducks_when_source_loud() -> None:
    src = sine(80.0, 0.5, SR) * 0.9
    tgt = sine(200.0, 0.5, SR) * 0.8
    duck = SideChainDuck(src, tgt, -40.0, 8.0, 5.0, 50.0, SR)
    y = duck.process()
    # The target should be attenuated somewhere in the output.
    assert np.max(np.abs(y)) < np.max(np.abs(tgt))


def test_sidechain_determinism() -> None:
    src = sine(80.0, 0.3, SR) * 0.9
    tgt = sine(200.0, 0.3, SR) * 0.8
    a = SideChainDuck(src, tgt, -40.0, 8.0, 5.0, 50.0, SR).process()
    b = SideChainDuck(src, tgt, -40.0, 8.0, 5.0, 50.0, SR).process()
    assert np.allclose(a, b)
