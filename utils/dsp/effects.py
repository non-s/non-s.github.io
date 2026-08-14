"""Time- and amplitude-domain effects for the Liquid Wire DSP engine.

Delay, chorus, phaser, distortion and bitcrusher - all pure numpy, no external
assets. Each effect accepts a mono (or stereo) numpy float64 array and returns
an array of the same shape.
"""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.filters import BiquadFilter


def _to_channels(signal: np.ndarray) -> list[np.ndarray]:
    x = np.asarray(signal, dtype=np.float64)
    if x.ndim == 1:
        return [x]
    return [x[:, c] for c in range(x.shape[1])]


def _from_channels(channels: list[np.ndarray]) -> np.ndarray:
    if len(channels) == 1:
        return channels[0]
    return np.stack(channels, axis=1)


class Delay:
    """Feedback delay line with wet/dry mix."""

    def __init__(
        self,
        time_ms: float,
        feedback: float = 0.3,
        mix: float = 0.25,
        sample_rate: int = 44100,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self.time_ms = float(time_ms)
        self.feedback = float(np.clip(feedback, 0.0, 0.999))
        self.mix = float(np.clip(mix, 0.0, 1.0))
        self._delay_samples = max(1, int(round(self.time_ms * 1e-3 * self.sample_rate)))

    def process(self, signal: np.ndarray) -> np.ndarray:
        channels = _to_channels(signal)
        out_channels: list[np.ndarray] = []
        for ch in channels:
            n = ch.size
            buf = np.zeros(self._delay_samples, dtype=np.float64)
            out = np.empty(n, dtype=np.float64)
            idx = 0
            for i in range(n):
                delayed = buf[idx]
                out[i] = ch[i] + self.mix * delayed
                buf[idx] = ch[i] + self.feedback * delayed
                idx = (idx + 1) % self._delay_samples
            out_channels.append(out)
        return _from_channels(out_channels)


class Chorus:
    """Multi-voice chorus via modulated delay lines."""

    def __init__(
        self,
        rate_hz: float = 0.5,
        depth: float = 0.3,
        voices: int = 3,
        sample_rate: int = 44100,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self.rate_hz = float(rate_hz)
        self.depth = float(depth)
        self.voices = max(1, int(voices))
        # Base delay around 25 ms; voices are offset slightly to thicken.
        self._base_delay = int(round(0.025 * self.sample_rate))
        self._max_delay = int(round((0.025 + 0.020) * self.sample_rate))

    def process(self, signal: np.ndarray) -> np.ndarray:
        channels = _to_channels(signal)
        out_channels: list[np.ndarray] = []
        for ch in channels:
            n = ch.size
            out = ch.copy()
            for v in range(self.voices):
                # Each voice has a slightly different LFO phase and rate.
                phase = v * (2.0 * np.pi / self.voices)
                rate_v = self.rate_hz * (1.0 + 0.07 * v)
                lfo = osc.sine(rate_v, n / float(self.sample_rate), self.sample_rate, phase=phase)
                # Map LFO [-1, 1] to a delay offset in samples.
                delay = self._base_delay + (lfo * self.depth * 0.015 * self.sample_rate).astype(np.float64)
                buf = np.zeros(self._max_delay, dtype=np.float64)
                widx = 0
                for i in range(n):
                    # Read position is fractional -> linear interpolation.
                    read = (widx - delay[i]) % self._max_delay
                    r0 = int(np.floor(read))
                    r1 = (r0 + 1) % self._max_delay
                    frac = read - r0
                    delayed = (1.0 - frac) * buf[r0] + frac * buf[r1]
                    out[i] += delayed / float(self.voices + 1)
                    buf[widx] = ch[i]
                    widx = (widx + 1) % self._max_delay
            out_channels.append(out)
        return _from_channels(out_channels)


class Phaser:
    """Multi-stage allpass phaser with an LFO-modulated cutoff."""

    def __init__(
        self,
        rate_hz: float = 0.5,
        depth: float = 0.5,
        stages: int = 4,
        sample_rate: int = 44100,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self.rate_hz = float(rate_hz)
        self.depth = float(np.clip(depth, 0.0, 1.0))
        self.stages = max(1, int(stages))

    def process(self, signal: np.ndarray) -> np.ndarray:
        channels = _to_channels(signal)
        out_channels: list[np.ndarray] = []
        for ch in channels:
            n = ch.size
            # LFO sweeps the allpass cutoff between ~200 Hz and ~2 kHz.
            lfo = osc.triangle(self.rate_hz, n / float(self.sample_rate), self.sample_rate)
            min_f = 200.0
            max_f = 2000.0
            cutoffs = min_f * (max_f / min_f) ** ((lfo * 0.5 + 0.5) * self.depth + (1.0 - self.depth) * 0.5)
            # Build a fresh chain of allpass biquads per sample (coeffs are cheap).
            filters = [BiquadFilter("allpass", 1000.0, 0.707, self.sample_rate) for _ in range(self.stages)]
            out = np.empty(n, dtype=np.float64)
            for i in range(n):
                f = float(np.clip(cutoffs[i], 10.0, self.sample_rate * 0.49))
                for flt in filters:
                    flt.set_cutoff(f)
                s = np.array([ch[i]], dtype=np.float64)
                for flt in filters:
                    s = flt.process(s)
                # Mix dry + wet for the classic phaser sweep.
                out[i] = 0.5 * ch[i] + 0.5 * s[0]
            out_channels.append(out)
        return _from_channels(out_channels)


class Distortion:
    """Asymmetrical soft/hard clipping with a tone-control lowpass."""

    def __init__(self, drive: float = 0.7, tone: float = 0.5, sample_rate: int = 44100) -> None:
        self.sample_rate = int(sample_rate)
        self.drive = float(np.clip(drive, 0.0, 1.0)) * 10.0 + 1.0
        self.tone = float(np.clip(tone, 0.0, 1.0))
        # Tone lowpass cutoff sweeps from ~1.5 kHz (dark) to ~8 kHz (bright).
        self._tone_cutoff = 1500.0 + self.tone * 6500.0
        self._tone = BiquadFilter("lowpass", self._tone_cutoff, 0.707, self.sample_rate)

    def process(self, signal: np.ndarray) -> np.ndarray:
        channels = _to_channels(signal)
        out_channels: list[np.ndarray] = []
        for ch in channels:
            driven = ch * self.drive
            # Asymmetrical clipping: positive half soft-clipped harder than negative.
            pos = np.tanh(driven)
            neg = np.tanh(driven * 0.6) / 0.6
            clipped = np.where(driven >= 0.0, pos, neg)
            toned = self._tone.process(clipped)
            peak = float(np.max(np.abs(toned))) if toned.size else 1.0
            if peak > 1e-12:
                toned = toned / peak
            out_channels.append(toned)
        return _from_channels(out_channels)


class Bitcrusher:
    """Reduce the effective bit depth and (optionally) sample rate."""

    def __init__(self, bits: int = 8, sample_rate: int = 44100) -> None:
        self.bits = max(1, int(bits))
        self.sample_rate = int(sample_rate)

    def process(self, signal: np.ndarray) -> np.ndarray:
        channels = _to_channels(signal)
        out_channels: list[np.ndarray] = []
        levels = 2.0 ** self.bits
        for ch in channels:
            # Quantise to ``bits`` resolution.
            quantised = np.round(ch * levels) / levels
            out_channels.append(quantised)
        return _from_channels(out_channels)
