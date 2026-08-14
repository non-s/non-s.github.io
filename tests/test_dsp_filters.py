from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.filters import BiquadFilter, FormantFilter, LadderFilter

SR = 44100


def test_biquad_lowpass_reduces_highs() -> None:
    sr = SR
    # Mix a low (200 Hz) and high (3 kHz) sine.
    low = osc.sine(200.0, 0.5, sr)
    high = osc.sine(3000.0, 0.5, sr)
    mix = low + high
    filt = BiquadFilter("lowpass", 500.0, 0.707, sr)
    out = filt.process(mix)
    assert out.shape == mix.shape
    # High-frequency energy should be reduced relative to input.
    in_high = np.abs(np.fft.rfft(mix)).copy()
    out_high = np.abs(np.fft.rfft(out)).copy()
    bin_3k = int(3000.0 * (in_high.size - 1) / (sr / 2.0))
    assert out_high[bin_3k] < in_high[bin_3k]


def test_biquad_highpass_reduces_lows() -> None:
    sr = SR
    low = osc.sine(200.0, 0.5, sr)
    high = osc.sine(3000.0, 0.5, sr)
    mix = low + high
    filt = BiquadFilter("highpass", 1000.0, 0.707, sr)
    out = filt.process(mix)
    in_spec = np.abs(np.fft.rfft(mix))
    out_spec = np.abs(np.fft.rfft(out))
    bin_200 = int(200.0 * (in_spec.size - 1) / (sr / 2.0))
    assert out_spec[bin_200] < in_spec[bin_200]


def test_biquad_set_cutoff_and_q() -> None:
    filt = BiquadFilter("lowpass", 1000.0, 0.7, SR)
    filt.set_cutoff(2000.0)
    filt.set_q(1.5)
    assert filt.cutoff_hz == 2000.0
    assert filt.q == 1.5


def test_biquad_length_preserved() -> None:
    x = osc.sine(440.0, 0.2, SR)
    for ftype in ("lowpass", "highpass", "bandpass", "notch", "allpass"):
        filt = BiquadFilter(ftype, 1000.0, 0.707, SR)
        out = filt.process(x)
        assert out.shape == x.shape


def test_biquad_determinism() -> None:
    x = osc.sine(440.0, 0.2, SR)
    a = BiquadFilter("lowpass", 1000.0, 0.707, SR).process(x)
    b = BiquadFilter("lowpass", 1000.0, 0.707, SR).process(x)
    assert np.allclose(a, b)


def test_ladder_length_and_lowpass() -> None:
    sr = SR
    low = osc.sine(200.0, 0.3, sr)
    high = osc.sine(3000.0, 0.3, sr)
    mix = low + high
    filt = LadderFilter(500.0, 0.2, sr)
    out = filt.process(mix)
    assert out.shape == mix.shape
    in_spec = np.abs(np.fft.rfft(mix))
    out_spec = np.abs(np.fft.rfft(out))
    bin_3k = int(3000.0 * (in_spec.size - 1) / (sr / 2.0))
    assert out_spec[bin_3k] < in_spec[bin_3k]


def test_ladder_determinism() -> None:
    x = osc.sine(440.0, 0.2, SR)
    a = LadderFilter(800.0, 0.3, SR).process(x)
    b = LadderFilter(800.0, 0.3, SR).process(x)
    assert np.allclose(a, b)


def test_formant_length_and_range() -> None:
    x = osc.sawtooth(150.0, 0.3, SR)
    for vowel in ("a", "e", "i", "o", "u"):
        out = FormantFilter(vowel, SR).process(x)
        assert out.shape == x.shape
        assert np.all(np.isfinite(out))


def test_formant_determinism() -> None:
    x = osc.sawtooth(150.0, 0.3, SR)
    a = FormantFilter("a", SR).process(x)
    b = FormantFilter("a", SR).process(x)
    assert np.allclose(a, b)
