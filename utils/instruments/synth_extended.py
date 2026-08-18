"""Extended synth instruments: vocoder, wavetable, FM, granular, supersaw, shimmer.

Six advanced instruments built on the DSP layer (FM, wavetable, granular,
pitch-shifting, formant filtering). All are 100% procedural and return mono
float64 numpy arrays normalised to [-1, 1].
"""

from __future__ import annotations

import numpy as np

from utils.dsp import oscillators as osc
from utils.dsp.effects import Chorus, Delay
from utils.dsp.envelopes import ADSR, LFO
from utils.dsp.extra_effects import Harmonizer
from utils.dsp.filters import BiquadFilter, FormantFilter, LadderFilter
from utils.dsp.fm_synth import FMSynth as _FMSynth
from utils.dsp.fm_synth import _Operator
from utils.dsp.granular import GrainCloud
from utils.dsp.wavetable import MorphWavetable as _MorphWavetable
from utils.dsp.wavetable import WavetableSynth as _WTSynth
from utils.instruments.base import Instrument, NoteEvent, clamp, midi_to_hz, normalise


class VocoderSynth(Instrument):
    """Vocoder: synthetic voice via bandpass-filtered saw carrier + formant.

    A sawtooth carrier (fundamental + 2nd harmonic) is split into five bandpass
    bands whose amplitudes are modulated by a slow ADSR. A formant filter on
    the summed bands gives a vocal "a" quality, and a 5 Hz vibrato adds the
    robotic-vocal character.
    """

    name = "vocoder_synth"

    _BAND_FREQS = (200.0, 500.0, 1200.0, 2800.0, 6500.0)

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
        carrier = osc.sawtooth(freq, note.duration, sr)
        carrier = carrier + 0.4 * osc.sawtooth(freq * 2.0, note.duration, sr)
        carrier = normalise(carrier)
        env = ADSR(0.1, 0.3, 0.8, 0.5).render(note.duration, sr)
        signal = np.zeros(n, dtype=np.float64)
        chunk = 256
        bands = [BiquadFilter("bandpass", f, 3.0, sr) for f in self._BAND_FREQS]
        for i in range(0, n, chunk):
            end_i = min(n, i + chunk)
            e = float(env[i])
            for band in bands:
                signal[i:end_i] += e * band.process(carrier[i:end_i])
        signal = normalise(signal)
        formant = FormantFilter("a", sr)
        signal = formant.process(signal)
        vibrato = LFO(5.0, "sine", 0.15, sr, note.duration).apply_to(signal, target="pitch")
        signal = vibrato * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class WavetableSynth(Instrument):
    """Morphing wavetable pad: MorphWavetable scanned by a slow LFO.

    Uses a 32-frame morphing wavetable (sine -> saw -> square -> noise) with a
    slow morph LFO for evolving timbral movement, shaped by a medium ADSR.
    """

    name = "wavetable_synth"

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
        table = _MorphWavetable(size=2048, num_frames=32, seed=self.seed)
        synth = _WTSynth(table, morph_lfo_rate=0.3, morph_position=0.0)
        env = ADSR(0.05, 0.2, 0.8, 0.3)
        signal = synth.render(freq, note.duration, sr, env=env)
        signal = signal * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class FMSynth(Instrument):
    """FM electric piano: algorithm 2 with three active operators.

    Operator 0 is the carrier (ratio 1.0, level 0.7); operators 1 and 2 are
    modulators feeding it (ratios 1.0 and 2.0 with moderate modulation
    indices) producing the classic DX7 electric-piano timbre.
    """

    name = "fm_synth"

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
        operators = [
            _Operator(ratio=1.0, level=0.7, mod_index=0.0, env=ADSR(0.005, 0.3, 0.6, 0.4)),
            _Operator(ratio=1.0, level=0.5, mod_index=1.5, env=ADSR(0.005, 0.2, 0.4, 0.3)),
            _Operator(ratio=2.0, level=0.3, mod_index=0.8, env=ADSR(0.005, 0.15, 0.2, 0.2)),
            _Operator(level=0.0),
            _Operator(level=0.0),
            _Operator(level=0.0),
        ]
        synth = _FMSynth(algorithm=2, operators=operators)
        signal = synth.render(freq, note.duration, sr)
        signal = signal * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class GranularPad(Instrument):
    """Granular pad: cloud of grains drawn from a sine + 3rd harmonic source.

    A source buffer of a sine wave with its 3rd harmonic is fed into a
    GrainCloud with moderate density and pitch/position jitter. The stereo
    cloud output is summed to mono and shaped by a slow ADSR for an ethereal,
    textural pad.
    """

    name = "granular_pad"

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
        src_dur = max(note.duration, 1.0)
        source = osc.sine(freq, src_dur, sr)
        source = source + 0.33 * osc.sine(freq * 3.0, src_dur, sr)
        source = normalise(source)
        cloud = GrainCloud(
            source,
            sr,
            density=15.0,
            grain_ms=50.0,
            pitch_jitter=0.02,
            pos_jitter=0.1,
            spread=0.6,
            seed=self.seed,
        )
        stereo = cloud.render(note.duration)
        signal = stereo[0] + stereo[1]
        env = ADSR(0.3, 0.2, 0.9, 0.5).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)


class SupersawStereo(Instrument):
    """Stereo supersaw: two detuned supersaws panned hard L/R + chorus.

    Two supersaw renders with alternating detune and different seeds are summed
    into a stereo pair, then collapsed to mono. A chorus adds extra width and
    movement.
    """

    name = "supersaw_stereo"

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
        left = osc.supersaw(freq, note.duration, sr, detune=0.15, voices=7)
        right = osc.supersaw(freq, note.duration, sr, detune=0.11, voices=7)
        signal = left + right
        env = ADSR(0.02, 0.2, 0.8, 0.3).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        signal = Chorus(rate_hz=0.5, depth=0.3, voices=3, sample_rate=sr).process(signal)
        signal = normalise(signal)
        return clamp(signal)


class ShimmerPad(Instrument):
    """Shimmer pad: supersaw + octave-up harmonizer + feedback delay + filter LFO.

    A five-voice supersaw is enriched by a +12 semitone harmonizer, washed
    through a feedback delay (reverb-like), and shaped by a LadderFilter whose
    cutoff is slowly swept by a 0.2 Hz LFO. A long ADSR gives the angelic,
    ethereal sustain.
    """

    name = "shimmer_pad"

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
        saw = osc.supersaw(freq, note.duration, sr, detune=0.1, voices=5)
        harmonizer = Harmonizer(interval_semitones=12.0, mix=0.4, sample_rate=sr)
        signal = harmonizer.process(saw)
        base_cutoff = max(freq * 2.0, 400.0)
        max_cutoff = min(freq * 8.0, sr / 2.0 - 200.0)
        cutoff_lfo = LFO(0.2, "sine", 0.4, sr, note.duration).render()
        cutoffs = base_cutoff + (max_cutoff - base_cutoff) * (0.5 + 0.5 * cutoff_lfo)
        filtered = np.zeros(n, dtype=np.float64)
        chunk = 256
        filt = LadderFilter(base_cutoff, 0.2, sr)
        for i in range(0, n, chunk):
            end_i = min(n, i + chunk)
            filt.set_cutoff(float(np.clip(cutoffs[i], 50.0, sr / 2.0 - 100.0)))
            filtered[i:end_i] = filt.process(signal[i:end_i])
        delay = Delay(time_ms=180.0, feedback=0.45, mix=0.3, sample_rate=sr)
        signal = delay.process(filtered)
        env = ADSR(0.4, 0.3, 0.9, 0.8).render(note.duration, sr)
        signal = signal * env * float(note.velocity)
        signal = normalise(signal)
        return clamp(signal)
