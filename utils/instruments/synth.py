"""Synth instruments: pad, lead, sub-bass, synth bass, bell, mallet, choir."""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.effects import Chorus
from utils.dsp.envelopes import ADSR, LFO
from utils.dsp.filters import BiquadFilter, FormantFilter, LadderFilter
from utils.instruments.base import Instrument, NoteEvent, clamp, midi_to_hz, normalise


class Pad(Instrument):
    """Pad: supersaw + slow lowpass sweep + long attack + chorus."""

    name = "pad"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        saw = osc.supersaw(freq, note.duration, sr, detune=0.18, voices=7)
        # Slow lowpass sweep: opens up from ~300 Hz to ~freq*5 over the note.
        sweep_start = 300.0
        sweep_end = min(freq * 5.0, sr / 2.0 - 200.0)
        # Render filter in chunks of 256 samples for an evolving cutoff.
        signal = np.zeros(n, dtype=np.float64)
        chunk = 256
        filt = BiquadFilter("lowpass", sweep_start, 0.7, sr)
        for i in range(0, n, chunk):
            cutoff = sweep_start + (sweep_end - sweep_start) * (i / max(n - 1, 1))
            filt.set_cutoff(float(cutoff))
            end_i = min(n, i + chunk)
            signal[i:end_i] = filt.process(saw[i:end_i])
        # Long attack (up to 2s but clamped to note duration).
        attack = min(2.0, note.duration * 0.5)
        env = ADSR(attack, 0.3, 0.9, 1.5).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        # Chorus for width/movement.
        signal = Chorus(rate_hz=0.4, depth=0.3, voices=3, sample_rate=sr).process(signal)
        signal = normalise(signal)
        return clamp(signal)


class Lead(Instrument):
    """Lead: sawtooth/triangle + filter envelope (auto-wah) + vibrato."""

    name = "lead"

    def __init__(self, seed: int = 0, waveform: str = "saw") -> None:
        self.seed = int(seed)
        self.waveform = waveform

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        if self.waveform == "triangle":
            source = osc.triangle(freq, note.duration, sr)
        else:
            source = osc.sawtooth(freq, note.duration, sr)
        # Auto-wah: bandpass with cutoff envelope sweeping up then down.
        # Cutoff follows an ADSR-like curve centred on the fundamental.
        cutoff_env = ADSR(0.01, 0.2, 0.4, 0.3).render(note.duration, sr)
        min_f = max(freq * 1.5, 200.0)
        max_f = min(freq * 8.0, sr / 2.0 - 200.0)
        cutoffs = min_f + (max_f - min_f) * cutoff_env
        signal = np.zeros(n, dtype=np.float64)
        chunk = 256
        filt = BiquadFilter("bandpass", min_f, 2.0, sr)
        for i in range(0, n, chunk):
            end_i = min(n, i + chunk)
            filt.set_cutoff(float(np.clip(cutoffs[i], 50.0, sr / 2.0 - 100.0)))
            signal[i:end_i] = filt.process(source[i:end_i])
        # Vibrato.
        vibrato = LFO(6.0, "sine", 0.2, sr, note.duration).apply_to(signal, target="pitch")
        env = ADSR(0.01, 0.1, 0.85, 0.2).render(note.duration, sr)
        signal = vibrato * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class SubBass(Instrument):
    """Sub-bass: pure sine below 60 Hz + 2nd/3rd harmonics at low gain."""

    name = "sub_bass"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        # Clamp the perceived fundamental to <= 60 Hz for true sub content.
        if freq > 60.0:
            freq = 60.0 * (freq / 60.0) ** 0.0  # keep the lower octave only if needed
        t = np.arange(n, dtype=np.float64) / float(sr)
        signal = np.sin(2.0 * np.pi * freq * t)
        signal += 0.2 * np.sin(2.0 * np.pi * freq * 2.0 * t)
        signal += 0.1 * np.sin(2.0 * np.pi * freq * 3.0 * t)
        env = ADSR(0.02, 0.1, 0.9, 0.2).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class SynthBass(Instrument):
    """Synth bass: square wave + resonant lowpass + envelope."""

    name = "synth_bass"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        square = osc.square(freq, note.duration, sr)
        # Resonant lowpass with cutoff envelope.
        cutoff_env = ADSR(0.005, 0.15, 0.3, 0.1).render(note.duration, sr)
        min_f = max(freq * 1.2, 80.0)
        max_f = min(freq * 6.0, sr / 2.0 - 200.0)
        cutoffs = min_f + (max_f - min_f) * cutoff_env
        signal = np.zeros(n, dtype=np.float64)
        chunk = 256
        filt = LadderFilter(min_f, 0.7, sr)
        for i in range(0, n, chunk):
            end_i = min(n, i + chunk)
            filt.set_cutoff(float(np.clip(cutoffs[i], 50.0, sr / 2.0 - 100.0)))
            signal[i:end_i] = filt.process(square[i:end_i])
        env = ADSR(0.005, 0.2, 0.6, 0.1).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Bell(Instrument):
    """Bell: FM synthesis with inharmonic ratio (1:1.4) + long decay."""

    name = "bell"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Inharmonic FM: carrier:modulator ratio 1:1.4.
        carrier = freq
        modulator = freq * 1.4
        mod_index = 2.5 * np.exp(-t * 1.5)
        mod_sig = mod_index * np.sin(2.0 * np.pi * modulator * t)
        signal = np.sin(2.0 * np.pi * carrier * t + mod_sig)
        # Long exponential decay, fast attack.
        attack = np.minimum(1.0, t / 0.003)
        decay = np.exp(-t * 1.2)
        signal = signal * attack * decay * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Mallet(Instrument):
    """Mallet (marimba-like): inharmonic partials + fast decay."""

    name = "mallet"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Inharmonic partials (non-integer multiples) for marimba character.
        partials = [(1.0, 1.0), (2.01, 0.6), (3.97, 0.3), (5.92, 0.15), (8.0, 0.08)]
        signal = np.zeros(n, dtype=np.float64)
        for ratio, amp in partials:
            f = freq * ratio
            if f >= sr / 2.0:
                continue
            # Higher partials decay faster (marimba bar physics).
            decay_rate = 2.0 * ratio
            signal += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * decay_rate)
        attack = np.minimum(1.0, t / 0.001)
        signal = signal * attack * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Choir(Instrument):
    """Choir: sine + formant filter + vibrato + slow attack."""

    name = "choir"

    def __init__(self, seed: int = 0, vowel: str = "a") -> None:
        self.seed = int(seed)
        self.vowel = vowel

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        # Rich source: a few harmonics to feed the formant filter.
        t = np.arange(n, dtype=np.float64) / float(sr)
        source = np.sin(2.0 * np.pi * freq * t)
        source += 0.5 * np.sin(2.0 * np.pi * freq * 2.0 * t)
        source += 0.25 * np.sin(2.0 * np.pi * freq * 3.0 * t)
        formant = FormantFilter(self.vowel, sr)
        signal = formant.process(source)
        # Vibrato.
        vibrato = LFO(5.0, "sine", 0.3, sr, note.duration).apply_to(signal, target="pitch")
        # Slow attack, sustain, slow release.
        env = ADSR(0.5, 0.2, 0.85, 0.6).render(note.duration, sr)
        signal = vibrato * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)
