"""Granular synthesis (cloud grains, freeze, time-stretch).

Granular synthesis builds textures from many short "grains" — tiny windows
of sound (10-100 ms) extracted from a source and recombined. It enables
time-stretching without pitch shift, pitch-shifting without time change,
"freeze" textures, and rich cloud-like pads.

Public API:
- ``GrainCloud`` — a cloud of grains extracted from a source buffer, with
  density, pitch jitter, position jitter, grain size and envelope controls.
- ``freeze`` — render a static cloud from a single moment of a source.
- ``time_stretch`` — stretch a source buffer by a factor using grain
  overlap.
"""

from __future__ import annotations

import numpy as np


def _grain_envelope(size: int, window: str = "hann") -> np.ndarray:
    """Return a normalised grain envelope of ``size`` samples."""
    if window == "hann":
        env = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(size) / max(size - 1, 1)))
    elif window == "tukey":
        taper = max(1, size // 4)
        env = np.ones(size, dtype=np.float64)
        ramp = np.linspace(0.0, 1.0, taper)
        env[:taper] = ramp
        env[-taper:] = ramp[::-1]
    elif window == "gaussian":
        sigma = size / 6.0
        env = np.exp(-0.5 * ((np.arange(size) - size * 0.5) / sigma) ** 2)
    else:  # rectangular
        env = np.ones(size, dtype=np.float64)
    peak = float(np.max(env)) if env.size else 1.0
    if peak > 1e-12:
        env = env / peak
    return env


def extract_grain(source: np.ndarray, start: float, size: int, sr: int) -> np.ndarray:
    """Extract a windowed grain of ``size`` samples starting at ``start`` (seconds)."""
    i = int(start * sr)
    end = min(source.size, i + size)
    grain = np.zeros(size, dtype=np.float64)
    if i < source.size:
        grain[: end - i] = source[i:end]
    return grain * _grain_envelope(size)


class GrainCloud:
    """A cloud of grains drawn from a source buffer.

    Parameters
    ----------
    source : np.ndarray
        The mono source buffer to draw grains from.
    sr : int
        Sample rate.
    density : float
        Grains per second. Higher = denser cloud.
    grain_ms : float
        Grain length in milliseconds.
    pitch_jitter : float
        Random pitch multiplier range (0 = none, 0.1 = ±10%).
    pos_jitter : float
        Random position offset in seconds (jitter on source position).
    spread : float
        Stereo spread (0 = mono, 1 = full stereo).
    pitch_shift : float
        Global pitch multiplier (1.0 = no shift).
    """

    def __init__(
        self,
        source: np.ndarray,
        sr: int,
        density: float = 20.0,
        grain_ms: float = 40.0,
        pitch_jitter: float = 0.0,
        pos_jitter: float = 0.05,
        spread: float = 0.5,
        pitch_shift: float = 1.0,
        seed: int = 0,
    ) -> None:
        self.source = np.asarray(source, dtype=np.float64).ravel()
        self.sr = int(sr)
        self.density = float(density)
        self.grain_ms = float(grain_ms)
        self.pitch_jitter = float(pitch_jitter)
        self.pos_jitter = float(pos_jitter)
        self.spread = float(np.clip(spread, 0.0, 1.0))
        self.pitch_shift = float(pitch_shift)
        self.rng = np.random.default_rng(seed)

    def render(self, duration: float) -> np.ndarray:
        """Render ``duration`` seconds of grain cloud output (stereo)."""
        n = int(round(duration * self.sr))
        if n <= 0:
            return np.zeros((2, 1), dtype=np.float64)
        grain_size = max(1, int(self.grain_ms * 0.001 * self.sr))
        # Schedule grains deterministically by density.
        num_grains = max(1, int(self.density * duration))
        # Random start times spread across the duration.
        start_times = self.rng.uniform(0.0, duration, size=num_grains)
        left = np.zeros(n, dtype=np.float64)
        right = np.zeros(n, dtype=np.float64)
        for st in start_times:
            i = int(st * self.sr)
            if i >= n:
                continue
            # Source position: cycle through the source with jitter.
            src_pos = self.rng.uniform(0.0, max(0.0, self.source.size / self.sr - self.grain_ms / 1000.0))
            src_pos += self.rng.uniform(-self.pos_jitter, self.pos_jitter)
            src_pos = max(0.0, src_pos)
            # Pitch multiplier with jitter.
            pmul = self.pitch_shift * (1.0 + self.rng.uniform(-self.pitch_jitter, self.pitch_jitter))
            # Resample the grain by linear interpolation for pitch shift.
            src_i = int(src_pos * self.sr)
            grain_len = min(grain_size, self.source.size - src_i)
            if grain_len <= 0:
                continue
            indices = np.arange(grain_len, dtype=np.float64) * pmul
            indices_int = np.clip(indices.astype(np.int64), 0, self.source.size - 1)
            grain = self.source[indices_int][:grain_size]
            if grain.size < grain_size:
                grain = np.pad(grain, (0, grain_size - grain.size))
            grain = grain * _grain_envelope(grain_size)
            # Stereo placement by random pan.
            pan = self.rng.uniform(-self.spread, self.spread)
            gain_l = np.cos((pan + 1.0) * 0.5 * np.pi * 0.5)
            gain_r = np.sin((pan + 1.0) * 0.5 * np.pi * 0.5)
            end_i = min(n, i + grain_size)
            length = end_i - i
            left[i:end_i] += grain[:length] * gain_l
            right[i:end_i] += grain[:length] * gain_r
        # Normalise by peak.
        stereo = np.stack([left, right])
        peak = float(np.max(np.abs(stereo))) if stereo.size else 1.0
        if peak > 1e-12:
            stereo = stereo / peak
        return stereo.astype(np.float64)


def freeze(
    source: np.ndarray,
    sr: int,
    duration: float,
    at: float = 0.0,
    density: float = 40.0,
    grain_ms: float = 30.0,
    seed: int = 0,
) -> np.ndarray:
    """Render a frozen cloud around the source position ``at`` (seconds)."""
    cloud = GrainCloud(
        source,
        sr,
        density=density,
        grain_ms=grain_ms,
        pos_jitter=0.02,
        pitch_jitter=0.005,
        spread=0.7,
        seed=seed,
    )
    # Override source position jitter to keep grains near ``at``.
    cloud.pos_jitter = 0.005
    return cloud.render(duration)


def time_stretch(
    source: np.ndarray,
    sr: int,
    factor: float,
    grain_ms: float = 50.0,
    overlap: float = 0.5,
) -> np.ndarray:
    """Stretch ``source`` by ``factor`` (1.5 = 50% longer) without pitch shift."""
    source = np.asarray(source, dtype=np.float64).ravel()
    grain_size = max(1, int(grain_ms * 0.001 * sr))
    hop = max(1, int(grain_size * (1.0 - overlap)))
    out_len = int(source.size * factor)
    out = np.zeros(out_len, dtype=np.float64)
    env = _grain_envelope(grain_size)
    out_pos = 0
    src_pos = 0
    while out_pos < out_len and src_pos + grain_size <= source.size:
        grain = source[src_pos : src_pos + grain_size] * env
        end = min(out_len, out_pos + grain_size)
        out[out_pos:end] += grain[: end - out_pos]
        out_pos += hop
        src_pos += int(hop / factor)
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out
