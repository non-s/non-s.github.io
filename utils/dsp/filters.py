"""Biquad, ladder and formant filters for the Liquid Wire DSP engine.

Everything is implemented with pure numpy + stdlib (no scipy). The biquad
follows the standard RBJ Audio-EQ-Cookbook topology, the ladder is a 4-pole
Moog-style lowpass with one-pole RC sections and a global feedback gain, and
the formant filter banks three bandpass biquads tuned to vowel formants.
"""

from __future__ import annotations

import numpy as np

_VALID_BIQUAD_TYPES = {"lowpass", "highpass", "bandpass", "notch", "allpass"}

# Formant centre frequencies (Hz) and bandwidths (Hz) for the five cardinal
# vowels. Values are rounded approximations of measured adult-voice formants.
_FORMANTS: dict[str, list[tuple[float, float]]] = {
    "a": [(800.0, 130.0), (1150.0, 140.0), (2900.0, 200.0)],
    "e": [(400.0, 90.0), (1700.0, 110.0), (2600.0, 160.0)],
    "i": [(290.0, 80.0), (2300.0, 130.0), (3000.0, 180.0)],
    "o": [(500.0, 100.0), (900.0, 120.0), (2600.0, 170.0)],
    "u": [(320.0, 80.0), (800.0, 100.0), (2400.0, 160.0)],
}


def _biquad_coeffs(ftype: str, cutoff: float, q: float, sr: int) -> tuple[float, float, float, float, float, float]:
    """Return (b0, b1, b2, a1, a2, gain) for the requested RBJ biquad.

    Coefficients are normalised so that a0 = 1; ``gain`` is the leading
    coefficient used as the overall gain factor (== 1/a0).
    """
    w0 = 2.0 * np.pi * cutoff / float(sr)
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / (2.0 * q)

    if ftype == "lowpass":
        b0 = (1.0 - cos_w0) / 2.0
        b1 = 1.0 - cos_w0
        b2 = (1.0 - cos_w0) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif ftype == "highpass":
        b0 = (1.0 + cos_w0) / 2.0
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif ftype == "bandpass":
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif ftype == "notch":
        b0 = 1.0
        b1 = -2.0 * cos_w0
        b2 = 1.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif ftype == "allpass":
        b0 = 1.0 - alpha
        b1 = -2.0 * cos_w0
        b2 = 1.0 + alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    else:  # pragma: no cover - guarded by caller
        raise ValueError(f"unknown filter type: {ftype!r}")

    gain = 1.0 / a0
    return b0, b1, b2, a1, a2, gain


class BiquadFilter:
    """RBJ biquad implementing lowpass/highpass/bandpass/notch/allpass."""

    def __init__(self, filter_type: str, cutoff_hz: float, q: float, sample_rate: int) -> None:
        if filter_type not in _VALID_BIQUAD_TYPES:
            raise ValueError(f"filter_type must be one of {_VALID_BIQUAD_TYPES}, got {filter_type!r}")
        self.filter_type = filter_type
        self.sample_rate = int(sample_rate)
        self.cutoff_hz = float(cutoff_hz)
        self.q = float(q)
        self._recompute()
        # State (Direct Form I transposed).
        self._z1 = 0.0
        self._z2 = 0.0

    def _recompute(self) -> None:
        b0, b1, b2, a1, a2, gain = _biquad_coeffs(self.filter_type, self.cutoff_hz, self.q, self.sample_rate)
        self._b0 = b0 * gain
        self._b1 = b1 * gain
        self._b2 = b2 * gain
        self._a1 = a1 * gain
        self._a2 = a2 * gain

    def set_cutoff(self, cutoff_hz: float) -> None:
        self.cutoff_hz = float(cutoff_hz)
        self._recompute()

    def set_q(self, q: float) -> None:
        self.q = float(q)
        self._recompute()

    def process(self, signal: np.ndarray) -> np.ndarray:
        """Apply the filter to a 1-D float signal; returns a new array."""
        x = np.asarray(signal, dtype=np.float64).ravel()
        y = np.empty_like(x)
        b0, b1, b2 = self._b0, self._b1, self._b2
        a1, a2 = self._a1, self._a2
        z1, z2 = self._z1, self._z2
        for i in range(x.size):
            xn = x[i]
            yn = b0 * xn + z1
            z1 = b1 * xn - a1 * yn + z2
            z2 = b2 * xn - a2 * yn
            y[i] = yn
        self._z1 = z1
        self._z2 = z2
        return y


class LadderFilter:
    """4-pole Moog-style ladder lowpass with resonance feedback."""

    def __init__(self, cutoff_hz: float, resonance: float, sample_rate: int) -> None:
        self.sample_rate = int(sample_rate)
        self.cutoff_hz = float(cutoff_hz)
        self.resonance = float(np.clip(resonance, 0.0, 1.0))
        self._recompute()
        self._s = [0.0, 0.0, 0.0, 0.0]

    def _recompute(self) -> None:
        # Normalised cutoff (0..1 where 1 == Nyquist). Clamp to keep stable.
        fc = float(np.clip(self.cutoff_hz / (self.sample_rate * 0.5), 1e-4, 0.95))
        # One-pole RC coefficient: g = 1 - exp(-2*pi*fc).
        self._g = 1.0 - np.exp(-2.0 * np.pi * fc)
        # Resonance feedback gain (0..~3.9). Kept below 4 to avoid runaway.
        self._k = 3.9 * self.resonance

    def set_cutoff(self, cutoff_hz: float) -> None:
        self.cutoff_hz = float(cutoff_hz)
        self._recompute()

    def set_resonance(self, resonance: float) -> None:
        self.resonance = float(np.clip(resonance, 0.0, 1.0))
        self._recompute()

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        y = np.empty_like(x)
        g = self._g
        k = self._k
        s1, s2, s3, s4 = self._s
        for i in range(x.size):
            xn = x[i]
            # Feedback from the 4th stage output to the input (Moog-style).
            u = xn - k * s4
            # Four cascaded one-pole lowpass sections (RC integrators).
            s1 = s1 + g * (u - s1)
            s2 = s2 + g * (s1 - s2)
            s3 = s3 + g * (s2 - s3)
            s4 = s4 + g * (s3 - s4)
            y[i] = s4
        self._s = [s1, s2, s3, s4]
        return y


class FormantFilter:
    """Three-bandpass formant filter for vowel synthesis."""

    def __init__(self, vowel: str, sample_rate: int) -> None:
        if vowel not in _FORMANTS:
            raise ValueError(f"vowel must be one of {sorted(_FORMANTS)}, got {vowel!r}")
        self.vowel = vowel
        self.sample_rate = int(sample_rate)
        self._bands = [BiquadFilter("bandpass", f, bw / float(f), self.sample_rate) for f, bw in _FORMANTS[vowel]]

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        out = np.zeros_like(x)
        for band in self._bands:
            out += band.process(x)
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out
