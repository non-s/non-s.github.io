"""Extended wind instruments: reeds, brass and flutes. All procedural, mono float64 arrays."""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.envelopes import ADSR, LFO
from utils.dsp.filters import BiquadFilter, FormantFilter, LadderFilter
from utils.instruments.base import Instrument, NoteEvent, clamp, midi_to_hz, normalise


def _vibrato(n: int, sr: int, rate: float, depth: float, delay: float) -> np.ndarray:
    """Delayed vibrato: returns a phase-modulation term in radians."""
    t = np.arange(n, dtype=np.float64) / float(sr)
    gate = np.clip((t - delay) / 0.05, 0.0, 1.0)
    return (depth * gate * np.sin(2.0 * np.pi * rate * t)) * 2.0 * np.pi


class Clarinet(Instrument):
    """Single-reed clarinet: square wave (odd harmonics) + lowpass + formant 'e'."""

    name = "clarinet"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        sig = osc.square(freq, note.duration, sr)
        sig = BiquadFilter("lowpass", freq * 8.0, 0.8, sr).process(sig)
        sig = FormantFilter("e", sr).process(sig)
        rng = np.random.default_rng(self.seed + int(note.note))
        breath = BiquadFilter("highpass", 1200.0, 0.7, sr).process(rng.standard_normal(n))
        sig = sig + 0.06 * breath
        env = ADSR(0.08, 0.05, 0.85, 0.2).render(note.duration, sr)
        t = np.arange(n, dtype=np.float64) / float(sr)
        vib = _vibrato(n, sr, 5.0, 0.012, 0.3)
        sig = np.sin(2.0 * np.pi * freq * t + vib) * 0.15 + sig * 0.85
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Oboe(Instrument):
    """Double-reed oboe: sawtooth + formant 'o' + lowpass ~2kHz. Nasal tone."""

    name = "oboe"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        sig = osc.sawtooth(freq, note.duration, sr)
        sig = BiquadFilter("lowpass", 2000.0, 0.7, sr).process(sig)
        sig = FormantFilter("o", sr).process(sig)
        env = ADSR(0.08, 0.2, 0.8, 0.15).render(note.duration, sr)
        t = np.arange(n, dtype=np.float64) / float(sr)
        vib = _vibrato(n, sr, 5.5, 0.014, 0.4)
        sig = np.sin(2.0 * np.pi * freq * t + vib) * 0.12 + sig * 0.88
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Saxophone(Instrument):
    """Single-reed sax: square + 2nd harmonic (saw) + formant 'a' + ladder LPF."""

    name = "saxophone"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        sig = osc.square(freq, note.duration, sr)
        h2 = osc.sawtooth(freq * 2.0, note.duration, sr)
        sig = sig + 0.25 * h2
        sig = LadderFilter(2000.0, 0.2, sr).process(sig)
        sig = FormantFilter("a", sr).process(sig)
        rng = np.random.default_rng(self.seed + int(note.note))
        breath = BiquadFilter("highpass", 1800.0, 0.7, sr).process(rng.standard_normal(n))
        sig = sig + 0.04 * breath
        env = ADSR(0.03, 0.3, 0.7, 0.2).render(note.duration, sr)
        t = np.arange(n, dtype=np.float64) / float(sr)
        vib = _vibrato(n, sr, 5.0, 0.015, 0.5)
        sig = np.sin(2.0 * np.pi * freq * t + vib) * 0.1 + sig * 0.9
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Trumpet(Instrument):
    """Brass trumpet: sawtooth + lowpass cutoff swept freq*2 -> freq*4. Bright."""

    name = "trumpet"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        sig = osc.sawtooth(freq, note.duration, sr)
        env = ADSR(0.08, 0.2, 0.85, 0.2).render(note.duration, sr)
        t = np.arange(n, dtype=np.float64) / float(sr)
        cutoff = freq * (2.0 + 2.0 * env)
        lp = BiquadFilter("lowpass", float(cutoff[0]), 0.8, sr)
        out = np.zeros(n, dtype=np.float64)
        block = 256
        for i in range(0, n, block):
            j = min(i + block, n)
            lp.set_cutoff(float(np.clip(cutoff[i], 100.0, sr / 2.0 - 1.0)))
            out[i:j] = lp.process(sig[i:j])
        sig = out
        vib = _vibrato(n, sr, 5.5, 0.01, 0.4)
        sig = np.sin(2.0 * np.pi * freq * t + vib) * 0.08 + sig * 0.92
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Trombone(Instrument):
    """Brass trombone: slow saw + lowpass freq*1.5 + initial pitch slide up."""

    name = "trombone"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        env = ADSR(0.12, 0.25, 0.85, 0.25).render(note.duration, sr)
        t = np.arange(n, dtype=np.float64) / float(sr)
        slide = np.clip(t / 0.12, 0.0, 1.0)
        f_inst = freq * (2.0 ** (-0.5 / 12.0)) * (1.0 + (1.0 - 2.0 ** (-0.5 / 12.0)) * slide)
        phase = np.cumsum(2.0 * np.pi * f_inst / float(sr))
        saw = 2.0 * ((phase / (2.0 * np.pi)) % 1.0) - 1.0
        cutoff = freq * (1.5 + 0.5 * env)
        lp = BiquadFilter("lowpass", float(cutoff[0]), 0.8, sr)
        sig = np.zeros(n, dtype=np.float64)
        block = 256
        for i in range(0, n, block):
            j = min(i + block, n)
            lp.set_cutoff(float(np.clip(cutoff[i], 80.0, sr / 2.0 - 1.0)))
            sig[i:j] = lp.process(saw[i:j])
        vib = _vibrato(n, sr, 4.5, 0.01, 0.4)
        sig = np.sin(phase + vib) * 0.08 + sig * 0.92
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Harmonica(Instrument):
    """Harmonica: sine + 2nd harmonic + formant 'i' + vibrato 5.5Hz. Nasal."""

    name = "harmonica"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        vib = 0.018 * np.sin(2.0 * np.pi * 5.5 * t)
        sig = np.sin(2.0 * np.pi * freq * t + vib * 2.0 * np.pi)
        f2 = freq * 2.0
        if f2 < sr / 2.0:
            sig += 0.3 * np.sin(2.0 * np.pi * f2 * t + vib * 2.0 * np.pi)
        sig = FormantFilter("i", sr).process(sig)
        env = ADSR(0.005, 0.5, 0.6, 0.3).render(note.duration, sr)
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Accordion(Instrument):
    """Accordion: sine + 3rd harmonic + tremolo AM 6Hz + subtle vibrato."""

    name = "accordion"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        vib = 0.008 * np.sin(2.0 * np.pi * 5.0 * t)
        sig = np.sin(2.0 * np.pi * freq * t + vib * 2.0 * np.pi)
        f3 = freq * 3.0
        if f3 < sr / 2.0:
            sig += 0.2 * np.sin(2.0 * np.pi * f3 * t + vib * 2.0 * np.pi)
        trem = LFO(6.0, "sine", 0.12, sr, note.duration).render()
        if trem.size < n:
            trem = np.tile(trem, int(np.ceil(n / max(trem.size, 1))))[:n]
        sig = sig * (1.0 + trem)
        env = ADSR(0.03, 0.2, 0.9, 0.3).render(note.duration, sr)
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Shakuhachi(Instrument):
    """Shakuhachi: sine + breath noise bandpass @ 3x fund + pitch wobble. Hollow."""

    name = "shakuhachi"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        wobble = 0.015 * np.sin(2.0 * np.pi * 4.0 * t)
        sig = np.sin(2.0 * np.pi * freq * t + wobble * 2.0 * np.pi)
        rng = np.random.default_rng(self.seed + int(note.note))
        breath = BiquadFilter("bandpass", freq * 3.0, 1.2, sr).process(rng.standard_normal(n))
        sig = sig + 0.12 * breath
        env = ADSR(0.05, 0.3, 0.7, 0.4).render(note.duration, sr)
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Ocarina(Instrument):
    """Ocarina: pure sine + weak 2nd harmonic + formant 'u'. Sweet, round."""

    name = "ocarina"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        sig = np.sin(2.0 * np.pi * freq * t)
        f2 = freq * 2.0
        if f2 < sr / 2.0:
            sig += 0.12 * np.sin(2.0 * np.pi * f2 * t)
        sig = FormantFilter("u", sr).process(sig)
        env = ADSR(0.02, 0.2, 0.8, 0.3).render(note.duration, sr)
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)


class Panpipes(Instrument):
    """Panpipes: sine + breath noise LPF @ 4x fund + vibrato + initial pitch dip."""

    name = "panpipes"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if freq <= 0.0:
            return np.zeros(n, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        dip = np.clip(1.0 - t / 0.08, 0.0, 1.0)
        f_inst = freq * (1.0 - 0.02 * dip)
        vib = 0.008 * np.sin(2.0 * np.pi * 4.0 * t)
        phase = np.cumsum(2.0 * np.pi * f_inst * (1.0 + vib) / float(sr))
        sig = np.sin(phase)
        rng = np.random.default_rng(self.seed + int(note.note))
        breath = BiquadFilter("lowpass", freq * 4.0, 0.8, sr).process(rng.standard_normal(n))
        sig = sig + 0.14 * breath
        env = ADSR(0.03, 0.2, 0.7, 0.4).render(note.duration, sr)
        sig = sig * env * float(note.velocity)
        sig = normalise(sig)
        return clamp(sig)
