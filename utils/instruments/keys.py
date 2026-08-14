"""Keyboard instruments: piano, electric piano, organ, clavinet, harpsichord.

All instruments are 100% procedural (additive, FM and subtractive synthesis)
and return mono float64 numpy arrays.
"""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.envelopes import ADSR
from utils.dsp.filters import BiquadFilter
from utils.instruments.base import Instrument, NoteEvent, clamp, midi_to_hz, normalise


class AcousticPiano(Instrument):
    """Acoustic piano: additive sine partials + hammer noise + ADSR.

    Refactored from ``generate_liquid_wire_video._synth_audio.add_piano`` so
    the same warm lo-fi timbre is available to every composition layer.
    """

    name = "acoustic_piano"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        rng = np.random.default_rng(self.seed + int(note.note))
        t = np.arange(n, dtype=np.float64) / float(sr)
        freq = midi_to_hz(note.note + float(rng.normal(0.0, 0.025)))
        # ADSR: 12 ms attack, exponential decay; sustain falls off naturally.
        attack = np.minimum(1.0, t / 0.012)
        decay = np.exp(-t * float(rng.uniform(1.7, 2.25)))
        body = (
            np.sin(2.0 * np.pi * freq * t)
            + 0.42 * np.sin(2.0 * np.pi * freq * 2.01 * t + 0.3)
            + 0.18 * np.sin(2.0 * np.pi * freq * 3.98 * t + 0.9)
        )
        hammer = 0.08 * rng.standard_normal(n) * np.exp(-t * 24.0)
        signal = attack * decay * (body + hammer)
        signal = signal * float(note.velocity)
        signal = clamp(signal)
        return signal.astype(np.float64)


class ElectricPiano(Instrument):
    """Electric piano (Rhodes-like): FM synthesis + tine attack noise."""

    name = "electric_piano"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        rng = np.random.default_rng(self.seed + int(note.note))
        carrier = midi_to_hz(note.note)
        modulator = carrier * 1.0  # 1:1 ratio for a bell-like tine
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Modulation index decays: bright attack, mellow sustain.
        mod_index = 3.0 * np.exp(-t * 4.0)
        mod_sig = mod_index * np.sin(2.0 * np.pi * modulator * t)
        carrier_sig = np.sin(2.0 * np.pi * carrier * t + mod_sig)
        # Tine attack: a short filtered noise burst.
        tine = 0.15 * rng.standard_normal(n) * np.exp(-t * 80.0)
        tine = BiquadFilter("highpass", 2000.0, 0.7, sr).process(tine)
        env = ADSR(0.005, 0.3, 0.2, 0.4).render(note.duration, sr)
        signal = (carrier_sig + tine) * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Organ(Instrument):
    """Drawbar organ: 9 harmonics at classic drawbar ratios + optional Leslie."""

    name = "organ"

    # Classic Hammond drawbar footages (16', 5 1/3', 8', 4', 2 2/3', 2', 1 3/5', 1 1/3', 1').
    _DRAWBAR_RATIOS = (0.5, 1.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0)
    _DRAWBAR_GAINS = (0.8, 0.3, 1.0, 0.6, 0.4, 0.3, 0.2, 0.2, 0.2)

    def __init__(self, leslie: bool = True, seed: int = 0) -> None:
        self.leslie = bool(leslie)
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        signal = np.zeros(n, dtype=np.float64)
        for ratio, gain in zip(self._DRAWBAR_RATIOS, self._DRAWBAR_GAINS, strict=True):
            f = freq * ratio
            if f >= sr / 2.0:
                continue
            signal += gain * np.sin(2.0 * np.pi * f * t)
        if self.leslie:
            # Leslie: chorus (slight delay vibrato) + amplitude modulation.
            lfo = osc.sine(5.5, note.duration, sr)
            tremolo = 0.85 + 0.15 * lfo
            signal = signal * tremolo
        env = ADSR(0.02, 0.05, 0.9, 0.15).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Clavinet(Instrument):
    """Clavinet: sawtooth + bandpass filter + pluck envelope."""

    name = "clavinet"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        saw = osc.sawtooth(freq, note.duration, sr)
        # Bandpass centred near the fundamental for the clavinet bite.
        bp = BiquadFilter("bandpass", freq * 2.0, 1.2, sr)
        signal = bp.process(saw)
        # Pluck envelope: fast attack, medium decay.
        env = ADSR(0.003, 0.25, 0.0, 0.15).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Harpsichord(Instrument):
    """Harpsichord: plucked multiple harmonics, fast decay, no sustain."""

    name = "harpsichord"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Two ranks (8' and 4') for the classic harpsichord coupling.
        harmonics = [(1.0, 1.0), (2.0, 0.5), (3.0, 0.25), (4.0, 0.12), (1.0 * 2.0, 0.4)]
        signal = np.zeros(n, dtype=np.float64)
        for ratio, amp in harmonics:
            f = freq * ratio
            if f >= sr / 2.0:
                continue
            signal += amp * np.sin(2.0 * np.pi * f * t)
        # Pluck: very fast attack, exponential decay (no sustain).
        attack = np.minimum(1.0, t / 0.002)
        decay = np.exp(-t * 6.0)
        signal = signal * attack * decay * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)
