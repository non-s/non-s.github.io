"""Stringed and brass instruments: ensemble, brass, guitars, sitar.

All instruments are 100% procedural and return mono float64 numpy arrays.
"""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.effects import Distortion
from utils.dsp.envelopes import ADSR, LFO
from utils.dsp.filters import BiquadFilter
from utils.instruments.base import Instrument, NoteEvent, clamp, midi_to_hz, normalise


class StringEnsemble(Instrument):
    """String ensemble: supersaw (7 detuned voices) + vibrato + lowpass + slow ADSR."""

    name = "string_ensemble"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        saw = osc.supersaw(freq, note.duration, sr, detune=0.12, voices=7)
        # Vibrato LFO (5 Hz, ~15 cents depth) applied as pitch modulation.
        vibrato = LFO(5.0, "sine", 0.25, sr, note.duration).apply_to(saw, target="pitch")
        # Warm lowpass to remove harshness of the supersaw.
        lowpass = BiquadFilter("lowpass", min(freq * 6.0, sr / 2.0 - 100.0), 0.7, sr)
        signal = lowpass.process(vibrato)
        # Crescendo ADSR: slow attack, sustain, slow release.
        env = ADSR(0.4, 0.2, 0.85, 0.4).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class BrassSection(Instrument):
    """Brass section: sawtooth + lowpass + crescendo + delayed vibrato."""

    name = "brass_section"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        saw = osc.sawtooth(freq, note.duration, sr)
        # Lowpass with cutoff rising during the crescendo.
        lowpass = BiquadFilter("lowpass", min(freq * 4.0, sr / 2.0 - 100.0), 0.7, sr)
        signal = lowpass.process(saw)
        # Delayed vibrato: starts after 0.3s, fades in over 0.2s.
        t = np.arange(n, dtype=np.float64) / float(sr)
        vib_gain = np.clip((t - 0.3) / 0.2, 0.0, 1.0)
        vibrato = LFO(5.5, "sine", 0.2, sr, note.duration).apply_to(signal, target="pitch")
        signal = (1.0 - vib_gain) * signal + vib_gain * vibrato
        env = ADSR(0.15, 0.2, 0.85, 0.25).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class AcousticGuitar(Instrument):
    """Acoustic guitar: sawtooth + body resonance filter + pluck envelope."""

    name = "acoustic_guitar"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        saw = osc.sawtooth(freq, note.duration, sr)
        # Body resonance: a peaking lowpass around 200 Hz (guitar body).
        body = BiquadFilter("lowpass", 2000.0, 0.8, sr)
        signal = body.process(saw)
        # Pluck envelope: fast attack, medium decay.
        env = ADSR(0.002, 0.5, 0.0, 0.2).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class DistortedGuitar(Instrument):
    """Distorted guitar: supersaw + hard clipping + cabinet lowpass + palm mute."""

    name = "distorted_guitar"

    def __init__(self, seed: int = 0, palm_mute: bool = False) -> None:
        self.seed = int(seed)
        self.palm_mute = bool(palm_mute)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        saw = osc.supersaw(freq, note.duration, sr, detune=0.08, voices=5)
        # Hard clipping distortion + cabinet lowpass.
        distorted = Distortion(drive=0.85, tone=0.6, sample_rate=sr).process(saw)
        # Cabinet: additional lowpass.
        cabinet = BiquadFilter("lowpass", 4500.0, 0.7, sr)
        signal = cabinet.process(distorted)
        if self.palm_mute:
            env = ADSR(0.001, 0.08, 0.0, 0.05).render(note.duration, sr)
        else:
            env = ADSR(0.003, 0.3, 0.4, 0.2).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class BassGuitar(Instrument):
    """Bass guitar: sawtooth + lowpass + pluck envelope (medium decay)."""

    name = "bass_guitar"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        saw = osc.sawtooth(freq, note.duration, sr)
        # Warm lowpass for bass body.
        lowpass = BiquadFilter("lowpass", min(freq * 4.0, 1200.0), 0.8, sr)
        signal = lowpass.process(saw)
        env = ADSR(0.005, 0.4, 0.1, 0.15).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Sitar(Instrument):
    """Sitar: plucked + sympathetic string resonance (detuned harmonic sines)."""

    name = "sitar"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Main plucked string: fundamental + harmonics with fast decay.
        signal = np.zeros(n, dtype=np.float64)
        for k, amp in enumerate((1.0, 0.5, 0.33, 0.25, 0.2), start=1):
            f = freq * k
            if f >= sr / 2.0:
                continue
            signal += amp * np.sin(2.0 * np.pi * f * t)
        # Sympathetic strings: several detuned sines at harmonic ratios.
        sympathetic = np.zeros(n, dtype=np.float64)
        for ratio, amp in ((1.0, 0.3), (1.5, 0.2), (2.0, 0.15), (3.0, 0.1), (4.0, 0.08)):
            f = freq * ratio * 1.003  # slight detune for shimmer
            if f >= sr / 2.0:
                continue
            sympathetic += amp * np.sin(2.0 * np.pi * f * t)
        signal += 0.4 * sympathetic
        # Pluck envelope: very fast attack, long decay.
        attack = np.minimum(1.0, t / 0.002)
        decay = np.exp(-t * 2.5)
        signal = signal * attack * decay * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)
