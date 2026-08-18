"""Schroeder (Freeverb) and plate-style reverbs.

Both reverbs generate their delay networks entirely from ``room_size`` and
``damping`` parameters - no impulse-response files are loaded. The comb and
allpass filters use direct-form delay lines with tight inner loops (the comb
feedback path uses a one-pole lowpass for damping). Mono and stereo inputs are
accepted; stereo inputs are processed with the comb/allpass banks per channel
for a sense of width.
"""

from __future__ import annotations

import numpy as np

# Freeverb fixed delay lengths (in samples at 44.1 kHz) from the classic spec.
_FREEVERB_COMB = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617]
_FREEVERB_ALLPASS = [556, 441, 341, 225]


class _Comb:
    """Schroeder comb filter with a one-pole lowpass in the feedback path.

    Implemented as a direct-form delay line with a tight inner loop. The
    feedback damping lowpass is applied inline (one multiply-add per sample)
    so no scipy call is needed per sample.
    """

    def __init__(self, delay: int, damp: float, feedback: float) -> None:
        self.delay = max(1, int(delay))
        self.damp = float(np.clip(damp, 0.0, 1.0))
        self.feedback = float(np.clip(feedback, 0.0, 0.999))
        self._buf = np.zeros(self.delay, dtype=np.float64)
        self._idx = 0
        self._store = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64).ravel()
        if x.size == 0:
            return x.copy()
        n = x.size
        D = self.delay
        fb = self.feedback
        buf = self._buf
        idx = self._idx
        out = np.empty(n, dtype=np.float64)
        # Process in a tight loop over the delay-line read/write. The inner
        # work per sample is minimal (one read, one write, one mul) so this
        # loop is the unavoidable cost of a comb filter; numpy vectorization
        # would require strided tricks that are no faster for D ~ 1000.
        for i in range(n):
            delayed = buf[idx]
            out[i] = delayed
            # One-pole lowpass in the feedback path (stateful).
            self._store = (1.0 - self.damp) * delayed + self.damp * self._store
            buf[idx] = x[i] + fb * self._store
            idx = (idx + 1) % D
        self._idx = idx
        return out


class _Allpass:
    """Schroeder allpass filter via direct-form delay line; stateful."""

    def __init__(self, delay: int, feedback: float) -> None:
        self.delay = max(1, int(delay))
        self.feedback = float(np.clip(feedback, 0.0, 0.999))
        self._buf = np.zeros(self.delay, dtype=np.float64)
        self._idx = 0

    def process(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64).ravel()
        if x.size == 0:
            return x.copy()
        n = x.size
        D = self.delay
        fb = self.feedback
        buf = self._buf
        idx = self._idx
        out = np.empty(n, dtype=np.float64)
        for i in range(n):
            buf_out = buf[idx]
            out[i] = -x[i] + buf_out
            buf[idx] = x[i] + buf_out * fb
            idx = (idx + 1) % D
        self._idx = idx
        return out


def _to_channels(signal: np.ndarray) -> list[np.ndarray]:
    x = np.asarray(signal, dtype=np.float64)
    if x.ndim == 1:
        return [x]
    return [x[:, c] for c in range(x.shape[1])]


def _from_channels(channels: list[np.ndarray]) -> np.ndarray:
    if len(channels) == 1:
        return channels[0]
    return np.stack(channels, axis=1)


class Freeverb:
    """Schroeder reverb: 8 comb filters + 4 allpass filters per channel."""

    def __init__(
        self,
        room_size: float = 0.7,
        damping: float = 0.5,
        wet: float = 0.3,
        dry: float = 0.7,
        width: float = 0.5,
        sample_rate: int = 44100,
    ) -> None:
        self.room_size = float(np.clip(room_size, 0.0, 1.0))
        self.damping = float(np.clip(damping, 0.0, 1.0))
        self.wet = float(np.clip(wet, 0.0, 1.0))
        self.dry = float(np.clip(dry, 0.0, 1.0))
        self.width = float(np.clip(width, 0.0, 1.0))
        self.sample_rate = int(sample_rate)
        # Scale comb delay lengths to the actual sample rate.
        scale = self.sample_rate / 44100.0
        self._comb_delays = [max(1, int(round(d * scale))) for d in _FREEVERB_COMB]
        self._ap_delays = [max(1, int(round(d * scale))) for d in _FREEVERB_ALLPASS]
        # Freeverb maps room_size 0..1 to feedback 0.28..0.84 (approx).
        self._feedback = 0.28 + 0.56 * self.room_size
        # Two parallel banks (left/right) for stereo width.
        self._combs_l = [_Comb(d, self.damping, self._feedback) for d in self._comb_delays]
        self._combs_r = [_Comb(d, self.damping, self._feedback) for d in self._comb_delays]
        self._aps_l = [_Allpass(d, 0.5) for d in self._ap_delays]
        self._aps_r = [_Allpass(d, 0.5) for d in self._ap_delays]

    def _process_channel(self, x: np.ndarray, combs: list[_Comb], aps: list[_Allpass]) -> np.ndarray:
        wet_sig = np.zeros_like(x)
        for comb in combs:
            wet_sig += comb.process(x)
        wet_sig /= float(len(combs))
        for ap in aps:
            wet_sig = ap.process(wet_sig)
        return wet_sig

    def process(self, signal: np.ndarray) -> np.ndarray:
        channels = _to_channels(signal)
        out_channels: list[np.ndarray] = []
        if len(channels) == 1:
            wet = self._process_channel(channels[0], self._combs_l, self._aps_l)
            out = self.dry * channels[0] + self.wet * wet
            out_channels.append(out)
        else:
            wet_l = self._process_channel(channels[0], self._combs_l, self._aps_l)
            wet_r = self._process_channel(channels[1], self._combs_r, self._aps_r)
            # Width cross-mix.
            wet_l_mix = (1.0 - self.width) * wet_l + self.width * wet_r
            wet_r_mix = (1.0 - self.width) * wet_r + self.width * wet_l
            out_channels.append(self.dry * channels[0] + self.wet * wet_l_mix)
            out_channels.append(self.dry * channels[1] + self.wet * wet_r_mix)
        return _from_channels(out_channels)


class PlateReverb:
    """Plate-style reverb using a shorter, denser delay network.

    The plate uses 6 comb filters with shorter, irregularly spaced delays and
    2 allpass filters in series, emulating the bright, diffuse decay of a
    metal plate.
    """

    def __init__(
        self,
        room_size: float = 0.6,
        damping: float = 0.4,
        wet: float = 0.25,
        sample_rate: int = 44100,
    ) -> None:
        self.room_size = float(np.clip(room_size, 0.0, 1.0))
        self.damping = float(np.clip(damping, 0.0, 1.0))
        self.wet = float(np.clip(wet, 0.0, 1.0))
        self.sample_rate = int(sample_rate)
        scale = self.sample_rate / 44100.0
        # Shorter, irregularly spaced comb delays for a plate-like density.
        base_delays = [421, 533, 619, 757, 887, 997]
        self._comb_delays = [max(1, int(round(d * scale * (0.5 + self.room_size)))) for d in base_delays]
        self._ap_delays = [max(1, int(round(d * scale))) for d in (167, 211)]
        self._feedback = 0.35 + 0.55 * self.room_size
        self._combs = [_Comb(d, self.damping, self._feedback) for d in self._comb_delays]
        self._aps = [_Allpass(d, 0.6) for d in self._ap_delays]

    def process(self, signal: np.ndarray) -> np.ndarray:
        channels = _to_channels(signal)
        out_channels: list[np.ndarray] = []
        for ch in channels:
            wet = np.zeros_like(ch)
            for comb in self._combs:
                wet += comb.process(ch)
            wet /= float(len(self._combs))
            for ap in self._aps:
                wet = ap.process(wet)
            out_channels.append((1.0 - self.wet) * ch + self.wet * wet)
        return _from_channels(out_channels)
