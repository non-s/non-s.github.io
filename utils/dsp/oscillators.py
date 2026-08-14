"""Pure-numpy oscillators for the Liquid Wire universal music engine.

All oscillators are bandlimited where it matters (saw/square/triangle use
additive synthesis up to Nyquist) and operate entirely on procedural math:
no external samples, IRs or soundfonts are loaded. Every function returns a
``np.ndarray`` of dtype float64 centred around zero (roughly [-1, 1]).
"""

from __future__ import annotations

import numpy as np


def _time_vector(dur: float, sr: int) -> np.ndarray:
    """Return a float64 sample-index time vector for ``dur`` seconds at ``sr``."""
    n = int(round(dur * sr))
    return np.arange(n, dtype=np.float64) / float(sr)


def sine(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Pure sine wave at ``freq`` Hz lasting ``dur`` seconds."""
    t = _time_vector(dur, sr)
    return np.sin(2.0 * np.pi * freq * t + phase).astype(np.float64)


def _additive(freq: float, dur: float, sr: int, phase: float, harmonic_amp, harmonic_sign) -> np.ndarray:
    """Additive-synthesis helper used by saw/square/triangle.

    ``harmonic_amp(k)`` returns the amplitude of harmonic ``k`` (1-indexed) and
    ``harmonic_sign(k)`` returns +1/-1 to alternate the sign per harmonic.
    Harmonics above Nyquist are skipped automatically.
    """
    t = _time_vector(dur, sr)
    nyquist = sr / 2.0
    out = np.zeros_like(t)
    k = 1
    while True:
        f_k = freq * k
        if f_k >= nyquist:
            break
        amp = harmonic_amp(k)
        if amp <= 0.0:
            k += 1
            continue
        out += harmonic_sign(k) * amp * np.sin(2.0 * np.pi * f_k * t + phase * k)
        k += 1
    # Normalise to roughly [-1, 1] regardless of harmonic count.
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out.astype(np.float64)


def sawtooth(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Bandlimited sawtooth via additive synthesis (1/k amplitudes)."""
    return _additive(
        freq,
        dur,
        sr,
        phase,
        harmonic_amp=lambda k: 1.0 / k,
        harmonic_sign=lambda k: 1.0,
    )


def square(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Bandlimited square via additive synthesis (odd harmonics only)."""
    return _additive(
        freq,
        dur,
        sr,
        phase,
        harmonic_amp=lambda k: (1.0 / k) if (k % 2 == 1) else 0.0,
        harmonic_sign=lambda k: 1.0,
    )


def triangle(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Bandlimited triangle via additive synthesis (odd harmonics, 1/k^2)."""
    return _additive(
        freq,
        dur,
        sr,
        phase,
        harmonic_amp=lambda k: (1.0 / (k * k)) if (k % 2 == 1) else 0.0,
        harmonic_sign=lambda k: 1.0 if ((k - 1) // 2) % 2 == 0 else -1.0,
    )


def pulse(freq: float, dur: float, sr: int, pulse_width: float = 0.5, phase: float = 0.0) -> np.ndarray:
    """Variable-width bandlimited pulse via difference of two phase-shifted saws."""
    pw = float(np.clip(pulse_width, 1e-3, 1.0 - 1e-3))
    # A pulse of width pw = difference of two saws offset by pw*period.
    # Phase offset (in radians) = 2*pi*pw.
    saw_a = sawtooth(freq, dur, sr, phase=phase)
    saw_b = sawtooth(freq, dur, sr, phase=phase + 2.0 * np.pi * pw)
    out = saw_a - saw_b
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out.astype(np.float64)


def supersaw(
    freq: float,
    dur: float,
    sr: int,
    detune: float = 0.12,
    voices: int = 7,
    phase: float = 0.0,
) -> np.ndarray:
    """Multiple detuned sawtooths summed (supersaw).

    ``detune`` is the maximum semitone spread; ``voices`` saws are spread
    symmetrically around ``freq`` and equal-power summed.
    """
    v = max(1, int(voices))
    if v == 1:
        return sawtooth(freq, dur, sr, phase=phase)
    # Symmetric linear spread in semitones.
    spread = np.linspace(-detune, detune, v)
    out = np.zeros(int(round(dur * sr)), dtype=np.float64)
    for s in spread:
        f_v = freq * (2.0 ** (s / 12.0))
        out += sawtooth(f_v, dur, sr, phase=phase)
    out /= float(v)
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out.astype(np.float64)


def noise_white(dur: float, sr: int, seed: int | None = None) -> np.ndarray:
    """White noise; deterministic when ``seed`` is provided."""
    n = int(round(dur * sr))
    rng = np.random.default_rng(seed)
    return rng.standard_normal(n).astype(np.float64)


def noise_pink(dur: float, sr: int, seed: int | None = None) -> np.ndarray:
    """Pink noise via the Voss-McCartney algorithm (sum of randomised octaves)."""
    n = int(round(dur * sr))
    rng = np.random.default_rng(seed)
    # Number of octave "rows": each row updates at a different power-of-2 stride.
    rows = 16
    # Start with all rows holding a random value; update row i every 2**i samples.
    values = rng.standard_normal(rows)
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        # Update rows whose stride divides i.
        for r in range(rows):
            if (i & ((1 << r) - 1)) == 0:
                values[r] = rng.standard_normal()
        out[i] = values.sum()
    # Normalise to [-1, 1].
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out.astype(np.float64)


def noise_brown(dur: float, sr: int, seed: int | None = None) -> np.ndarray:
    """Brown noise: integrated white noise (random walk)."""
    n = int(round(dur * sr))
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(n).astype(np.float64)
    # Leaky integrator so the walk stays bounded over long durations.
    out = np.empty(n, dtype=np.float64)
    acc = 0.0
    leak = 0.997
    for i in range(n):
        acc = acc * leak + white[i]
        out[i] = acc
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out.astype(np.float64)


def fm(
    carrier_freq: float,
    modulator_freq: float,
    dur: float,
    sr: int,
    mod_index: float = 1.0,
    phase: float = 0.0,
) -> np.ndarray:
    """Simple FM synthesis: carrier phase modulated by a sine modulator."""
    t = _time_vector(dur, sr)
    modulator = mod_index * np.sin(2.0 * np.pi * modulator_freq * t)
    out = np.sin(2.0 * np.pi * carrier_freq * t + modulator + phase)
    return out.astype(np.float64)
