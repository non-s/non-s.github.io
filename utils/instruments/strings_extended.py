"""Extended procedural string instruments via physical modeling.

Seven new instruments built on Karplus-Strong / waveguide synthesis:
violin, cello, harp, koto, banjo, mandolin, ukulele. All return mono
float64 numpy arrays normalised to [-1, 1].
"""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.envelopes import ADSR, LFO
from utils.dsp.filters import BiquadFilter
from utils.dsp.physical_modeling import KarplusStrong, WaveguideString
from utils.instruments.base import Instrument, NoteEvent, clamp, midi_to_hz, normalise


def _pitch_shift_buffer(signal: np.ndarray, ratio: np.ndarray) -> np.ndarray:
    """Resample ``signal`` by a per-sample ``ratio`` via linear interpolation."""
    x = np.asarray(signal, dtype=np.float64).ravel()
    if x.size == 0:
        return x.copy()
    phase = np.cumsum(np.asarray(ratio, dtype=np.float64).ravel())
    phase -= phase[0]
    src_idx = np.clip(phase, 0.0, x.size - 1.0)
    i0 = np.floor(src_idx).astype(np.int64)
    i1 = np.clip(i0 + 1, 0, x.size - 1)
    frac = src_idx - i0
    return ((1.0 - frac) * x[i0] + frac * x[i1]).astype(np.float64)


class Violin(Instrument):
    """Bowed violin: waveguide string driven by a sawtooth bowing envelope."""

    name = "violin"

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
        waveguide = WaveguideString(
            decay=0.998, damping=0.2, dispersion=0.1, bridge_pos=0.3, seed=self.seed
        )
        body = waveguide.render(freq, note.duration, sr, velocity=float(note.velocity))
        bow_env = ADSR(0.05, 0.05, 0.9, 0.1).render(note.duration, sr)
        saw = osc.sawtooth(freq, note.duration, sr)
        bowed = body * 0.6 + 0.4 * saw * bow_env
        vibrato = LFO(5.0, "sine", 10.0 / 12.0, sr, note.duration).render()  # 10 cents
        ratio = 2.0 ** (vibrato / 12.0)
        bowed = _pitch_shift_buffer(bowed, ratio)
        bowed = bowed * bow_env * float(note.velocity)
        bowed = normalise(bowed)
        return clamp(bowed)


class Cello(Instrument):
    """Bowed cello: warmer, slower bowing than the violin, lower register."""

    name = "cello"

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
        waveguide = WaveguideString(
            decay=0.997, damping=0.15, dispersion=0.08, bridge_pos=0.25, seed=self.seed
        )
        body = waveguide.render(freq, note.duration, sr, velocity=float(note.velocity))
        bow_env = ADSR(0.08, 0.05, 0.9, 0.12).render(note.duration, sr)
        saw = osc.sawtooth(freq, note.duration, sr)
        lowpass = BiquadFilter("lowpass", min(freq * 5.0, sr / 2.0 - 100.0), 0.8, sr)
        saw = lowpass.process(saw)
        bowed = body * 0.65 + 0.35 * saw * bow_env
        vibrato = LFO(4.5, "sine", 8.0 / 12.0, sr, note.duration).render()  # 8 cents
        ratio = 2.0 ** (vibrato / 12.0)
        bowed = _pitch_shift_buffer(bowed, ratio)
        bowed = bowed * bow_env * float(note.velocity)
        bowed = normalise(bowed)
        return clamp(bowed)


class Harp(Instrument):
    """Harp: Karplus-Strong pluck with a faint octave harmonic for richness."""

    name = "harp"

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
        ks = KarplusStrong(decay=0.995, blend=0.4, seed=self.seed)
        fundamental = ks.render(freq, note.duration, sr, velocity=float(note.velocity))
        harmonic = np.zeros_like(fundamental)
        if 2.0 * freq < sr / 2.0:
            ks2 = KarplusStrong(decay=0.99, blend=0.4, seed=self.seed + 1)
            harmonic = ks2.render(2.0 * freq, note.duration, sr, velocity=0.35 * float(note.velocity))
        if harmonic.size < fundamental.size:
            harmonic = np.pad(harmonic, (0, fundamental.size - harmonic.size))
        elif harmonic.size > fundamental.size:
            harmonic = harmonic[: fundamental.size]
        signal = fundamental + 0.25 * harmonic
        env = ADSR(0.001, 0.8, 0.0, 0.5).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Koto(Instrument):
    """Koto: bright metallic pluck with pick noise and a short pitch pull."""

    name = "koto"

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
        ks = KarplusStrong(decay=0.996, blend=0.3, seed=self.seed)
        signal = ks.render(freq, note.duration, sr, velocity=float(note.velocity))
        rng = np.random.default_rng(self.seed + 7)
        click_len = max(1, int(0.001 * sr))
        click = np.zeros(n, dtype=np.float64)
        click[:click_len] = rng.standard_normal(click_len) * float(note.velocity)
        highpass = BiquadFilter("highpass", min(freq * 4.0, sr / 2.0 - 100.0), 0.7, sr)
        click = highpass.process(click)
        if click.size < signal.size:
            click = np.pad(click, (0, signal.size - click.size))
        elif click.size > signal.size:
            click = click[: signal.size]
        signal = signal + 0.15 * click
        pull_len = max(1, int(0.05 * sr))
        ratio = np.ones(n, dtype=np.float64)
        ratio[:pull_len] = np.linspace(1.02, 1.0, pull_len)
        signal = _pitch_shift_buffer(signal, ratio)
        env = ADSR(0.002, 0.7, 0.1, 0.3).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Banjo(Instrument):
    """Banjo: short percussive decay with an aggressive pick noise burst."""

    name = "banjo"

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
        ks = KarplusStrong(decay=0.97, blend=0.2, seed=self.seed)
        signal = ks.render(freq, note.duration, sr, velocity=float(note.velocity))
        rng = np.random.default_rng(self.seed + 3)
        burst_len = max(1, int(0.003 * sr))
        burst = np.zeros(n, dtype=np.float64)
        burst[:burst_len] = rng.standard_normal(burst_len) * float(note.velocity)
        highpass = BiquadFilter("highpass", min(freq * 3.0, sr / 2.0 - 100.0), 0.6, sr)
        burst = highpass.process(burst)
        if burst.size < signal.size:
            burst = np.pad(burst, (0, signal.size - burst.size))
        elif burst.size > signal.size:
            burst = burst[: signal.size]
        signal = signal + 0.2 * burst
        env = ADSR(0.001, 0.3, 0.0, 0.2).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Mandolin(Instrument):
    """Mandolin: four detuned Karplus-Strong chorused strings."""

    name = "mandolin"

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
        detunes = (-2.0, -1.0, 1.0, 2.0)
        signal = np.zeros(n, dtype=np.float64)
        for i, cents in enumerate(detunes):
            f = freq * (2.0 ** (cents / 1200.0))
            ks = KarplusStrong(decay=0.994, blend=0.35, seed=self.seed + i)
            voice = ks.render(f, note.duration, sr, velocity=float(note.velocity))
            if voice.size < n:
                voice = np.pad(voice, (0, n - voice.size))
            elif voice.size > n:
                voice = voice[:n]
            signal += voice
        signal /= float(len(detunes))
        env = ADSR(0.001, 0.5, 0.0, 0.3).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Ukulele(Instrument):
    """Ukulele: medium-decay Karplus-Strong pluck with a sweet soft attack."""

    name = "ukulele"

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
        ks = KarplusStrong(decay=0.985, blend=0.5, seed=self.seed)
        signal = ks.render(freq, note.duration, sr, velocity=float(note.velocity))
        lowpass = BiquadFilter("lowpass", min(freq * 6.0, sr / 2.0 - 100.0), 0.7, sr)
        signal = lowpass.process(signal)
        env = ADSR(0.002, 0.4, 0.0, 0.2).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)
