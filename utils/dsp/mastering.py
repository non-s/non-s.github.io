"""Mastering-grade effects for the Liquid Wire engine.

Stereo widener, harmonic exciter, tape saturation simulator, multiband
compressor, and a convolution-style reverb using a procedurally synthesized
impulse response. All pure numpy/scipy, no external assets.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

from utils.dsp.dynamics import Compressor
from utils.dsp.filters import BiquadFilter


class StereoWidener:
    """Mid/side stereo widener.

    Adjusts the side (L-R) channel gain relative to the mid (L+R) to widen
    or narrow the stereo image. Operates on a stereo array of shape (2, N).
    """

    def __init__(self, width: float = 1.5) -> None:
        self.width = float(np.clip(width, 0.0, 3.0))

    def process(self, stereo: np.ndarray) -> np.ndarray:
        x = np.asarray(stereo, dtype=np.float64)
        if x.ndim != 2 or x.shape[0] != 2:
            return x
        mid = 0.5 * (x[0] + x[1])
        side = 0.5 * (x[0] - x[1])
        side = side * self.width
        left = mid + side
        right = mid - side
        return np.stack([left, right], axis=0)


class HarmonicExciter:
    """Harmonic exciter: adds controlled even/odd harmonics for brightness.

    Generates harmonics via a soft clipper applied to a high-passed copy of
    the signal, then blends the excitation back in. Gives air and presence
    without raising overall level.
    """

    def __init__(
        self,
        crossover_hz: float = 3500.0,
        drive: float = 0.6,
        mix: float = 0.25,
        sample_rate: int = 44100,
    ) -> None:
        self.crossover_hz = float(crossover_hz)
        self.drive = float(np.clip(drive, 0.0, 2.0))
        self.mix = float(np.clip(mix, 0.0, 1.0))
        self.sample_rate = int(sample_rate)

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        # High-pass to isolate the band that will be excited.
        hp = BiquadFilter("highpass", self.crossover_hz, 0.707, self.sample_rate)
        high_band = hp.process(x)
        # Soft clip to generate harmonics.
        driven = high_band * (1.0 + self.drive * 4.0)
        excited = np.tanh(driven)
        # Blend back.
        return (x + self.mix * excited).astype(np.float64)


class TapeSim:
    """Analog tape saturation simulator.

    Models tape compression (soft saturation), high-frequency roll-off (tape
    head loss), and a slow wow/flutter modulation. Adds warmth and glue.
    """

    def __init__(
        self,
        saturation: float = 0.5,
        hf_loss_hz: float = 12000.0,
        wow_depth: float = 0.002,
        flutter_depth: float = 0.0008,
        sample_rate: int = 44100,
    ) -> None:
        self.saturation = float(np.clip(saturation, 0.0, 1.5))
        self.hf_loss_hz = float(hf_loss_hz)
        self.wow_depth = float(wow_depth)
        self.flutter_depth = float(flutter_depth)
        self.sample_rate = int(sample_rate)

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        sr = self.sample_rate
        n = x.size
        if n == 0:
            return x.copy()
        # Saturation: tanh soft clip with drive.
        drive = 1.0 + self.saturation * 2.0
        saturated = np.tanh(x * drive) / np.tanh(drive)
        # High-frequency tape loss: gentle lowpass.
        if self.hf_loss_hz < sr / 2.0:
            lp = BiquadFilter("lowpass", self.hf_loss_hz, 0.6, sr)
            saturated = lp.process(saturated)
        # Wow (slow) + flutter (fast) pitch modulation via resampling.
        if self.wow_depth > 0 or self.flutter_depth > 0:
            t = np.arange(n, dtype=np.float64) / float(sr)
            wow = self.wow_depth * np.sin(2.0 * np.pi * 0.5 * t)
            flutter = self.flutter_depth * np.sin(2.0 * np.pi * 13.0 * t + 1.3)
            pitch_mod = 1.0 + wow + flutter
            # Phase accumulation resampling.
            phase = np.cumsum(pitch_mod)
            src_idx = np.clip(phase, 0.0, n - 1.0)
            i0 = np.floor(src_idx).astype(np.int64)
            i1 = np.clip(i0 + 1, 0, n - 1)
            frac = src_idx - i0
            saturated = (1.0 - frac) * saturated[i0] + frac * saturated[i1]
        return saturated.astype(np.float64)


class MultibandCompressor:
    """3-band multiband compressor for mastering.

    Splits the signal into low/mid/high bands via Linkwitz-Riley crossovers,
    compresses each band independently, then recombines. Gives tight low end,
    controlled mids, and airy highs.
    """

    def __init__(
        self,
        crossover_low_hz: float = 200.0,
        crossover_high_hz: float = 4000.0,
        sample_rate: int = 44100,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self._crossover_low = float(crossover_low_hz)
        self._crossover_high = float(crossover_high_hz)
        # Per-band compressors (threshold, ratio, attack, release, makeup).
        self._low_comp = Compressor(-12.0, 3.0, 8.0, 80.0, makeup_gain=1.3, sample_rate=sample_rate)
        self._mid_comp = Compressor(-10.0, 2.5, 12.0, 120.0, makeup_gain=1.1, sample_rate=sample_rate)
        self._high_comp = Compressor(-8.0, 2.0, 5.0, 60.0, makeup_gain=1.2, sample_rate=sample_rate)

    def _lr4_split(self, x: np.ndarray, cutoff: float) -> tuple[np.ndarray, np.ndarray]:
        """Linkwitz-Riley 4th-order crossover split into (low, high)."""
        sr = self.sample_rate
        # Two cascaded 2nd-order Butterworth (Q=0.5) filters = LR4.
        lp1 = BiquadFilter("lowpass", cutoff, 0.5, sr)
        lp2 = BiquadFilter("lowpass", cutoff, 0.5, sr)
        hp1 = BiquadFilter("highpass", cutoff, 0.5, sr)
        hp2 = BiquadFilter("highpass", cutoff, 0.5, sr)
        low = lp2.process(lp1.process(x))
        high = hp2.process(hp1.process(x))
        return low, high

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        if x.size == 0:
            return x.copy()
        # Split into 3 bands.
        low, rest = self._lr4_split(x, self._crossover_low)
        mid, high = self._lr4_split(rest, self._crossover_high)
        # Compress each band.
        low = self._low_comp.process(low)
        mid = self._mid_comp.process(mid)
        high = self._high_comp.process(high)
        # Recombine.
        return (low + mid + high).astype(np.float64)


class ConvolutionReverb:
    """Convolution reverb using a procedurally synthesized impulse response.

    Generates a synthetic IR from exponentially decaying filtered noise with
    early reflections, then convolves the input with it via scipy.signal
    fftconvolve for a lush, realistic reverb tail. No external IR files.
    """

    def __init__(
        self,
        room_size: float = 0.6,
        decay_seconds: float = 2.0,
        wet: float = 0.3,
        sample_rate: int = 44100,
        seed: int = 0,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self.room_size = float(np.clip(room_size, 0.0, 1.0))
        self.decay_seconds = float(max(0.1, decay_seconds))
        self.wet = float(np.clip(wet, 0.0, 1.0))
        self._ir = self._build_ir(seed)

    def _build_ir(self, seed: int) -> np.ndarray:
        sr = self.sample_rate
        n = int(self.decay_seconds * sr)
        rng = np.random.default_rng(seed)
        # Exponentially decaying noise as the diffuse tail.
        t = np.arange(n, dtype=np.float64) / float(sr)
        decay = np.exp(-t * (2.0 / self.decay_seconds) * (0.5 + self.room_size))
        ir = rng.standard_normal(n) * decay
        # Early reflections: a few discrete impulses at room-dependent delays.
        n_early = 6
        for i in range(n_early):
            delay = int((0.01 + 0.02 * i + 0.01 * rng.random()) * sr)
            if delay < n:
                ir[delay] += (0.5 ** i) * rng.uniform(0.5, 1.0)
        # Lowpass the IR for a warmer room tone.
        lp = BiquadFilter("lowpass", 6000.0 - 3000.0 * (1.0 - self.room_size), 0.7, sr)
        ir = lp.process(ir)
        # Normalise.
        peak = float(np.max(np.abs(ir))) if ir.size else 1.0
        if peak > 1e-12:
            ir = ir / peak
        return ir.astype(np.float64)

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        if x.size == 0:
            return x.copy()
        wet = fftconvolve(x, self._ir, mode="full")[: x.size]
        # The convolution output can be large; scale by the IR's RMS energy
        # and apply a fixed gain so the wet return adds audible presence.
        ir_rms = float(np.sqrt(np.mean(self._ir ** 2))) if self._ir.size else 1.0
        if ir_rms > 1e-12:
            wet = wet / ir_rms * 0.3
        return (x + self.wet * wet).astype(np.float64)
