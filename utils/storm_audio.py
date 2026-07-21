"""Procedural rain + distant-thunder ambience (growth pass, 2026-07-21).

Real "rain sounds for sleep" / "thunderstorm ambience" channels are one of
YouTube's biggest evergreen, non-lofi-saturated formats -- see the chat
that picked this direction over another lofi variant. Every channel doing
this loops a *recorded* rain sample; this synthesizes one instead, so
there is no recording to license, clear, or run out of, and the exact
same technique that makes utils/brand_motion.py's video loops seamless
(an integer number of cycles across the loop) has a direct audio
equivalent: a noise bed built by inverse-FFT of a shaped spectrum with
random phases is *exactly* periodic over the block length used, by
construction -- period-N samples in, period-N samples out, no crossfade
needed. Thunder is layered on top as short, contained bursts (not part of
the periodic bed), positioned with margin so no burst's tail is cut by
the loop seam.

No API key, network call, or external asset required -- this works
standalone. generate_storm_ambience.py renders this loop's WAV as the
audio bed and mixes it under an optional quiet Jamendo track.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44100


def _periodic_noise(n_samples: int, seed: int, *, low_hz: float = 20.0, high_hz: float = 7000.0) -> np.ndarray:
    """A mono noise signal that is *exactly* periodic over `n_samples`.

    Built by shaping a magnitude spectrum (pink-ish: energy ~ 1/sqrt(f),
    the classic rain/hiss shape) between `low_hz` and `high_hz`, assigning
    uniform-random phases per bin, and taking the inverse real FFT.
    `numpy.fft.irfft` of a spectrum defined only at bin frequencies
    k/n_samples produces a signal whose period is exactly `n_samples` --
    concatenating the result with itself has no seam, by construction.
    """
    rng = np.random.default_rng(seed)
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / SAMPLE_RATE)
    magnitude = np.zeros_like(freqs)
    band = (freqs >= low_hz) & (freqs <= high_hz)
    with np.errstate(divide="ignore"):
        magnitude[band] = 1.0 / np.sqrt(np.maximum(freqs[band], 1.0))
    phases = rng.uniform(0, 2 * np.pi, size=freqs.shape)
    spectrum = magnitude * np.exp(1j * phases)
    signal = np.fft.irfft(spectrum, n=n_samples)
    peak = np.max(np.abs(signal)) or 1.0
    return (signal / peak).astype(np.float64)


def _periodic_envelope(
    n_samples: int, seed: int, *, cycles: tuple[int, ...] = (2, 5), depth: float = 0.18
) -> np.ndarray:
    """A slow, organic-feeling amplitude swell around 1.0, built from a
    couple of low-integer-cycle sine components so it stays exactly
    periodic over `n_samples` too -- rain that never varies in intensity
    reads as an obvious loop; this keeps the variation loop-safe."""
    rng = np.random.default_rng(seed + 1)
    t = np.linspace(0, 1, n_samples, endpoint=False)
    envelope = np.ones(n_samples)
    for cycle in cycles:
        phase = rng.uniform(0, 2 * np.pi)
        weight = depth / len(cycles)
        envelope += weight * np.sin(2 * np.pi * cycle * t + phase)
    return np.clip(envelope, 1 - depth, 1 + depth)


def _one_pole_lowpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    """Simple recursive low-pass -- cheap and enough to turn broadband
    noise into a dull, distant "rumble" for thunder; no scipy dependency
    needed for a filter this simple."""
    alpha = 1.0 - np.exp(-2 * np.pi * cutoff_hz / SAMPLE_RATE)
    out = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        out[i] = acc
    return out


def _thunder_burst(seed: int, *, duration_s: float = 3.5) -> np.ndarray:
    """One contained rumble: a noise burst, low-passed for a dull boom,
    with a fast attack / slow decay envelope and a slow secondary
    modulation for a "rolling thunder" character."""
    n = int(duration_s * SAMPLE_RATE)
    rng = np.random.default_rng(seed)
    noise = rng.uniform(-1, 1, size=n)
    rumble = _one_pole_lowpass(noise, cutoff_hz=120.0)
    t = np.linspace(0, 1, n, endpoint=False)
    attack = np.clip(t / 0.03, 0, 1)
    decay = np.exp(-t * 2.2)
    roll = 1 + 0.35 * np.sin(2 * np.pi * rng.uniform(1.5, 3.0) * t)
    envelope = attack * decay * roll
    burst = rumble * envelope
    peak = np.max(np.abs(burst)) or 1.0
    return burst / peak


def generate_rain_bed(
    duration_s: float = 60.0,
    *,
    seed: int = 0,
    thunder_count: int = 2,
    rain_level: float = 0.55,
    thunder_level: float = 0.5,
) -> np.ndarray:
    """Build one seamless stereo loop: (n_samples, 2) float64 in [-1, 1].

    L/R channels are independently synthesized (different seeds) for
    stereo width; thunder bursts share timing across channels but are
    generated independently too. Bursts are kept with margin from both
    ends of the loop so a burst's tail is never cut by the wrap.
    """
    n_samples = int(duration_s * SAMPLE_RATE)
    left = _periodic_noise(n_samples, seed) * _periodic_envelope(n_samples, seed)
    right = _periodic_noise(n_samples, seed + 1000) * _periodic_envelope(n_samples, seed + 1000)
    bed = np.stack([left, right], axis=1) * rain_level

    rng = np.random.default_rng(seed + 2000)
    margin_s = 4.5
    for i in range(max(0, thunder_count)):
        burst_seed = seed + 3000 + i
        burst = _thunder_burst(burst_seed, duration_s=rng.uniform(2.5, 4.5))
        latest_start_s = duration_s - margin_s - len(burst) / SAMPLE_RATE
        if latest_start_s <= margin_s:
            continue
        start_s = rng.uniform(margin_s, latest_start_s)
        start = int(start_s * SAMPLE_RATE)
        pan = rng.uniform(0.3, 0.7)
        end = start + len(burst)
        bed[start:end, 0] += burst * pan * thunder_level
        bed[start:end, 1] += burst * (1 - pan) * thunder_level

    peak = np.max(np.abs(bed)) or 1.0
    if peak > 0.98:
        bed = bed / peak * 0.98
    return bed


def write_wav(samples: np.ndarray, path: Path, *, sample_rate: int = SAMPLE_RATE) -> None:
    """Write a (n_samples, 2) float64 [-1, 1] array as a 16-bit PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    ints = (clipped * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(ints.tobytes())
