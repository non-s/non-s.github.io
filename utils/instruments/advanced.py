"""Advanced high-fidelity instruments for the Liquid Wire engine.

These instruments use more sophisticated synthesis techniques (physical
modeling, wavetable, granular, FM) for richer, more realistic timbres than
the base instrument set. All are 100% procedural and return mono float64
numpy arrays.
"""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.effects import Chorus
from utils.dsp.envelopes import ADSR, LFO
from utils.dsp.filters import BiquadFilter, FormantFilter, LadderFilter
from utils.instruments.base import Instrument, NoteEvent, clamp, midi_to_hz, normalise


class GlassHarp(Instrument):
    """Glass harp: rubbed wine glass with inharmonic partials and long ring.

    Uses additive synthesis with glass-like inharmonic ratios (1.0, 2.76,
    5.4, 8.93) and a very long exponential decay. A subtle 2nd-order beating
    between close partials gives the shimmering, breathing quality of a
    singing bowl.
    """

    name = "glass_harp"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        rng = np.random.default_rng(self.seed + int(note.note))
        # Glass-like inharmonic partials (measured from real wine glasses).
        partials = [(1.0, 1.0, 0.4), (2.76, 0.45, 0.7), (5.40, 0.18, 1.1), (8.93, 0.08, 1.6)]
        signal = np.zeros(n, dtype=np.float64)
        for ratio, amp, decay_mult in partials:
            f = freq * ratio
            if f >= sr / 2.0:
                continue
            # Slight detune per partial for shimmering beats.
            detune = float(rng.uniform(-0.002, 0.002))
            f_detuned = f * (1.0 + detune)
            decay = 0.4 * decay_mult
            signal += amp * np.sin(2.0 * np.pi * f_detuned * t) * np.exp(-t * decay)
        # Very slow attack (rubbing excitation) + extremely long ring.
        attack = np.minimum(1.0, t / 0.08)
        signal = signal * attack * float(note.velocity)
        # Subtle vibrato for the living, breathing quality.
        vibrato = LFO(4.5, "sine", 0.08, sr, note.duration).apply_to(signal, target="pitch")
        signal = (0.7 * signal + 0.3 * vibrato)
        signal = normalise(signal)
        return clamp(signal)


class MusicBox(Instrument):
    """Music box: comb-tooth plucked synthesis with metallic resonance.

    Models a music box comb tooth: fast pluck, bright harmonics with
    inharmonic stretch, and a characteristic metallic ring. A small chorus
    adds the mechanical wobble of a real music box mechanism.
    """

    name = "music_box"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Inharmonic stretch: real music box teeth are slightly sharp.
        stretch = 1.0 + 0.0004 * freq
        partials = [
            (1.0, 1.0),
            (2.0 * stretch, 0.55),
            (3.0 * stretch**2, 0.28),
            (4.0 * stretch**3, 0.14),
            (5.0 * stretch**4, 0.07),
        ]
        signal = np.zeros(n, dtype=np.float64)
        for k, (ratio, amp) in enumerate(partials, start=1):
            f = freq * ratio
            if f >= sr / 2.0:
                continue
            # Higher partials decay faster (rigid bar physics).
            decay = 2.0 + 0.8 * k
            signal += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * decay)
        # Instant pluck attack.
        attack = np.minimum(1.0, t / 0.0005)
        signal = signal * attack * float(note.velocity)
        # Mechanical wobble chorus.
        signal = Chorus(rate_hz=0.8, depth=0.15, voices=2, sample_rate=sr).process(signal)
        signal = normalise(signal)
        return clamp(signal)


class Theremin(Instrument):
    """Theremin: pure sine with continuous pitch glide and vibrato.

    The theremin has no envelope (continuous tone); the expressivity comes
    from pitch glides and vibrato. This instrument renders a note with a
    smooth portamento from the previous pitch (approximated by a slow
    exponential glide to the target frequency) and a wide, expressive vibrato.
    """

    name = "theremin"

    def __init__(self, seed: int = 0, vibrato_depth: float = 0.15) -> None:
        self.seed = int(seed)
        self.vibrato_depth = float(vibrato_depth)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Pitch glide: start ~3 semitones below and exponentially approach.
        glide_time = 0.15
        glide_env = 1.0 - np.exp(-t / glide_time)
        start_freq = freq * (2.0 ** (-3.0 / 12.0))
        inst_freq = start_freq + (freq - start_freq) * glide_env
        # Expressive vibrato that fades in and varies in depth.
        vibrato = self.vibrato_depth * np.sin(2.0 * np.pi * (5.0 + 0.3 * np.sin(0.7 * t)) * t)
        # Apply vibrato only after the glide settles.
        vib_gain = np.clip((t - glide_time) / 0.3, 0.0, 1.0)
        inst_freq = inst_freq * (1.0 + vibrato * vib_gain * 0.01)
        # Phase accumulation for the time-varying frequency.
        phase = 2.0 * np.pi * np.cumsum(inst_freq) / float(sr)
        signal = np.sin(phase)
        # Slight amplitude wobble (thereminist's hand distance).
        amp_wobble = 0.9 + 0.1 * np.sin(2.0 * np.pi * 0.3 * t)
        # Soft attack/release to avoid clicks at note boundaries.
        fade = int(0.05 * sr)
        env = np.ones(n, dtype=np.float64)
        if fade > 0 and fade < n // 2:
            env[:fade] = np.linspace(0.0, 1.0, fade)
            env[-fade:] = np.linspace(1.0, 0.0, fade)
        signal = signal * amp_wobble * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class PulsarSynth(Instrument):
    """Pulsar synthesizer: pulsaret grains at audio rate with formant filtering.

    A pulsar emits tiny grains (pulsaret) at a configurable rate; each grain
    is a short windowed sine burst. When the grain rate is near the note
    frequency, classic pitched synthesis emerges; when it diverges, rich
    inharmonic textures appear. Formant filtering gives a vocal quality.
    """

    name = "pulsar_synth"

    def __init__(self, seed: int = 0, pulsaret_rate: float = 1.0, vowel: str = "a") -> None:
        self.seed = int(seed)
        self.pulsaret_rate = float(pulsaret_rate)
        self.vowel = vowel

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        # Pulsaret period: rate * note period.
        pulsaret_period = max(8, int(sr / (freq * self.pulsaret_rate)))
        # Pulsaret width: 50% duty cycle windowed by a Hann window.
        width = max(4, pulsaret_period // 2)
        window = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(width) / max(width - 1, 1)))
        carrier_freq = freq * 2.0  # one octave up for brightness
        # Build one pulsaret.
        t_local = np.arange(width, dtype=np.float64) / float(sr)
        pulsaret = window * np.sin(2.0 * np.pi * carrier_freq * t_local)
        # Tile pulsaret across the note duration.
        signal = np.zeros(n, dtype=np.float64)
        pos = 0
        while pos + width <= n:
            signal[pos : pos + width] += pulsaret
            pos += pulsaret_period
        # Formant filtering for a vocal texture.
        formant = FormantFilter(self.vowel, sr)
        signal = formant.process(signal)
        env = ADSR(0.01, 0.1, 0.8, 0.2).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Dulcimer(Instrument):
    """Hammered dulcimer: struck multi-string courses with rapid decay.

    Each note has 2-3 slightly detuned strings (courses) that are struck by a
    hammer. The result is a bright, metallic attack with rich beating.
    """

    name = "dulcimer"

    def __init__(self, seed: int = 0, courses: int = 3) -> None:
        self.seed = int(seed)
        self.courses = max(1, int(courses))

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        rng = np.random.default_rng(self.seed + int(note.note))
        signal = np.zeros(n, dtype=np.float64)
        for _course in range(self.courses):
            detune = float(rng.uniform(-0.004, 0.004))
            f = freq * (1.0 + detune)
            # String harmonics with fast decay (struck string).
            for k, amp in enumerate((1.0, 0.5, 0.3, 0.18, 0.1, 0.06), start=1):
                f_k = f * k
                if f_k >= sr / 2.0:
                    continue
                decay = 1.5 + 0.4 * k
                signal += amp * np.sin(2.0 * np.pi * f_k * t) * np.exp(-t * decay) / float(self.courses)
        # Hammer attack: very fast, with a tiny noise transient.
        attack = np.minimum(1.0, t / 0.001)
        hammer = 0.03 * rng.standard_normal(n) * np.exp(-t * 200.0)
        signal = (signal + hammer) * attack * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class Hang(Instrument):
    """Hang drum (handpan): elliptical membrane modes with long sustain.

    Models the characteristic modes of a hang drum: a fundamental, a
    hum-mode, and a high-mode, plus a metallic edge. The result is a mellow,
    resonant percussion tone with a long, singing sustain.
    """

    name = "hang"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        rng = np.random.default_rng(self.seed + int(note.note))
        # Hang drum modes (elliptical membrane): fundamental, hum (0.5x),
        # octave (2.0x), and fifth (3.0x), plus a metallic high at 5.4x.
        modes = [(1.0, 1.0, 1.2), (2.0, 0.55, 2.0), (3.0, 0.25, 2.8), (5.4, 0.12, 4.5)]
        signal = np.zeros(n, dtype=np.float64)
        for ratio, amp, decay in modes:
            f = freq * ratio
            if f >= sr / 2.0:
                continue
            signal += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * decay)
        # Hand strike: fast attack with a soft thud (low-passed noise burst).
        attack = np.minimum(1.0, t / 0.003)
        thud = 0.05 * rng.standard_normal(n) * np.exp(-t * 120.0)
        thud = BiquadFilter("lowpass", 400.0, 0.7, sr).process(thud)
        signal = (signal + thud) * attack * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class CrystalBow(Instrument):
    """Bowed crystal bowl: continuous bowed tone with harmonic richness.

    A sustained, bowed glass tone with slow harmonic evolution, rich
    upper partials, and a slow vibrato. The bowing excitation is modeled
    as filtered noise added to the sustain.
    """

    name = "crystal_bow"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        t = np.arange(n, dtype=np.float64) / float(sr)
        rng = np.random.default_rng(self.seed + int(note.note))
        # Harmonic series with glass-like inharmonicity.
        partials = [(1.0, 1.0), (2.01, 0.4), (3.03, 0.22), (4.06, 0.12), (5.10, 0.06)]
        signal = np.zeros(n, dtype=np.float64)
        for ratio, amp in partials:
            f = freq * ratio
            if f >= sr / 2.0:
                continue
            # Slow amplitude evolution per partial.
            amp_env = 0.7 + 0.3 * np.sin(2.0 * np.pi * (0.2 + 0.1 * ratio) * t + rng.uniform(0, 2 * np.pi))
            signal += amp * amp_env * np.sin(2.0 * np.pi * f * t)
        # Bowing noise: bandpass-filtered, low-level, sustained.
        bow_noise = rng.standard_normal(n)
        bow_noise = BiquadFilter("bandpass", freq * 3.0, 0.5, sr).process(bow_noise)
        signal += 0.04 * bow_noise
        # Slow vibrato.
        vibrato = LFO(4.0, "sine", 0.06, sr, note.duration).apply_to(signal, target="pitch")
        signal = 0.6 * signal + 0.4 * vibrato
        env = ADSR(0.3, 0.2, 0.9, 0.5).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class WarmPad(Instrument):
    """Warm analog pad: detuned supersaw + slow filter sweep + LFO tremolo.

    A richer pad than the base Pad: uses 11 detuned voices, a stereo chorus,
    a slow filter sweep, and a tremolo LFO for the classic analog warmth.
    """

    name = "warm_pad"

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(note.duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        freq = midi_to_hz(note.note)
        saw = osc.supersaw(freq, note.duration, sr, detune=0.22, voices=11)
        # Slow lowpass sweep with resonance for analog warmth.
        sweep_start = 250.0
        sweep_end = min(freq * 4.0, sr / 2.0 - 200.0)
        signal = np.zeros(n, dtype=np.float64)
        chunk = 256
        filt = LadderFilter(sweep_start, 0.3, sr)
        for i in range(0, n, chunk):
            cutoff = sweep_start + (sweep_end - sweep_start) * (i / max(n - 1, 1))
            filt.set_cutoff(float(cutoff))
            end_i = min(n, i + chunk)
            signal[i:end_i] = filt.process(saw[i:end_i])
        # Long attack + tremolo.
        attack = min(3.0, note.duration * 0.4)
        env = ADSR(attack, 0.4, 0.9, 1.8).render(note.duration, sr)
        tremolo = LFO(0.3, "sine", 0.06, sr, note.duration).apply_to(signal, target="amplitude")
        signal = tremolo * env * float(note.velocity)
        # Stereo chorus for width.
        signal = Chorus(rate_hz=0.35, depth=0.25, voices=3, sample_rate=sr).process(signal)
        signal = normalise(signal)
        return clamp(signal)
