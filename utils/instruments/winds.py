"""Wind instruments: flute, kalimba. All procedural, mono float64 arrays."""

from __future__ import annotations

import numpy as np

from utils.dsp.envelopes import ADSR
from utils.dsp.filters import BiquadFilter
from utils.instruments.base import Instrument, NoteEvent, clamp, midi_to_hz, normalise


class Flute(Instrument):
    """Flute: sine + breath noise (filtered) + vibrato + slow attack."""

    name = "flute"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Slight pitch wobble (vibrato) applied via FM-style phase modulation.
        vibrato = 0.02 * np.sin(2.0 * np.pi * 5.0 * t)
        signal = np.sin(2.0 * np.pi * freq * t + vibrato * 2.0 * np.pi)
        # Breath noise: filtered white noise gated by amplitude envelope.
        rng = np.random.default_rng(self.seed + int(note.note))
        breath = rng.standard_normal(n)
        breath = BiquadFilter("bandpass", freq * 2.0, 1.5, sr).process(breath)
        signal += 0.08 * breath
        env = ADSR(0.12, 0.05, 0.85, 0.2).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Kalimba(Instrument):
    """Kalimba: sine + harmonics + fast decay + thumb piano character."""

    name = "kalimba"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Inharmonic partials typical of a thumb piano (slightly sharp harmonics).
        partials = [(1.0, 1.0), (2.02, 0.5), (3.05, 0.25), (4.1, 0.12)]
        signal = np.zeros(n, dtype=np.float64)
        for ratio, amp in partials:
            f = freq * ratio
            if f >= sr / 2.0:
                continue
            decay_rate = 3.0 + 1.5 * (ratio - 1.0)
            signal += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * decay_rate)
        # Very fast attack (pluck of the thumb).
        attack = np.minimum(1.0, t / 0.001)
        signal = signal * attack * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)
