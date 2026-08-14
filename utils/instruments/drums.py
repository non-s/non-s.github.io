"""Percussion instruments: kicks, snares, claps, hats, cymbals, toms, etc.

Each drum implements both :meth:`render` (taking a :class:`NoteEvent` whose
``note`` selects the pitch and ``velocity`` the loudness) and
:meth:`render_hit` (a simpler velocity/duration API used by the drum
sequencer). All output is mono float64 numpy arrays.
"""

from __future__ import annotations

import numpy as np

from utils.dsp.filters import BiquadFilter
from utils.instruments.base import Instrument, NoteEvent, clamp, normalise


class _DrumBase(Instrument):
    """Base class providing ``render`` -> ``render_hit`` delegation."""

    name = "drum_base"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.5, sample_rate: int = 44100) -> np.ndarray:
        """Render a single hit. Override in subclasses."""
        raise NotImplementedError

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        # Map MIDI note to a pitch factor: 60 = neutral, lower notes = lower pitch.
        pitch_factor = 2.0 ** ((note.note - 60) / 12.0)
        base = self.render_hit(note.velocity, note.duration, sample_rate)
        # Resample the base hit by the pitch factor (linear interpolation).
        if abs(pitch_factor - 1.0) < 1e-6:
            return clamp(base)
        indices = np.arange(base.size, dtype=np.float64) * pitch_factor
        i0 = np.floor(indices).astype(np.int64)
        i0 = np.clip(i0, 0, base.size - 1)
        i1 = np.clip(i0 + 1, 0, base.size - 1)
        frac = indices - i0
        out = (1.0 - frac) * base[i0] + frac * base[i1]
        return clamp(out)


class Kick808(_DrumBase):
    """808 kick: sine with long pitch drop + long decay (melodic 808 bass)."""

    name = "kick_808"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.5, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Pitch drops from ~150 Hz to ~50 Hz over ~0.05s.
        freq = 50.0 + 100.0 * np.exp(-t * 30.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase)
        env = np.exp(-t * 3.0)
        signal = signal * env * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Kick909(_DrumBase):
    """909 kick: sine with short pitch drop + click transient."""

    name = "kick_909"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.3, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Short pitch drop from ~120 Hz to ~60 Hz over ~0.02s.
        freq = 60.0 + 60.0 * np.exp(-t * 80.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase)
        # Click transient at the very start.
        click = 0.4 * np.exp(-t * 400.0) * np.sign(np.sin(2.0 * np.pi * 3000.0 * t))
        signal = (signal + click) * np.exp(-t * 12.0) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class KickAcoustic(_DrumBase):
    """Acoustic kick: sine + noise transient + body resonance."""

    name = "kick_acoustic"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.25, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Body resonance around 60 Hz.
        freq = 60.0 + 40.0 * np.exp(-t * 60.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase) * np.exp(-t * 18.0)
        # Noise transient (beater click).
        rng = np.random.default_rng(0)
        noise = rng.standard_normal(n) * np.exp(-t * 200.0)
        noise = BiquadFilter("highpass", 1000.0, 0.7, sr).process(noise)
        signal = (signal + 0.3 * noise) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Snare(_DrumBase):
    """Snare: noise + tonal body (~200 Hz) + bandpass + envelope."""

    name = "snare"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.2, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Tonal body around 200 Hz.
        body = np.sin(2.0 * np.pi * 200.0 * t) * np.exp(-t * 30.0)
        # Noise component (the snare wires).
        rng = np.random.default_rng(1)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("bandpass", 1800.0, 0.8, sr).process(noise)
        noise = noise * np.exp(-t * 18.0)
        signal = (0.6 * noise + 0.4 * body) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Clap(_DrumBase):
    """Clap: layered noise bursts (3-4 quick bursts) + envelope."""

    name = "clap"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.2, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        rng = np.random.default_rng(2)
        signal = np.zeros(n, dtype=np.float64)
        # Four quick bursts at staggered onsets for the classic clap.
        onsets = (0.0, 0.008, 0.016, 0.024)
        for onset in onsets:
            start_i = int(onset * sr)
            if start_i >= n:
                continue
            burst_len = n - start_i
            burst = rng.standard_normal(burst_len)
            burst = BiquadFilter("bandpass", 1500.0, 0.6, sr).process(burst)
            t_local = np.arange(burst_len, dtype=np.float64) / float(sr)
            decay = np.exp(-t_local * 40.0)
            signal[start_i:] += burst * decay
        # Longer tail decay for the body of the clap.
        t = np.arange(n, dtype=np.float64) / float(sr)
        tail = np.exp(-t * 8.0)
        signal = signal * tail * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class HiHat(_DrumBase):
    """Hi-hat: white noise + highpass + envelope (closed=short, open=long)."""

    name = "hihat"

    def __init__(self, open_hat: bool = False, seed: int = 0) -> None:
        self.open_hat = bool(open_hat)
        self.seed = int(seed)

    def render_hit(self, velocity: float = 1.0, duration: float | None = None, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        dur = float(duration) if duration is not None else (0.4 if self.open_hat else 0.08)
        n = int(round(dur * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        rng = np.random.default_rng(self.seed)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("highpass", 7000.0, 0.7, sr).process(noise)
        t = np.arange(n, dtype=np.float64) / float(sr)
        decay_rate = 6.0 if self.open_hat else 60.0
        env = np.exp(-t * decay_rate)
        signal = noise * env * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Crash(_DrumBase):
    """Crash cymbal: white noise + bandpass + long decay."""

    name = "crash"

    def render_hit(self, velocity: float = 1.0, duration: float = 1.2, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        rng = np.random.default_rng(3)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("bandpass", 5000.0, 0.5, sr).process(noise)
        t = np.arange(n, dtype=np.float64) / float(sr)
        env = np.exp(-t * 1.8)
        signal = noise * env * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Ride(_DrumBase):
    """Ride cymbal: inharmonic partials + noise + sustain."""

    name = "ride"

    def render_hit(self, velocity: float = 1.0, duration: float = 1.0, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Inharmonic metallic partials (the "ping" + body).
        partials = [(310.0, 0.6), (430.0, 0.4), (590.0, 0.3), (820.0, 0.2), (1100.0, 0.15)]
        signal = np.zeros(n, dtype=np.float64)
        for f, amp in partials:
            if f >= sr / 2.0:
                continue
            signal += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-t * 3.0)
        # Noise wash for the sustained shimmer.
        rng = np.random.default_rng(4)
        noise = rng.standard_normal(n)
        noise = BiquadFilter("highpass", 6000.0, 0.7, sr).process(noise)
        signal += 0.3 * noise * np.exp(-t * 1.5)
        signal = signal * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Tom(_DrumBase):
    """Tom: sine with pitch drop + envelope."""

    name = "tom"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.4, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Pitch drop from ~220 Hz to ~120 Hz.
        freq = 120.0 + 100.0 * np.exp(-t * 25.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase) * np.exp(-t * 8.0) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Tabla(_DrumBase):
    """Tabla: tonal hand drum with pitch bend."""

    name = "tabla"

    def render_hit(self, velocity: float = 1.0, duration: float = 0.4, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Pitch bends down then up slightly (the characteristic tabla "gul").
        freq = 180.0 + 60.0 * np.exp(-t * 30.0) + 20.0 * (1.0 - np.exp(-t * 50.0))
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase)
        # Add a couple harmonics for the resonant head.
        signal += 0.4 * np.sin(2.0 * phase) * np.exp(-t * 12.0)
        signal += 0.2 * np.sin(3.0 * phase) * np.exp(-t * 20.0)
        env = np.exp(-t * 6.0)
        signal = signal * env * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


class Timpani(_DrumBase):
    """Timpani: sine with pitch bend + long decay."""

    name = "timpani"

    def render_hit(self, velocity: float = 1.0, duration: float = 1.2, sample_rate: int = 44100) -> np.ndarray:
        sr = int(sample_rate)
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        t = np.arange(n, dtype=np.float64) / float(sr)
        # Slight pitch glide (the drum head settles).
        freq = 110.0 + 20.0 * np.exp(-t * 8.0)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(sr)
        signal = np.sin(phase)
        # Add harmonics for the orchestral timbre.
        signal += 0.3 * np.sin(2.0 * phase) * np.exp(-t * 2.0)
        signal += 0.15 * np.sin(3.0 * phase) * np.exp(-t * 3.0)
        # Initial strike transient.
        rng = np.random.default_rng(5)
        transient = rng.standard_normal(n) * np.exp(-t * 150.0)
        transient = BiquadFilter("lowpass", 800.0, 0.7, sr).process(transient)
        signal = (signal + 0.3 * transient) * np.exp(-t * 1.5) * float(velocity)
        signal = normalise(signal)
        return clamp(signal)


# Convenience registry for the drum sequencer.
DRUM_REGISTRY: dict[str, type[_DrumBase]] = {
    "kick_808": Kick808,
    "kick_909": Kick909,
    "kick_acoustic": KickAcoustic,
    "kick": Kick909,  # alias for generic "kick"
    "snare": Snare,
    "clap": Clap,
    "hihat": HiHat,
    "hihat_open": HiHat,
    "crash": Crash,
    "ride": Ride,
    "tom": Tom,
    "tabla": Tabla,
    "timpani": Timpani,
}
