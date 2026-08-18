"""Tests for the advanced instruments and mastering effects."""

from __future__ import annotations

import numpy as np

from utils.dsp.mastering import (
    ConvolutionReverb,
    HarmonicExciter,
    MultibandCompressor,
    StereoWidener,
    TapeSim,
)
from utils.instruments import advanced as adv
from utils.instruments.base import NoteEvent

SR = 44100


def _note(dur: float = 0.3, midi: int = 60, vel: float = 0.7) -> NoteEvent:
    return NoteEvent(note=midi, start=0.0, duration=dur, velocity=vel)


def _sine(freq: float = 440.0, dur: float = 0.3) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    return 0.5 * np.sin(2 * np.pi * freq * t)


# --- Advanced instruments ---


def test_glass_harp_length_and_finite() -> None:
    out = adv.GlassHarp(seed=1).render(_note(0.5), SR)
    assert out.shape[0] == int(0.5 * SR)
    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) > 0.1


def test_music_box_length_and_finite() -> None:
    out = adv.MusicBox(seed=1).render(_note(0.4), SR)
    assert out.shape[0] == int(0.4 * SR)
    assert np.all(np.isfinite(out))


def test_theremin_length_and_finite() -> None:
    out = adv.Theremin(seed=1).render(_note(0.5), SR)
    assert out.shape[0] == int(0.5 * SR)
    assert np.all(np.isfinite(out))


def test_pulsar_synth_length_and_finite() -> None:
    out = adv.PulsarSynth(seed=1).render(_note(0.3), SR)
    assert out.shape[0] == int(0.3 * SR)
    assert np.all(np.isfinite(out))


def test_dulcimer_length_and_finite() -> None:
    out = adv.Dulcimer(seed=1).render(_note(0.4), SR)
    assert out.shape[0] == int(0.4 * SR)
    assert np.all(np.isfinite(out))


def test_hang_length_and_finite() -> None:
    out = adv.Hang(seed=1).render(_note(0.5), SR)
    assert out.shape[0] == int(0.5 * SR)
    assert np.all(np.isfinite(out))


def test_crystal_bow_length_and_finite() -> None:
    out = adv.CrystalBow(seed=1).render(_note(0.5), SR)
    assert out.shape[0] == int(0.5 * SR)
    assert np.all(np.isfinite(out))


def test_warm_pad_length_and_finite() -> None:
    out = adv.WarmPad(seed=1).render(_note(0.5), SR)
    assert out.shape[0] == int(0.5 * SR)
    assert np.all(np.isfinite(out))


def test_advanced_instruments_determinism() -> None:
    for cls in (adv.GlassHarp, adv.MusicBox, adv.Dulcimer, adv.Hang):
        a = cls(seed=42).render(_note(0.2), SR)
        b = cls(seed=42).render(_note(0.2), SR)
        assert np.allclose(a, b)


# --- Mastering effects ---


def test_stereo_widener_preserves_length() -> None:
    x = np.stack([_sine(440.0, 0.3), _sine(440.0, 0.3)], axis=0)
    y = StereoWidener(width=1.5).process(x)
    assert y.shape == x.shape


def test_stereo_widener_mono_passthrough() -> None:
    x = _sine(440.0, 0.2)
    y = StereoWidener(width=2.0).process(x)
    assert np.allclose(y, x)


def test_harmonic_exciter_preserves_length() -> None:
    x = _sine(440.0, 0.3)
    y = HarmonicExciter(sample_rate=SR).process(x)
    assert y.shape == x.shape
    assert np.all(np.isfinite(y))


def test_harmonic_exciter_adds_high_freq_content() -> None:
    x = _sine(200.0, 0.3)
    y = HarmonicExciter(crossover_hz=150.0, drive=1.0, mix=0.5, sample_rate=SR).process(x)
    in_spec = np.abs(np.fft.rfft(x))
    out_spec = np.abs(np.fft.rfft(y))
    # High-frequency energy should increase.
    high_bins = in_spec.size // 4
    assert np.sum(out_spec[high_bins:]) > np.sum(in_spec[high_bins:])


def test_tape_sim_preserves_length() -> None:
    x = _sine(440.0, 0.3)
    y = TapeSim(sample_rate=SR).process(x)
    assert y.shape == x.shape
    assert np.all(np.isfinite(y))


def test_multiband_compressor_preserves_length() -> None:
    x = _sine(80.0, 0.3) + _sine(1000.0, 0.3) + _sine(6000.0, 0.3)
    y = MultibandCompressor(sample_rate=SR).process(x)
    assert y.shape == x.shape
    assert np.all(np.isfinite(y))


def test_convolution_reverb_preserves_length() -> None:
    x = _sine(440.0, 0.5)
    y = ConvolutionReverb(decay_seconds=0.5, wet=0.3, sample_rate=SR).process(x)
    assert y.shape == x.shape
    assert np.all(np.isfinite(y))


def test_convolution_reverb_adds_energy() -> None:
    x = _sine(440.0, 0.5)
    dry_energy = float(np.sum(x ** 2))
    y = ConvolutionReverb(decay_seconds=1.0, wet=0.5, sample_rate=SR).process(x)
    wet_energy = float(np.sum(y ** 2))
    assert wet_energy > dry_energy


def test_mastering_effects_determinism() -> None:
    x = _sine(440.0, 0.3)
    a = TapeSim(sample_rate=SR).process(x)
    b = TapeSim(sample_rate=SR).process(x)
    assert np.allclose(a, b)
