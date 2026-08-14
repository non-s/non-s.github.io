"""Envelopes and LFOs for the Liquid Wire universal music engine.

All generators are pure procedural math on numpy arrays. ADSR/MultiStageEnv
return amplitude envelopes in [0, 1]; the LFO returns a bipolar signal in
[-depth, +depth] (or [0, depth] when used as a unipolar amplitude modulator).
"""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc

_LFO_SHAPES = {"sine", "triangle", "saw", "square", "random"}


class ADSR:
    """Attack-Decay-Sustain-Release envelope.

    Parameters are in seconds (attack, decay, release) and 0..1 (sustain).
    """

    def __init__(self, attack: float, decay: float, sustain: float, release: float) -> None:
        self.attack = max(0.0, float(attack))
        self.decay = max(0.0, float(decay))
        self.sustain = float(np.clip(sustain, 0.0, 1.0))
        self.release = max(0.0, float(release))

    def render(self, duration: float, sample_rate: int) -> np.ndarray:
        """Render an envelope of total length ``duration`` seconds.

        The envelope rises to 1 over ``attack``, falls to ``sustain`` over
        ``decay``, holds at ``sustain`` and releases to 0 over ``release`` if
        there is enough time left; otherwise it just sustains until the end.
        """
        sr = int(sample_rate)
        n = int(round(duration * sr))
        env = np.zeros(n, dtype=np.float64)
        a = int(round(self.attack * sr))
        d = int(round(self.decay * sr))
        r = int(round(self.release * sr))
        idx = 0
        # Attack.
        if a > 0 and idx < n:
            seg = min(a, n - idx)
            env[idx : idx + seg] = np.linspace(0.0, 1.0, seg, endpoint=False)
            idx += seg
        else:
            env[idx : min(idx + 1, n)] = 1.0
            idx = min(idx + 1, n)
        # Decay.
        if d > 0 and idx < n:
            seg = min(d, n - idx)
            env[idx : idx + seg] = np.linspace(1.0, self.sustain, seg, endpoint=False)
            idx += seg
        # Sustain + release.
        if idx < n:
            remaining = n - idx
            if r > 0 and r <= remaining:
                env[idx : idx + (remaining - r)] = self.sustain
                idx += remaining - r
                env[idx : idx + r] = np.linspace(self.sustain, 0.0, r, endpoint=False)
            else:
                env[idx:n] = self.sustain
        return env

    def render_with_release(self, duration: float, release_start: float, sample_rate: int) -> np.ndarray:
        """Render an envelope with an explicit release trigger point.

        ``release_start`` is the time (seconds) at which the note is released;
        the envelope holds at sustain up to that point then falls to 0 over
        ``self.release`` seconds (clamped to the remaining duration).
        """
        sr = int(sample_rate)
        n = int(round(duration * sr))
        rel_idx = int(round(release_start * sr))
        rel_idx = int(np.clip(rel_idx, 0, n))
        env = np.zeros(n, dtype=np.float64)
        a = int(round(self.attack * sr))
        d = int(round(self.decay * sr))
        r = int(round(self.release * sr))
        idx = 0
        end = rel_idx
        # Attack.
        if a > 0 and idx < end:
            seg = min(a, end - idx)
            env[idx : idx + seg] = np.linspace(0.0, 1.0, seg, endpoint=False)
            idx += seg
        else:
            if idx < end:
                env[idx : min(idx + 1, end)] = 1.0
                idx = min(idx + 1, end)
        # Decay.
        if d > 0 and idx < end:
            seg = min(d, end - idx)
            env[idx : idx + seg] = np.linspace(1.0, self.sustain, seg, endpoint=False)
            idx += seg
        # Sustain until release point.
        if idx < end:
            env[idx:end] = self.sustain
        # Release.
        if rel_idx < n:
            rlen = min(r, n - rel_idx)
            if rlen > 0:
                env[rel_idx : rel_idx + rlen] = np.linspace(self.sustain, 0.0, rlen, endpoint=False)
            if rel_idx + rlen < n:
                env[rel_idx + rlen :] = 0.0
        return env


class MultiStageEnv:
    """Multi-segment envelope: list of (target_level, time_seconds)."""

    def __init__(self, segments: list[tuple[float, float]]) -> None:
        self.segments = [(float(lvl), max(0.0, float(t))) for lvl, t in segments]

    def render(self, duration: float, sample_rate: int) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        env = np.zeros(n, dtype=np.float64)
        idx = 0
        level = 0.0
        for target, t in self.segments:
            if idx >= n:
                break
            seg = int(round(t * sr))
            if seg <= 0:
                level = target
                continue
            seg = min(seg, n - idx)
            env[idx : idx + seg] = np.linspace(level, target, seg, endpoint=False)
            level = target
            idx += seg
        if idx < n:
            env[idx:n] = level
        return env


class LFO:
    """Low-frequency oscillator used for amplitude or pitch modulation."""

    def __init__(
        self,
        rate_hz: float,
        shape: str,
        depth: float,
        sample_rate: int,
        duration: float,
    ) -> None:
        if shape not in _LFO_SHAPES:
            raise ValueError(f"shape must be one of {sorted(_LFO_SHAPES)}, got {shape!r}")
        self.rate_hz = float(rate_hz)
        self.shape = shape
        self.depth = float(depth)
        self.sample_rate = int(sample_rate)
        self.duration = float(duration)

    def render(self) -> np.ndarray:
        """Return the bipolar LFO signal in [-depth, +depth]."""
        if self.shape == "sine":
            base = osc.sine(self.rate_hz, self.duration, self.sample_rate)
        elif self.shape == "triangle":
            base = osc.triangle(self.rate_hz, self.duration, self.sample_rate)
        elif self.shape == "saw":
            base = osc.sawtooth(self.rate_hz, self.duration, self.sample_rate)
        elif self.shape == "square":
            base = osc.square(self.rate_hz, self.duration, self.sample_rate)
        else:  # random
            base = osc.noise_white(self.duration, self.sample_rate, seed=0)
            # Smooth slightly so it acts as an LFO rather than audio-rate noise.
            if base.size > 1:
                kernel = np.ones(max(1, self.sample_rate // 50)) / max(1, self.sample_rate // 50)
                base = np.convolve(base, kernel, mode="same")
                peak = float(np.max(np.abs(base))) if base.size else 1.0
                if peak > 1e-12:
                    base = base / peak
        return (base * self.depth).astype(np.float64)

    def apply_to(self, signal: np.ndarray, target: str = "amplitude") -> np.ndarray:
        """Modulate ``signal``; ``target`` is "amplitude" or "pitch"."""
        x = np.asarray(signal, dtype=np.float64).ravel()
        lfo = self.render()
        if lfo.size < x.size:
            # Tile the LFO to cover the signal length.
            reps = int(np.ceil(x.size / max(lfo.size, 1)))
            lfo = np.tile(lfo, reps)[: x.size]
        else:
            lfo = lfo[: x.size]
        if target == "amplitude":
            # Unipolar amplitude modulation: (1 + lfo) where lfo in [-depth, +depth].
            return (x * (1.0 + lfo)).astype(np.float64)
        elif target == "pitch":
            # Approximate pitch shift via phase accumulation on a resynthesis.
            # Treat the input as already a sine-like waveform and frequency-shift
            # by modulating its instantaneous phase via a resampling factor.
            ratio = 2.0 ** (lfo / 12.0)
            phase = np.cumsum(ratio)
            phase -= phase[0] if phase.size else 0.0
            # Linear interpolation resample.
            src_idx = np.clip(phase, 0.0, x.size - 1.0)
            i0 = np.floor(src_idx).astype(np.int64)
            i1 = np.clip(i0 + 1, 0, x.size - 1)
            frac = src_idx - i0
            return ((1.0 - frac) * x[i0] + frac * x[i1]).astype(np.float64)
        else:
            raise ValueError(f"target must be 'amplitude' or 'pitch', got {target!r}")
