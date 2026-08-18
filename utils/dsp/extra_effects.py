"""Extra effects: flanger, ring mod, tremolo, vibrato, pitch shifter, harmonizer.

These complement the existing chorus/phaser/distortion/bitcrusher in
``utils.dsp.effects``. All are pure-numpy, sample-rate agnostic, and
accept mono or stereo input.

Public classes:
- ``Flanger`` — short modulated delay with feedback (comb through glissando).
- ``RingModulator`` — amplitude modulation with a carrier oscillator.
- ``Tremolo`` — amplitude modulation in the LFO range (1-10 Hz).
- ``Vibrato`` — pitch modulation via fractional delay line.
- ``PitchShifter`` — PSOLA-style pitch shifting using overlap-add grains.
- ``Harmonizer`` — pitch shifter that adds a shifted copy alongside the
  original (intervals: octave up/down, fifth, etc.).
"""

from __future__ import annotations

import numpy as np


class Flanger:
    """Flanger: short modulated delay with feedback.

    A flanger is a comb filter whose delay time is swept by an LFO, producing
    the classic "jet plane" sweep. With high feedback it tends toward
    self-resonance (useful for dramatic sweeps).

    Parameters
    ----------
    rate_hz : float
        LFO sweep rate in Hz (0.1-2 Hz typical).
    depth : float
        Sweep depth in milliseconds (0.5-5 ms typical).
    feedback : float
        Feedback gain (0-0.95). Higher = more resonant.
    mix : float
        Wet/dry mix (0 = dry, 1 = wet).
    """

    def __init__(
        self,
        rate_hz: float = 0.5,
        depth: float = 2.0,
        feedback: float = 0.7,
        mix: float = 0.5,
        sample_rate: int = 44100,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self.rate_hz = float(rate_hz)
        self.depth = float(depth)
        self.feedback = float(np.clip(feedback, 0.0, 0.95))
        self.mix = float(np.clip(mix, 0.0, 1.0))

    def process(self, signal: np.ndarray) -> np.ndarray:
        sr = self.sample_rate
        x = np.asarray(signal, dtype=np.float64).ravel()
        n = x.size
        if n == 0:
            return x.copy()
        t = np.arange(n, dtype=np.float64) / sr
        # Delay time in samples: base 1 ms + depth/2 * (1 + sin(LFO))
        max_delay_samples = int(self.depth * 0.001 * sr) + 2
        buffer = np.zeros(n + max_delay_samples, dtype=np.float64)
        buffer[:n] = x
        out = np.zeros(n, dtype=np.float64)
        feedback_state = 0.0
        for i in range(n):
            delay_ms = 1.0 + 0.5 * self.depth * (1.0 + np.sin(2.0 * np.pi * self.rate_hz * t[i]))
            delay_samples = delay_ms * 0.001 * sr
            di = int(np.floor(delay_samples))
            df = delay_samples - di
            # Read with linear interpolation from buffer.
            read_pos = i + di
            if read_pos + 1 < buffer.size:
                delayed = (1.0 - df) * buffer[read_pos] + df * buffer[read_pos + 1]
            else:
                delayed = 0.0
            # Feedback: add the delayed signal back into the input.
            with_feedback = x[i] + self.feedback * feedback_state
            buffer[i + max_delay_samples // 2] = with_feedback  # write into delay line
            feedback_state = delayed
            out[i] = (1.0 - self.mix) * x[i] + self.mix * delayed
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)


class RingModulator:
    """Ring modulator: multiplies the input by a sine carrier.

    Produces sum and difference frequencies. Classic for metallic, alien
    bell sounds (Doctor Who theme, etc.).

    Parameters
    ----------
    carrier_hz : float
        Carrier frequency.
    mix : float
        Wet/dry mix (0 = dry, 1 = full ring mod).
    """

    def __init__(self, carrier_hz: float = 200.0, mix: float = 1.0, sample_rate: int = 44100) -> None:
        self.sample_rate = int(sample_rate)
        self.carrier_hz = float(carrier_hz)
        self.mix = float(np.clip(mix, 0.0, 1.0))

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        n = x.size
        if n == 0:
            return x.copy()
        t = np.arange(n, dtype=np.float64) / self.sample_rate
        carrier = np.sin(2.0 * np.pi * self.carrier_hz * t)
        ring = x * carrier
        out = (1.0 - self.mix) * x + self.mix * ring
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)


class Tremolo:
    """Tremolo: amplitude modulation in the LFO range (1-10 Hz).

    Unlike ring mod (which produces sidebands), tremolo varies the
    amplitude of the signal — a classic guitar-amp effect.

    Parameters
    ----------
    rate_hz : float
        Modulation rate (1-10 Hz typical).
    depth : float
        Modulation depth (0 = none, 1 = full cut to zero).
    shape : str
        "sine" or "square".
    """

    def __init__(self, rate_hz: float = 5.0, depth: float = 0.5, shape: str = "sine", sample_rate: int = 44100) -> None:
        self.sample_rate = int(sample_rate)
        self.rate_hz = float(rate_hz)
        self.depth = float(np.clip(depth, 0.0, 1.0))
        self.shape = str(shape)

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        n = x.size
        if n == 0:
            return x.copy()
        t = np.arange(n, dtype=np.float64) / self.sample_rate
        if self.shape == "square":
            lfo = np.where(np.sin(2.0 * np.pi * self.rate_hz * t) >= 0, 1.0, 0.0)
        else:
            lfo = 0.5 + 0.5 * np.sin(2.0 * np.pi * self.rate_hz * t)
        gain = 1.0 - self.depth + self.depth * lfo
        out = x * gain
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)


class Vibrato:
    """Vibrato: pitch modulation via fractional delay line.

    Parameters
    ----------
    rate_hz : float
        Modulation rate (5-7 Hz typical for vocal/instrument vibrato).
    depth_cents : float
        Pitch deviation depth in cents (10-50 typical).
    """

    def __init__(self, rate_hz: float = 5.5, depth_cents: float = 25.0, sample_rate: int = 44100) -> None:
        self.sample_rate = int(sample_rate)
        self.rate_hz = float(rate_hz)
        self.depth_cents = float(depth_cents)

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        n = x.size
        if n == 0:
            return x.copy()
        t = np.arange(n, dtype=np.float64) / self.sample_rate
        # Pitch deviation in samples: delay = (cents/1200) * period_samples.
        # Use a base delay of 0 and modulate around it.
        max_delay = int(abs(self.depth_cents) / 1200.0 * self.sample_rate / 100.0) + 2  # small buffer
        buffer = np.zeros(n + max_delay, dtype=np.float64)
        buffer[max_delay : max_delay + n] = x
        out = np.zeros(n, dtype=np.float64)
        lfo = np.sin(2.0 * np.pi * self.rate_hz * t)
        delay_samples = (self.depth_cents / 1200.0) * (self.sample_rate / 100.0) * lfo
        for i in range(n):
            di = max_delay + delay_samples[i]
            ii = int(np.floor(di))
            frac = di - ii
            if ii + 1 < buffer.size:
                out[i] = (1.0 - frac) * buffer[ii] + frac * buffer[ii + 1]
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)


class PitchShifter:
    """PSOLA-style pitch shifter using overlap-add grains.

    Parameters
    ----------
    shift_semitones : float
        Pitch shift in semitones (-12 to +12 typical).
    grain_ms : float
        Analysis grain size (30-50 ms typical).
    """

    def __init__(self, shift_semitones: float = 7.0, grain_ms: float = 40.0, sample_rate: int = 44100) -> None:
        self.sample_rate = int(sample_rate)
        self.shift = 2.0 ** (shift_semitones / 12.0)
        self.grain_ms = float(grain_ms)

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        n = x.size
        if n == 0:
            return x.copy()
        grain_size = max(1, int(self.grain_ms * 0.001 * self.sample_rate))
        hop = max(1, grain_size // 2)
        # Hann window for grains.
        win = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(grain_size) / max(grain_size - 1, 1)))
        out = np.zeros(n, dtype=np.float64)
        # Resample each grain to shift pitch, then overlap-add.
        for i in range(0, n - grain_size, hop):
            grain = x[i : i + grain_size] * win
            # Resample by factor 1/shift (lower shift = longer grain = lower pitch).
            indices = np.arange(grain_size, dtype=np.float64) / self.shift
            indices_int = np.clip(indices.astype(np.int64), 0, grain_size - 1)
            shifted = grain[indices_int]
            end = min(n, i + grain_size)
            out[i:end] += shifted[: end - i]
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)


class Harmonizer:
    """Harmonizer: adds a pitch-shifted copy alongside the original.

    Parameters
    ----------
    interval_semitones : float
        Harmony interval (e.g. 7 = perfect fifth up, -5 = perfect fourth down).
    mix : float
        Level of the harmony voice (0 = none, 1 = same as original).
    """

    def __init__(self, interval_semitones: float = 7.0, mix: float = 0.6, sample_rate: int = 44100) -> None:
        self.shifter = PitchShifter(interval_semitones, sample_rate=sample_rate)
        self.mix = float(np.clip(mix, 0.0, 1.0))

    def process(self, signal: np.ndarray) -> np.ndarray:
        x = np.asarray(signal, dtype=np.float64).ravel()
        harmony = self.shifter.process(x)
        out = x + self.mix * harmony
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)
