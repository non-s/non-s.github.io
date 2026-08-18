"""Pure-numpy oscillators for the Liquid Wire universal music engine.

All oscillators are bandlimited where it matters (saw/square/triangle use
additive synthesis up to Nyquist) and operate entirely on procedural math:
no external samples, IRs or soundfonts are loaded. Every function returns a
``np.ndarray`` of dtype float64 centred around zero (roughly [-1, 1]).
"""

from __future__ import annotations

import numpy as np

# Frequencies at or below this are sub-audio (LFOs, vibrato, control signals).
# For these the bandlimited additive path would iterate up to ~nyquist/freq
# harmonics (e.g. 44100/0.5 = 88200 iterations for a 0.5 Hz triangle), which
# is both wasteful — aliasing is inaudible below ~20 Hz — and slow enough to
# dominate render time (a 0.5 Hz Phaser LFO took ~4s before this fast path).
# Sub-audio oscillators use direct geometric waveforms instead.
_SUBAUDIO_HZ = 20.0


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

    Vectorised: the per-harmonic amplitude/sign lookups and the Nyquist bound
    are computed once over the full harmonic range via numpy arrays instead of
    a Python ``while`` loop calling ``harmonic_amp``/``harmonic_sign`` once per
    harmonic. The previous per-harmonic Python loop dominated render time for
    low notes (a 65 Hz supersaw spent ~9s here per note) because each iteration
    allocated a fresh ``np.sin`` array and incurred Python/lambda overhead ~220
    times. The output is numerically identical (max abs diff ~1e-11).
    """
    t = _time_vector(dur, sr)
    nyquist = sr / 2.0
    # Upper bound on harmonic index before crossing Nyquist.
    k_max = max(1, int(nyquist // max(freq, 1e-9)))
    k = np.arange(1, k_max + 1, dtype=np.float64)
    f_k = freq * k
    # Drop harmonics above Nyquist (bound is inclusive of f_k < nyquist).
    valid = f_k < nyquist
    k = k[valid]
    f_k = f_k[valid]
    if k.size == 0:
        return np.zeros_like(t)
    # Evaluate the amplitude/sign callables vectorised over all harmonics at
    # once. The public callables (sawtooth/square/triangle) are written to
    # accept either a scalar or an array, so this is a single dispatch. A
    # callable returning a scalar (e.g. ``lambda k: 1.0``) is broadcast to the
    # harmonic count so downstream arithmetic works elementwise.
    amps = np.asarray(harmonic_amp(k), dtype=np.float64).ravel()
    signs = np.asarray(harmonic_sign(k), dtype=np.float64).ravel()
    if amps.size == 1 and k.size > 1:
        amps = np.full(k.shape, float(amps[0]), dtype=np.float64)
    if signs.size == 1 and k.size > 1:
        signs = np.full(k.shape, float(signs[0]), dtype=np.float64)
    keep = amps > 0.0
    if not np.any(keep):
        return np.zeros_like(t)
    k = k[keep]
    f_k = f_k[keep]
    amps = amps[keep]
    signs = signs[keep]
    # Sum the sinusoidal harmonics. A single 2D sin over (harmonics, samples)
    # would allocate k.size * t.size float64 (e.g. 220 * 190k = 335 MB for a
    # low note) and is slower than the streaming sum because it blows the
    # cache. Accumulate in a float64 buffer one harmonic at a time instead:
    # this stays in cache, matches the previous numeric output to ~1e-11 and
    # is ~30-50% faster in practice than the materialised 2D path.
    out = np.zeros_like(t)
    two_pi = 2.0 * np.pi
    coeffs = signs * amps
    phase_k = phase * k
    for i in range(k.size):
        out += coeffs[i] * np.sin(two_pi * f_k[i] * t + phase_k[i])
    # Normalise to roughly [-1, 1] regardless of harmonic count.
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out.astype(np.float64)


def _phase_index(freq: float, dur: float, sr: int, phase: float) -> np.ndarray:
    """Return the normalised phase progress in [0, 1) for ``freq`` Hz."""
    n = int(round(dur * sr))
    t = np.arange(n, dtype=np.float64) / float(sr)
    return (freq * t + phase / (2.0 * np.pi)) % 1.0


def _direct_saw(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Direct (non-bandlimited) saw: phase ramp from -1 to 1. Fast path for LFOs."""
    p = _phase_index(freq, dur, sr, phase)
    out = (2.0 * p - 1.0).astype(np.float64)
    return out


def _direct_square(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Direct (non-bandlimited) square: +1/-1 based on phase. Fast path for LFOs."""
    p = _phase_index(freq, dur, sr, phase)
    out = np.where(p < 0.5, 1.0, -1.0).astype(np.float64)
    return out


def _direct_triangle(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Direct (non-bandlimited) triangle: abs of phase. Fast path for LFOs."""
    p = _phase_index(freq, dur, sr, phase)
    out = (4.0 * np.abs(p - 0.5) - 1.0).astype(np.float64)
    return out


def sawtooth(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Bandlimited sawtooth via additive synthesis (1/k amplitudes).

    Sub-audio frequencies (``freq <= _SUBAUDIO_HZ``) take a direct geometric
    fast path: at those rates aliasing is inaudible, and the additive path
    would iterate up to ``nyquist/freq`` (e.g. 88200 iterations for 0.5 Hz)
    which dominates runtime for LFO-driven effects.
    """
    if 0.0 < freq <= _SUBAUDIO_HZ:
        return _direct_saw(freq, dur, sr, phase)
    return _additive(
        freq,
        dur,
        sr,
        phase,
        harmonic_amp=lambda k: 1.0 / k,
        harmonic_sign=lambda k: 1.0,
    )


def square(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Bandlimited square via additive synthesis (odd harmonics only).

    Sub-audio frequencies take the direct geometric fast path (see
    :func:`sawtooth`).
    """
    if 0.0 < freq <= _SUBAUDIO_HZ:
        return _direct_square(freq, dur, sr, phase)
    return _additive(
        freq,
        dur,
        sr,
        phase,
        harmonic_amp=lambda k: np.where(k % 2 == 1, 1.0 / k, 0.0),
        harmonic_sign=lambda k: 1.0,
    )


def triangle(freq: float, dur: float, sr: int, phase: float = 0.0) -> np.ndarray:
    """Bandlimited triangle via additive synthesis (odd harmonics, 1/k^2).

    Sub-audio frequencies take the direct geometric fast path (see
    :func:`sawtooth`).
    """
    if 0.0 < freq <= _SUBAUDIO_HZ:
        return _direct_triangle(freq, dur, sr, phase)
    return _additive(
        freq,
        dur,
        sr,
        phase,
        harmonic_amp=lambda k: np.where(k % 2 == 1, 1.0 / (k * k), 0.0),
        harmonic_sign=lambda k: np.where(((k - 1) // 2) % 2 == 0, 1.0, -1.0),
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
    """Pink noise via the Voss-McCartney algorithm (sum of randomised octaves).

    Vectorized: precomputes the update mask for each octave row and applies
    all updates in a single pass over the rows (16 rows regardless of n),
    giving O(rows * n) with numpy vectorised inner loops instead of O(n*rows)
    with Python-level branching per sample.
    """
    n = int(round(dur * sr))
    rng = np.random.default_rng(seed)
    # Number of octave "rows": each row updates at a different power-of-2 stride.
    rows = 16
    # For each row r, the update stride is 2**r. Precompute per-row value arrays
    # using a vectorised resample: row r contributes a value that changes every
    # 2**r samples. We generate one random per block and expand to length n.
    out = np.zeros(n, dtype=np.float64)
    for r in range(rows):
        stride = 1 << r
        # Number of distinct blocks for this row.
        n_blocks = (n + stride - 1) // stride
        values = rng.standard_normal(n_blocks)
        # Expand each block value to `stride` samples (last block may be short).
        row = np.repeat(values, stride)[:n]
        out += row
    # Normalise to [-1, 1].
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out.astype(np.float64)


def noise_brown(dur: float, sr: int, seed: int | None = None) -> np.ndarray:
    """Brown noise: integrated white noise (random walk), vectorized with cumsum."""
    n = int(round(dur * sr))
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(n).astype(np.float64)
    # Leaky integrator so the walk stays bounded over long durations.
    # Implemented as a vectorized exponential moving average:
    #   out[i] = leak * out[i-1] + white[i]
    # This is an IIR one-pole lowpass; use scipy.signal.lfilter for C speed.
    from scipy.signal import lfilter

    leak = 0.997
    b = np.array([1.0], dtype=np.float64)
    a = np.array([1.0, -leak], dtype=np.float64)
    out = lfilter(b, a, white).astype(np.float64)
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    if peak > 1e-12:
        out = out / peak
    return out


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
