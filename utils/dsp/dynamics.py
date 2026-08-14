"""Dynamic-range processors: compressor, limiter and sidechain ducker.

All operate on mono numpy float64 arrays and use a feed-forward/feedback RMS
detector with smooth attack/release coefficients. No external assets.
"""

from __future__ import annotations

import numpy as np


def _to_mono(signal: np.ndarray) -> np.ndarray:
    x = np.asarray(signal, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=tuple(range(1, x.ndim)))
    return x.ravel()


class Compressor:
    """Feed-forward RMS compressor with attack/release smoothing."""

    def __init__(
        self,
        threshold: float,
        ratio: float,
        attack_ms: float,
        release_ms: float,
        makeup_gain: float = 1.0,
        sample_rate: int = 44100,
    ) -> None:
        self.threshold = float(threshold)
        self.ratio = max(1.0, float(ratio))
        self.attack_ms = float(attack_ms)
        self.release_ms = float(release_ms)
        self.makeup_gain = float(makeup_gain)
        self.sample_rate = int(sample_rate)
        self._update_coeffs()

    def _update_coeffs(self) -> None:
        sr = self.sample_rate
        # Coefficients for a one-pole smoothing filter (per-sample).
        atk = max(self.attack_ms, 1e-3) * 1e-3
        rel = max(self.release_ms, 1e-3) * 1e-3
        self._attack_coef = np.exp(-1.0 / (atk * sr))
        self._release_coef = np.exp(-1.0 / (rel * sr))

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = _to_mono(signal)
        # RMS detector with a short window (rectified envelope).
        env = np.abs(x)
        # Smooth envelope.
        det = np.empty_like(env)
        c_atk = self._attack_coef
        c_rel = self._release_coef
        e = 0.0
        for i in range(env.size):
            if env[i] > e:
                e = c_atk * e + (1.0 - c_atk) * env[i]
            else:
                e = c_rel * e + (1.0 - c_rel) * env[i]
            det[i] = e
        # Gain reduction in dB.
        det_db = 20.0 * np.log10(np.maximum(det, 1e-12))
        over = np.maximum(det_db - self.threshold, 0.0)
        # Compression gain (dB): negative for above-threshold signals.
        gain_db = -over * (1.0 - 1.0 / self.ratio)
        gain_lin = 10.0 ** (gain_db / 20.0)
        out = x * gain_lin * self.makeup_gain
        return out.astype(np.float64)


class Limiter:
    """Brick-wall limiter with lookahead-free fast attack and longer release."""

    def __init__(
        self,
        ceiling: float = 0.95,
        attack_ms: float = 1.0,
        release_ms: float = 50.0,
        sample_rate: int = 44100,
    ) -> None:
        self.ceiling = float(ceiling)
        self.attack_ms = float(attack_ms)
        self.release_ms = float(release_ms)
        self.sample_rate = int(sample_rate)
        sr = self.sample_rate
        self._attack_coef = np.exp(-1.0 / (max(self.attack_ms, 1e-3) * 1e-3 * sr))
        self._release_coef = np.exp(-1.0 / (max(self.release_ms, 1e-3) * 1e-3 * sr))

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = _to_mono(signal)
        env = np.abs(x)
        c_atk = self._attack_coef
        c_rel = self._release_coef
        e = 0.0
        gain = np.empty_like(env)
        for i in range(env.size):
            if env[i] > e:
                e = c_atk * e + (1.0 - c_atk) * env[i]
            else:
                e = c_rel * e + (1.0 - c_rel) * env[i]
            # Brick-wall: scale so peak envelope never exceeds ceiling.
            if e > self.ceiling:
                gain[i] = self.ceiling / e
            else:
                gain[i] = 1.0
        out = x * gain
        # Final hard clip as a safety net.
        return np.clip(out, -self.ceiling, self.ceiling).astype(np.float64)


class SideChainDuck:
    """Duck ``target`` based on the amplitude envelope of ``source``."""

    def __init__(
        self,
        source: np.ndarray,
        target: np.ndarray,
        threshold: float,
        ratio: float,
        attack_ms: float,
        release_ms: float,
        sample_rate: int,
    ) -> None:
        self.source = _to_mono(source)
        self.target = _to_mono(target)
        self.threshold = float(threshold)
        self.ratio = max(1.0, float(ratio))
        self.attack_ms = float(attack_ms)
        self.release_ms = float(release_ms)
        self.sample_rate = int(sample_rate)
        sr = self.sample_rate
        self._attack_coef = np.exp(-1.0 / (max(self.attack_ms, 1e-3) * 1e-3 * sr))
        self._release_coef = np.exp(-1.0 / (max(self.release_ms, 1e-3) * 1e-3 * sr))

    def process(self) -> np.ndarray:
        src = self.source
        tgt = self.target
        n = max(src.size, tgt.size)
        # Pad shorter array with zeros so lengths match.
        if src.size < n:
            src = np.pad(src, (0, n - src.size))
        if tgt.size < n:
            tgt = np.pad(tgt, (0, n - tgt.size))
        env = np.abs(src)
        c_atk = self._attack_coef
        c_rel = self._release_coef
        e = 0.0
        det = np.empty_like(env)
        for i in range(env.size):
            if env[i] > e:
                e = c_atk * e + (1.0 - c_atk) * env[i]
            else:
                e = c_rel * e + (1.0 - c_rel) * env[i]
            det[i] = e
        det_db = 20.0 * np.log10(np.maximum(det, 1e-12))
        over = np.maximum(det_db - self.threshold, 0.0)
        gain_db = -over * (1.0 - 1.0 / self.ratio)
        gain_lin = 10.0 ** (gain_db / 20.0)
        return (tgt * gain_lin).astype(np.float64)
