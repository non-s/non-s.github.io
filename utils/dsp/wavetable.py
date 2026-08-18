"""Wavetable synthesis with morphing.

A wavetable holds a bank of single-cycle waveforms; the synthesizer
crossfades between adjacent waves over time ("scanning") to produce timbral
evolution. This is the technique behind Serum, Massive, and modern
wavetable synths. We generate the tables procedurally so no external
samples are needed.

Public API:
- ``Wavetable`` — a bank of single-cycle waveforms with interpolation.
- ``WavetableSynth`` — oscillator that scans the table at audio rate,
  supports morph position modulation (LFO/manual), and applies an ADSR.
- ``MorphWavetable`` — pre-built morphing tables (sine→saw→square→noise).
"""

from __future__ import annotations

import numpy as np

from utils.dsp.envelopes import ADSR


def _make_table(size: int = 2048) -> np.ndarray:
    """Return a normalised single-cycle waveform of ``size`` samples."""
    t = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float64)
    return t


def _saw_table(size: int = 2048) -> np.ndarray:
    t = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float64)
    return (2.0 * t - 1.0)


def _square_table(size: int = 2048) -> np.ndarray:
    t = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float64)
    return np.where(t < 0.5, 1.0, -1.0)


def _sine_table(size: int = 2048) -> np.ndarray:
    t = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float64)
    return np.sin(2.0 * np.pi * t)


def _triangle_table(size: int = 2048) -> np.ndarray:
    t = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float64)
    return (4.0 * np.abs(t - 0.5) - 1.0)


def _noise_table(size: int = 2048, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = rng.standard_normal(size)
    peak = np.max(np.abs(t)) if t.size else 1.0
    if peak > 1e-12:
        t = t / peak
    return t


class Wavetable:
    """Bank of single-cycle waveforms with linear interpolation.

    Parameters
    ----------
    frames : np.ndarray
        2D array of shape (num_frames, frame_size). Each row is one
        single-cycle waveform normalised to roughly [-1, 1].
    """

    def __init__(self, frames: np.ndarray) -> None:
        if frames.ndim != 2:
            raise ValueError("frames must be 2D (num_frames, frame_size)")
        self.frames = frames.astype(np.float64, copy=False)
        self.num_frames = frames.shape[0]
        self.frame_size = frames.shape[1]

    def sample(self, position: float, phase: float) -> float:
        """Sample one value at wavetable ``position`` (0..1) and ``phase`` (0..1)."""
        fi = position * (self.num_frames - 1)
        i0 = int(np.floor(fi))
        i1 = min(self.num_frames - 1, i0 + 1)
        frac = fi - i0
        row = (1.0 - frac) * self.frames[i0] + frac * self.frames[i1]
        pi = phase * self.frame_size
        j0 = int(np.floor(pi)) % self.frame_size
        j1 = (j0 + 1) % self.frame_size
        pf = pi - np.floor(pi)
        return float((1.0 - pf) * row[j0] + pf * row[j1])

    def scan(self, position: np.ndarray, phase: np.ndarray) -> np.ndarray:
        """Vectorised scan over arrays of ``position`` and ``phase`` (same length)."""
        n = position.size
        out = np.empty(n, dtype=np.float64)
        fi = np.clip(position, 0.0, 1.0) * (self.num_frames - 1)
        i0 = np.floor(fi).astype(np.int64)
        i1 = np.clip(i0 + 1, 0, self.num_frames - 1)
        frac = fi - i0
        pi = np.clip(phase, 0.0, None) * self.frame_size
        j0 = np.floor(pi).astype(np.int64) % self.frame_size
        j1 = (j0 + 1) % self.frame_size
        pf = pi - np.floor(pi)
        # Index the pre-interpolated frame rows per sample. Using advanced
        # indexing frames[i0, j0] gives shape (n,) — memory-bounded by n only,
        # not by table size (22050 samples × 8 bytes ~ 176 KB, trivial).
        v0 = (1.0 - frac) * self.frames[i0, j0] + frac * self.frames[i1, j0]
        v1 = (1.0 - frac) * self.frames[i0, j1] + frac * self.frames[i1, j1]
        out = (1.0 - pf) * v0 + pf * v1
        return out


class WavetableSynth:
    """Oscillator that scans a wavetable at audio rate.

    Parameters
    ----------
    table : Wavetable
        The wavetable bank to scan.
    morph_lfo_rate : float
        Rate (Hz) of an internal LFO that sweeps the morph position. 0
        disables it (position stays at ``morph_position``).
    morph_position : float
        Static morph position (0..1) when no LFO is active.
    """

    def __init__(self, table: Wavetable, morph_lfo_rate: float = 0.2, morph_position: float = 0.0) -> None:
        self.table = table
        self.morph_lfo_rate = float(morph_lfo_rate)
        self.morph_position = float(np.clip(morph_position, 0.0, 1.0))

    def render(self, freq: float, duration: float, sr: int, env: ADSR | None = None) -> np.ndarray:
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        phase = (freq * t) % 1.0
        if self.morph_lfo_rate > 1e-6:
            morph = 0.5 + 0.5 * np.sin(2.0 * np.pi * self.morph_lfo_rate * t + self.morph_position)
        else:
            morph = np.full(n, self.morph_position, dtype=np.float64)
        out = self.table.scan(morph, phase)
        if env is not None:
            e = env.render(duration, sr)
            if e.size < n:
                e = np.pad(e, (0, n - e.size))
            elif e.size > n:
                e = e[:n]
            out = out * e
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)


class MorphWavetable(Wavetable):
    """Pre-built wavetable that morphs through sine→saw→square→noise."""

    def __init__(self, size: int = 2048, num_frames: int = 32, seed: int = 0) -> None:
        sine = _sine_table(size)
        saw = _saw_table(size)
        square = _square_table(size)
        noise = _noise_table(size, seed=seed)
        frames = np.empty((num_frames, size), dtype=np.float64)
        # Interpolate across 4 key waveforms.
        keys = np.array([sine, saw, square, noise])
        for i in range(num_frames):
            p = i / max(num_frames - 1, 1) * (keys.shape[0] - 1)
            i0 = int(np.floor(p))
            i1 = min(keys.shape[0] - 1, i0 + 1)
            frac = p - i0
            frames[i] = (1.0 - frac) * keys[i0] + frac * keys[i1]
        super().__init__(frames)
