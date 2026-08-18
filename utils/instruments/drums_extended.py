"""Extended percussion: tambourine, conga, bongo, cowbell, shaker, woodblock,
clave, agogo, rimshot, sidestick, china, splash, surdo, caixa, cuica, tamborim.

Each drum implements both :meth:`render` (taking a :class:`NoteEvent` whose
``note`` selects the pitch and ``velocity`` the loudness) and
:meth:`render_hit` (a simpler velocity/duration API used by the drum
sequencer). All output is mono float64 numpy arrays.
"""

from __future__ import annotations

import numpy as np

from utils.dsp.filters import BiquadFilter
from utils.instruments.base import clamp, normalise
from utils.instruments.drums import _DrumBase


class Tambourine(_DrumBase):
    """Tambourine: bandpass-filtered noise + short jingle bells."""

    name = "tambourine"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.15, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        rng = np.random.default_rng(self.seed)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("bandpass", 6000.0, 0.8, sr).process(noise)
        shell = noise * np.exp(-t * 18.0)
        jingles = np.zeros(n, dtype=np.float64)
        for f, amp in ((8000.0, 0.5), (8200.0, 0.3), (7800.0, 0.3)):
            jingles += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * 25.0)
        jingle_noise = rng.standard_normal(n) * np.exp(-t * 30.0)
        jingle_noise = BiquadFilter("highpass", 7000.0, 0.7, sr).process(jingle_noise)
        jingles += jingle_noise
        signal = (0.6 * shell + 0.4 * jingles) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Conga(_DrumBase):
    """Conga: tonal hand drum with pitch drop + harmonics + noise attack."""

    name = "conga"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.25, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        freq = 150.0 + 50.0 * np.exp(-t * 25.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase)
        signal += 0.35 * np.sin(2.0 * np.pi * 400.0 * t) * np.exp(-t * 30.0)
        signal += 0.15 * np.sin(2.0 * np.pi * 600.0 * t) * np.exp(-t * 40.0)
        rng = np.random.default_rng(self.seed)
        attack = rng.standard_normal(n) * np.exp(-t * 200.0)
        attack = BiquadFilter("highpass", 2000.0, 0.7, sr).process(attack)
        signal = (signal * np.exp(-t * 7.0) + 0.3 * attack) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Bongo(_DrumBase):
    """Bongo: higher-pitched conga with shorter decay."""

    name = "bongo"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.12, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        freq = 220.0 + 80.0 * np.exp(-t * 30.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase)
        signal += 0.3 * np.sin(2.0 * np.pi * 600.0 * t) * np.exp(-t * 40.0)
        rng = np.random.default_rng(self.seed)
        attack = rng.standard_normal(n) * np.exp(-t * 250.0)
        attack = BiquadFilter("highpass", 3000.0, 0.7, sr).process(attack)
        signal = (signal * np.exp(-t * 14.0) + 0.25 * attack) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Cowbell(_DrumBase):
    """Cowbell: additive non-harmonic partials, hollow metallic tone."""

    name = "cowbell"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.2, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        signal = np.zeros(n, dtype=np.float64)
        for f, amp in ((560.0, 0.6), (845.0, 0.5), (1180.0, 0.3)):
            if f >= sr / 2.0:
                continue
            signal += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * 12.0)
        rng = np.random.default_rng(self.seed)
        clang = rng.standard_normal(n) * np.exp(-t * 80.0)
        clang = BiquadFilter("bandpass", 800.0, 0.7, sr).process(clang)
        signal = (signal + 0.2 * clang) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Shaker(_DrumBase):
    """Shaker: highpass noise with fast exponential decay, no pitch."""

    name = "shaker"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.08, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        rng = np.random.default_rng(self.seed)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("highpass", 6000.0, 0.7, sr).process(noise)
        env = np.exp(-t * 30.0)
        signal = noise * env * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Woodblock(_DrumBase):
    """Woodblock: sine + octave harmonic + click attack, woody tone."""

    name = "woodblock"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.1, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        signal = np.sin(2.0 * np.pi * 800.0 * t) * np.exp(-t * 35.0)
        signal += 0.4 * np.sin(2.0 * np.pi * 1600.0 * t) * np.exp(-t * 50.0)
        click = np.exp(-t * 600.0) * np.sign(np.sin(2.0 * np.pi * 2500.0 * t))
        signal = (signal + 0.2 * click) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Clave(_DrumBase):
    """Clave: sharp high-pitched click with pitch drop, very short."""

    name = "clave"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.06, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        freq = 2000.0 + 500.0 * np.exp(-t * 80.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase) * np.exp(-t * 50.0)
        click = np.exp(-t * 800.0) * np.sign(np.sin(2.0 * np.pi * 3000.0 * t))
        signal = (signal + 0.3 * click) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Agogo(_DrumBase):
    """Agogo: two metallic tones (440 Hz + 660 Hz) summed to mono."""

    name = "agogo"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.3, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        low = np.sin(2.0 * np.pi * 440.0 * t) * np.exp(-t * 6.0)
        high = np.sin(2.0 * np.pi * 660.0 * t) * np.exp(-t * 8.0)
        low += 0.3 * np.sin(2.0 * np.pi * 880.0 * t) * np.exp(-t * 10.0)
        high += 0.3 * np.sin(2.0 * np.pi * 1320.0 * t) * np.exp(-t * 12.0)
        rng = np.random.default_rng(self.seed)
        strike = rng.standard_normal(n) * np.exp(-t * 150.0)
        strike = BiquadFilter("highpass", 4000.0, 0.7, sr).process(strike)
        signal = (0.5 * low + 0.5 * high + 0.2 * strike) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Rimshot(_DrumBase):
    """Rimshot: sharp click + short tom body, beat on the rim."""

    name = "rimshot"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.05, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        click = np.exp(-t * 400.0) * np.sign(np.sin(2.0 * np.pi * 2000.0 * t))
        rng = np.random.default_rng(self.seed)
        noise = rng.standard_normal(n) * np.exp(-t * 300.0)
        noise = BiquadFilter("highpass", 4000.0, 0.7, sr).process(noise)
        freq = 300.0 + 50.0 * np.exp(-t * 40.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        tom = np.sin(phase) * np.exp(-t * 30.0)
        signal = (0.5 * click + 0.3 * noise + 0.4 * tom) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Sidestick(_DrumBase):
    """Sidestick: dry click + short resonance, very short."""

    name = "sidestick"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.04, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        click_len = min(n, int(0.01 * sr))
        click = np.zeros(n, dtype=np.float64)
        click[:click_len] = np.sign(np.sin(2.0 * np.pi * 1500.0 * t[:click_len])) * np.exp(-t[:click_len] * 600.0)
        res = np.sin(2.0 * np.pi * 250.0 * t) * np.exp(-t * 50.0)
        signal = (0.6 * click + 0.3 * res) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class China(_DrumBase):
    """China cymbal: bandpass noise + inharmonic partials, explosive long."""

    name = "china"

    def render_hit(self, velocity: float = 1.0, duration: float = 1.2, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        rng = np.random.default_rng(self.seed)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("bandpass", 3000.0, 0.5, sr).process(noise)
        signal = noise * np.exp(-t * 2.5)
        for f, amp in ((350.0, 0.4), (480.0, 0.3), (720.0, 0.25), (950.0, 0.2)):
            if f >= sr / 2.0:
                continue
            signal += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * 3.0)
        attack = rng.standard_normal(n) * np.exp(-t * 120.0)
        attack = BiquadFilter("highpass", 5000.0, 0.7, sr).process(attack)
        signal = (signal + 0.3 * attack) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Splash(_DrumBase):
    """Splash cymbal: bright bandpass noise, short decay."""

    name = "splash"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.4, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        rng = np.random.default_rng(self.seed)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("bandpass", 7000.0, 0.6, sr).process(noise)
        signal = noise * np.exp(-t * 7.0)
        for f, amp in ((3500.0, 0.3), (5200.0, 0.2), (8800.0, 0.15)):
            if f >= sr / 2.0:
                continue
            signal += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * 9.0)
        signal = signal * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Surdo(_DrumBase):
    """Surdo: deep Brazilian bass drum, low pitch drop + long decay."""

    name = "surdo"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.8, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        freq = 50.0 + 30.0 * np.exp(-t * 20.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase)
        signal += 0.25 * np.sin(2.0 * phase) * np.exp(-t * 4.0)
        rng = np.random.default_rng(self.seed)
        noise = rng.standard_normal(n) * np.exp(-t * 40.0)
        noise = BiquadFilter("lowpass", 200.0, 0.7, sr).process(noise)
        signal = (signal * np.exp(-t * 2.5) + 0.3 * noise) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Caixa(_DrumBase):
    """Caixa: Brazilian snare, bandpass noise + tonal body + snare wires."""

    name = "caixa"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.15, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        body = np.sin(2.0 * np.pi * 200.0 * t) * np.exp(-t * 30.0)
        rng = np.random.default_rng(self.seed)
        shell = rng.standard_normal(n)
        shell = BiquadFilter("bandpass", 1800.0, 0.8, sr).process(shell)
        shell = shell * np.exp(-t * 18.0)
        wires = rng.standard_normal(n)
        wires = BiquadFilter("highpass", 3000.0, 0.7, sr).process(wires)
        wires = wires * np.exp(-t * 22.0)
        signal = (0.4 * shell + 0.3 * body + 0.4 * wires) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Cuica(_DrumBase):
    """Cuica: Brazilian friction drum with pitch wobble and "choro" tone."""

    name = "cuica"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.3, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        lfo = 1.0 + 0.4 * np.sin(2.0 * np.pi * 8.0 * t)
        freq = 400.0 * lfo
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase)
        signal += 0.3 * np.sin(2.0 * phase) * np.exp(-t * 5.0)
        rng = np.random.default_rng(self.seed)
        friction = rng.standard_normal(n)
        friction = BiquadFilter("bandpass", 1200.0, 0.8, sr).process(friction)
        friction_env = np.exp(-t * 4.0) * (0.5 + 0.5 * np.sin(2.0 * np.pi * 8.0 * t))
        signal = (signal * np.exp(-t * 3.0) + 0.3 * friction * friction_env) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Tamborim(_DrumBase):
    """Tamborim: small high Brazilian drum, short pitch drop + bright noise."""

    name = "tamborim"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.08, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        freq = 600.0 + 150.0 * np.exp(-t * 60.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase) * np.exp(-t * 30.0)
        signal += 0.3 * np.sin(2.0 * phase) * np.exp(-t * 45.0)
        rng = np.random.default_rng(self.seed)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("highpass", 5000.0, 0.7, sr).process(noise)
        signal = (signal + 0.25 * noise * np.exp(-t * 40.0)) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


DRUM_EXTENDED_REGISTRY: dict[str, type[_DrumBase]] = {
    "tambourine": Tambourine,
    "conga": Conga,
    "bongo": Bongo,
    "cowbell": Cowbell,
    "shaker": Shaker,
    "woodblock": Woodblock,
    "clave": Clave,
    "agogo": Agogo,
    "rimshot": Rimshot,
    "sidestick": Sidestick,
    "china": China,
    "splash": Splash,
    "surdo": Surdo,
    "caixa": Caixa,
    "cuica": Cuica,
    "tamborim": Tamborim,
}
