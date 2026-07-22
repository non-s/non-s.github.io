"""Procedural white/pink/brown noise for baby-sleep & focus ambience
(acting-founder growth pass, 2026-07-22).

Sibling module to utils/storm_audio.py -- same exactly-periodic-by-
construction technique (a magnitude spectrum shaped in the frequency
domain, uniform-random phases per bin, inverse real FFT; a spectrum
defined only at bin frequencies k/n_samples produces a signal whose
period is exactly n_samples, so looping it via -stream_loop has no seam
to begin with, no crossfade needed), generalized to the three standard
"noise colors" instead of one rain-specific shape:

  - white: flat power spectral density (0 dB/octave) -- magnitude ~ f**0
  - pink:  PSD ~ 1/f (-3 dB/octave)                  -- magnitude ~ f**-0.5
  - brown: PSD ~ 1/f**2 (-6 dB/octave, aka "red")    -- magnitude ~ f**-1.0

(PSD is the squared magnitude, so a magnitude law of f**-k gives a PSD
law of f**-2k -- the exponents above follow directly.) utils/storm_audio.py's
existing `_periodic_noise` already happens to use exactly the pink-noise
exponent (`1.0 / sqrt(f)`) for its rain "wash" layer; `_periodic_colored_noise`
below generalizes that one function to all three colors via an explicit
exponent parameter instead of duplicating it three times.

Why this pillar instead of more rain/thunder content: parents needing
white/brown noise to get a baby to sleep are a purely functional,
massive, evergreen search audience this channel doesn't specifically
serve yet -- the rain pillar's own utils/storm_branding.py already lists
"baby sleep" and "tinnitus" scenes, but its audio is rain/thunder texture,
not the plain noise-color product this specific audience actually
searches for and expects (many parents specifically want brown noise,
not rain, because it's closer to in-womb sound and less "eventful" than
rain's droplet texture). Same brand ("Amber Hours") as the rain pillar,
not a new one like "Pata Jazz" -- the promise ("real ambient sound to
help you sleep/focus/calm down") is identical, just a different
scene/audience within it.

No thunder, no droplet texture, no music layer -- deliberately just
noise, since that's the actual product this audience searches for. A
very shallow, barely-perceptible amplitude swell (`_periodic_envelope`,
much shallower depth than the rain pillar's) keeps a long loop from
reading as an obviously static, digitally-perfect tone without making it
sound "breathing" or synthetic -- steady is the whole point for this
audience, unlike rain's louder, more organic swell.
"""

from __future__ import annotations

import numpy as np

from utils.storm_audio import SAMPLE_RATE, write_wav  # noqa: F401 (re-exported for callers)

__all__ = ["SAMPLE_RATE", "write_wav", "generate_noise_bed", "NOISE_COLORS"]

# magnitude ~ f**-exponent; PSD ~ f**-(2*exponent). See module docstring.
NOISE_COLORS: dict[str, float] = {"white": 0.0, "pink": 0.5, "brown": 1.0}


def _periodic_colored_noise(
    n_samples: int, seed: int, *, exponent: float, low_hz: float = 20.0, high_hz: float = 18000.0
) -> np.ndarray:
    """Same construction as utils/storm_audio.py's `_periodic_noise`,
    generalized with an explicit spectral-slope exponent instead of a
    hardcoded pink-noise shape. See module docstring for the exponent ->
    noise-color mapping."""
    rng = np.random.default_rng(seed)
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / SAMPLE_RATE)
    magnitude = np.zeros_like(freqs)
    band = (freqs >= low_hz) & (freqs <= high_hz)
    if exponent == 0:
        magnitude[band] = 1.0
    else:
        with np.errstate(divide="ignore"):
            magnitude[band] = 1.0 / np.power(np.maximum(freqs[band], 1.0), exponent)
    phases = rng.uniform(0, 2 * np.pi, size=freqs.shape)
    spectrum = magnitude * np.exp(1j * phases)
    signal = np.fft.irfft(spectrum, n=n_samples)
    peak = np.max(np.abs(signal)) or 1.0
    return (signal / peak).astype(np.float64)


def _periodic_envelope(
    n_samples: int, seed: int, *, cycles: tuple[int, ...] = (2, 3), depth: float = 0.05
) -> np.ndarray:
    """Same technique as utils/storm_audio.py's identical helper, much
    shallower `depth` (0.05 vs rain's 0.18): this audience wants *steady*
    noise, not an audible "breathing" swell -- just enough variation that
    a long loop doesn't read as a perfectly static, obviously-synthetic
    tone, without drawing attention to itself the way rain's louder swell
    deliberately does."""
    rng = np.random.default_rng(seed + 1)
    t = np.linspace(0, 1, n_samples, endpoint=False)
    envelope = np.ones(n_samples)
    for cycle in cycles:
        phase = rng.uniform(0, 2 * np.pi)
        weight = depth / len(cycles)
        envelope += weight * np.sin(2 * np.pi * cycle * t + phase)
    return np.clip(envelope, 1 - depth, 1 + depth)


def generate_noise_bed(
    duration_s: float = 60.0, *, seed: int = 0, color: str = "brown", level: float = 0.6
) -> np.ndarray:
    """Build one seamless stereo loop: (n_samples, 2) float64 in [-1, 1].

    `color` must be one of NOISE_COLORS ("white", "pink", "brown"). L/R
    channels are independently synthesized (different seeds) for stereo
    width, same as utils/storm_audio.py's generate_rain_bed.
    """
    if color not in NOISE_COLORS:
        raise ValueError(f"Unknown noise color {color!r}; must be one of {sorted(NOISE_COLORS)}")
    exponent = NOISE_COLORS[color]
    n_samples = int(duration_s * SAMPLE_RATE)
    left = _periodic_colored_noise(n_samples, seed, exponent=exponent) * _periodic_envelope(n_samples, seed)
    right = _periodic_colored_noise(n_samples, seed + 1000, exponent=exponent) * _periodic_envelope(
        n_samples, seed + 1000
    )
    bed = np.stack([left, right], axis=1) * level
    peak = np.max(np.abs(bed)) or 1.0
    if peak > 0.98:
        bed = bed / peak * 0.98
    return bed
