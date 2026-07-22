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

The first real upload made it obvious that a *pure* shaped-noise bed
(the original version of `_periodic_noise`, still used underneath as a
quiet base "wash") reads as flat static/hiss, not rain -- a continuous
colored-noise signal has no time-domain texture, and texture is exactly
what a listener uses to tell "rain" from "detuned radio." Real rain is a
wash *plus* a dense scatter of short, sparse-but-audible droplet
transients riding on top of it (higher crest factor / more "grain").
`_rain_droplets` adds that: thousands of short filtered-noise grains
placed at random offsets *inside* a fixed-length buffer, wrapping any
grain that overhangs the far end back to sample 0 (`% n_samples`) so the
grain-scatter buffer is exactly as loop-safe as the spectral wash, by the
same "one fixed-length buffer repeated" logic -- no discontinuity is
possible since nothing about the construction singles out sample 0 or
sample n-1 as special.

No API key, network call, or external asset required -- this works
standalone. generate_storm_ambience.py renders this loop's WAV as the
entire audio bed -- no music layer (chat, 2026-07-22: an optional quiet
Jamendo layer was tried and dropped; Jamendo's catalog is music, not
sound effects, so it never delivered rain sound, just extra complexity).
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


def _rain_droplets(
    n_samples: int,
    seed: int,
    *,
    density_per_s: float = 550.0,
    grain_variants: int = 40,
) -> np.ndarray:
    """A dense scatter of short filtered-noise "droplet" grains, exactly
    periodic over `n_samples` by construction: every grain is added into
    a fixed-length buffer with its index wrapped `% n_samples`, so a grain
    that overhangs the far end simply continues from sample 0 -- the
    buffer never has a seam to begin with, whether or not any individual
    grain straddles the wrap point.

    This is what turns the flat wash from `_periodic_noise` into
    something a listener actually recognizes as rain: individual drop
    transients (short, high-passed, fast-decay clicks) at random
    times/amplitudes, dense enough to read as continuous but with real
    time-domain grain -- the opposite of stationary hiss.
    """
    rng = np.random.default_rng(seed + 5000)
    duration_s = n_samples / SAMPLE_RATE
    count = max(0, int(duration_s * density_per_s))
    buffer = np.zeros(n_samples)
    if count == 0:
        return buffer

    max_grain_len = max(2, int(0.014 * SAMPLE_RATE))
    min_grain_len = max(1, int(0.003 * SAMPLE_RATE))
    grains: list[np.ndarray] = []
    for _ in range(grain_variants):
        grain_len = int(rng.integers(min_grain_len, max_grain_len + 1))
        noise = rng.uniform(-1, 1, size=grain_len)
        # A crude high-pass (first difference) gives the noise a "ticky"
        # character; a light low-pass afterward rounds off the harshest
        # edge without erasing the transient -- the combination reads as
        # a short droplet click, not a pop or a hiss.
        highpassed = np.diff(noise, prepend=0.0)
        grain = _one_pole_lowpass(highpassed, cutoff_hz=float(rng.uniform(2000.0, 6000.0)))
        t = np.arange(grain_len) / SAMPLE_RATE
        decay = np.exp(-t / rng.uniform(0.003, 0.012))
        grain = grain * decay
        peak = np.max(np.abs(grain)) or 1.0
        grains.append(grain / peak)

    starts = rng.integers(0, n_samples, size=count)
    variants = rng.integers(0, grain_variants, size=count)
    # Exponential amplitude spread: mostly quiet drops, occasional louder
    # "splash" -- a real crest-factor spread, not a uniform blur.
    amps = np.clip(rng.exponential(scale=0.35, size=count), 0.0, 1.4)

    for start, variant_idx, amp in zip(starts, variants, amps):
        grain = grains[variant_idx]
        idx = (start + np.arange(grain.shape[0])) % n_samples
        np.add.at(buffer, idx, grain * amp)

    peak = np.max(np.abs(buffer)) or 1.0
    return buffer / peak


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
    # Quiet, duller "wash" (a low body underneath) plus a dense droplet
    # scatter (the actual textured "rain" character) -- a pure wash alone
    # is what read as flat static/hiss on the first real upload; see this
    # module's docstring.
    wash_left = _periodic_noise(n_samples, seed, high_hz=2500.0) * _periodic_envelope(n_samples, seed)
    wash_right = _periodic_noise(n_samples, seed + 1000, high_hz=2500.0) * _periodic_envelope(n_samples, seed + 1000)
    drops_left = _rain_droplets(n_samples, seed + 4000)
    drops_right = _rain_droplets(n_samples, seed + 4100)
    left = wash_left * 0.35 + drops_left * 0.9
    right = wash_right * 0.35 + drops_right * 0.9
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
