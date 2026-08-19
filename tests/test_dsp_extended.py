"""Tests for the new DSP modules of Engine 4.0.

Covers fm_synth, wavetable, granular, physical_modeling and extra_effects.
Each test is fast (<1s) and validates shapes, finiteness and determinism.
"""

from __future__ import annotations

import numpy as np
import pytest

from utils.dsp.envelopes import ADSR
from utils.dsp.fm_synth import FMSynth, _Operator
from utils.dsp.granular import GrainCloud, freeze, time_stretch
from utils.dsp.physical_modeling import KarplusStrong, WaveguideString
from utils.dsp.wavetable import MorphWavetable, WavetableSynth

SR = 44100


def _sin(freq: float, dur: float, sr: int = SR) -> np.ndarray:
    t = np.arange(int(round(dur * sr)), dtype=np.float64) / sr
    return np.sin(2.0 * np.pi * freq * t)


# --- fm_synth ----------------------------------------------------------------

class TestFMSynth:
    def test_render_shape_finite(self):
        out = FMSynth().render(freq=220.0, duration=0.1, sr=SR)
        assert out.shape == (int(0.1 * SR),)
        assert np.all(np.isfinite(out))
        assert np.max(np.abs(out)) > 1e-6

    @pytest.mark.parametrize("algo", [0, 1, 2, 3, 4, 5])
    def test_algorithms(self, algo):
        out = FMSynth(algorithm=algo).render(freq=220.0, duration=0.1, sr=SR)
        assert np.all(np.isfinite(out))
        assert out.shape == (int(0.1 * SR),)

    def test_operator_default_patch(self):
        ops = FMSynth._default_patch()
        assert len(ops) == 6
        out = _Operator().render(freq=220.0, duration=0.1, sr=SR)
        assert np.all(np.isfinite(out))
        assert out.shape == (int(0.1 * SR),)

    def test_determinism(self):
        a = FMSynth(algorithm=2).render(freq=220.0, duration=0.1, sr=SR)
        b = FMSynth(algorithm=2).render(freq=220.0, duration=0.1, sr=SR)
        assert np.allclose(a, b)


# --- wavetable ---------------------------------------------------------------

class TestWavetable:
    def test_morph_wavetable_sample(self):
        wt = MorphWavetable(size=256, num_frames=8, seed=0)
        v = wt.sample(position=0.5, phase=0.3)
        assert isinstance(v, float)
        assert np.isfinite(v)

    def test_morph_wavetable_scan(self):
        wt = MorphWavetable(size=256, num_frames=8, seed=0)
        pos = np.linspace(0.0, 1.0, 64)
        phase = np.linspace(0.0, 1.0, 64)
        out = wt.scan(pos, phase)
        assert out.shape == (64,)
        assert np.all(np.isfinite(out))

    def test_wavetable_synth_render(self):
        wt = MorphWavetable(size=256, num_frames=8, seed=0)
        synth = WavetableSynth(wt, morph_lfo_rate=0.5, morph_position=0.3)
        out = synth.render(freq=440.0, duration=0.1, sr=SR)
        assert out.shape == (int(0.1 * SR),)
        assert np.all(np.isfinite(out))
        assert np.max(np.abs(out)) > 1e-6

    def test_wavetable_synth_no_lfo(self):
        wt = MorphWavetable(size=256, num_frames=8, seed=0)
        synth = WavetableSynth(wt, morph_lfo_rate=0.0, morph_position=0.5)
        out = synth.render(freq=440.0, duration=0.1, sr=SR, env=ADSR(0.01, 0.05, 0.8, 0.05))
        assert np.all(np.isfinite(out))


# --- granular ----------------------------------------------------------------

class TestGranular:
    def test_grain_cloud_render(self):
        src = _sin(440.0, 0.5)
        cloud = GrainCloud(src, sr=SR, density=30.0, grain_ms=30.0, seed=0)
        out = cloud.render(0.5)
        assert out.shape == (2, int(0.5 * SR))
        assert np.all(np.isfinite(out))

    def test_freeze(self):
        src = _sin(440.0, 0.5)
        out = freeze(src, sr=SR, duration=0.3, at=0.1, seed=0)
        assert out.shape[0] == 2
        assert np.all(np.isfinite(out))

    def test_time_stretch(self):
        src = _sin(440.0, 0.3)
        out = time_stretch(src, sr=SR, factor=1.5, grain_ms=40.0, overlap=0.5)
        assert out.ndim == 1
        assert np.all(np.isfinite(out))

    def test_grain_cloud_determinism(self):
        src = _sin(440.0, 0.3)
        a = GrainCloud(src, sr=SR, density=20.0, seed=42).render(0.2)
        b = GrainCloud(src, sr=SR, density=20.0, seed=42).render(0.2)
        assert np.allclose(a, b)


# --- physical_modeling -------------------------------------------------------

class TestPhysicalModeling:
    def test_karplus_strong_render(self):
        ks = KarplusStrong(decay=0.99, blend=0.5, seed=0)
        out = ks.render(freq=220.0, duration=0.2, sr=SR, velocity=0.8)
        assert out.shape == (int(0.2 * SR),)
        assert np.all(np.isfinite(out))
        assert np.max(np.abs(out)) > 1e-6

    def test_waveguide_string_render(self):
        wg = WaveguideString(decay=0.996, damping=0.3, dispersion=0.1, bridge_pos=0.3, seed=0)
        out = wg.render(freq=220.0, duration=0.2, sr=SR, velocity=0.8)
        assert out.shape == (int(0.2 * SR),)
        assert np.all(np.isfinite(out))

    def test_karplus_strong_determinism(self):
        a = KarplusStrong(seed=7).render(freq=220.0, duration=0.1, sr=SR)
        b = KarplusStrong(seed=7).render(freq=220.0, duration=0.1, sr=SR)
        assert np.allclose(a, b)


# --- extra_effects -----------------------------------------------------------

class TestExtraEffects:
    def setup_method(self):
        self.x = _sin(440.0, 0.2)

    def test_flanger(self):
        from utils.dsp.extra_effects import Flanger
        out = Flanger(rate_hz=0.5, depth=2.0, feedback=0.7, mix=0.5, sample_rate=SR).process(self.x)
        assert out.shape == self.x.shape
        assert np.all(np.isfinite(out))

    def test_ring_modulator(self):
        from utils.dsp.extra_effects import RingModulator
        out = RingModulator(carrier_hz=200.0, mix=0.8, sample_rate=SR).process(self.x)
        assert out.shape == self.x.shape
        assert np.all(np.isfinite(out))

    def test_tremolo(self):
        from utils.dsp.extra_effects import Tremolo
        out = Tremolo(rate_hz=5.0, depth=0.6, shape="sine", sample_rate=SR).process(self.x)
        assert out.shape == self.x.shape
        assert np.all(np.isfinite(out))

    def test_vibrato(self):
        from utils.dsp.extra_effects import Vibrato
        out = Vibrato(rate_hz=5.5, depth_cents=25.0, sample_rate=SR).process(self.x)
        assert out.shape == self.x.shape
        assert np.all(np.isfinite(out))

    def test_pitch_shifter(self):
        from utils.dsp.extra_effects import PitchShifter
        out = PitchShifter(shift_semitones=7.0, grain_ms=40.0, sample_rate=SR).process(self.x)
        assert out.shape == self.x.shape
        assert np.all(np.isfinite(out))

    def test_harmonizer(self):
        from utils.dsp.extra_effects import Harmonizer
        out = Harmonizer(interval_semitones=7.0, mix=0.6, sample_rate=SR).process(self.x)
        assert out.shape == self.x.shape
        assert np.all(np.isfinite(out))
