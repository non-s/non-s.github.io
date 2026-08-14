"""Drum sequencer: pattern-based percussion rendering with swing.

A :class:`DrumSequencer` holds a named pattern (a dict mapping instrument name
to a list of step indices) and renders it for a given number of bars at a
given BPM. Swing delays odd 8th-note steps; 0.0 = straight, ~0.66 = jazz swing.
"""

from __future__ import annotations

import numpy as np

from utils.instruments.drums import DRUM_REGISTRY, HiHat, _DrumBase

PATTERNS: dict[str, dict[str, list[int]]] = {
    "rock": {
        "kick": [0, 8],
        "snare": [4, 12],
        "hihat": [0, 2, 4, 6, 8, 10, 12, 14],
    },
    "four_on_floor": {
        "kick": [0, 4, 8, 12],
        "snare": [4, 12],
        "hihat": [0, 2, 4, 6, 8, 10, 12, 14],
    },
    "boom_bap": {
        "kick": [0, 6, 10],
        "snare": [4, 12],
        "hihat": [0, 2, 4, 6, 8, 10, 12, 14],
    },
    "trap": {
        "kick": [0, 3, 6, 10],
        "snare": [4, 12],
        "hihat": [0, 2, 3, 4, 6, 8, 10, 11, 12, 14],
    },
    "jazz_swing": {
        "kick": [0],
        "snare": [4, 12],
        "ride": [0, 3, 4, 7, 8, 11, 12, 15],
        "hihat": [4, 12],
    },
    "one_drop": {
        "kick": [0, 8],
        "snare": [4, 12],
        "hihat": [0, 2, 4, 6, 8, 10, 12, 14],
    },
    "blast_beat": {
        "kick": [0, 2, 4, 6, 8, 10, 12, 14],
        "snare": [1, 3, 5, 7, 9, 11, 13, 15],
        "hihat": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    },
    "samba": {
        "kick": [0, 6, 8, 14],
        "snare": [4, 12],
        "hihat": [0, 2, 4, 6, 8, 10, 12, 14],
        "tambourine": [2, 6, 10, 14],
    },
    "bossa_nova": {
        "kick": [0, 8],
        "snare": [4, 12],
        "hihat": [0, 2, 4, 6, 8, 10, 12, 14],
    },
    "funk_16ths": {
        "kick": [0, 3, 8, 11],
        "snare": [4, 12],
        "hihat": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    },
    "shuffle_blues": {
        "kick": [0, 8],
        "snare": [4, 12],
        "hihat": [0, 3, 4, 7, 8, 11, 12, 15],
    },
    "synthwave_gated": {
        "kick": [0, 4, 8, 12],
        "snare": [4, 12],
        "hihat": [0, 2, 4, 6, 8, 10, 12, 14],
        "clap": [4, 12],
    },
    "cinematic_percussion": {
        "kick": [0, 8],
        "timpani": [0, 8],
        "snare": [4, 12],
        "crash": [0],
        "ride": [2, 6, 10, 14],
    },
    "ambient_sparse": {
        "kick": [0],
        "hihat": [8],
        "crash": [0],
    },
    "light": {
        "kick": [0, 10],
        "snare": [8],
        "hihat": [0, 4, 8, 12],
    },
    "rubato": {
        "kick": [0, 9],
        "snare": [5, 13],
        "hihat": [2, 7, 11],
    },
}


class DrumSequencer:
    """Render a named drum pattern for ``bars`` bars at ``bpm`` BPM.

    Parameters
    ----------
    pattern_name:
        Key into :data:`PATTERNS` (e.g. ``"rock"``, ``"four_on_floor"``).
    swing:
        Swing amount in [0, 1]; 0.0 = straight, 0.66 = jazz swing. Off-beat
        8th-note steps are delayed by ``swing * (step_duration / 2)``.
    steps:
        Number of steps per bar (default 16 = 16th notes).
    """

    def __init__(self, pattern_name: str, swing: float = 0.0, steps: int = 16) -> None:
        if pattern_name not in PATTERNS:
            raise ValueError(f"unknown pattern {pattern_name!r}; valid: {sorted(PATTERNS)}")
        self.pattern_name = pattern_name
        self.swing = float(np.clip(swing, 0.0, 0.95))
        self.steps = int(steps)
        self.instruments: dict[int, list[tuple[str, float]]] = {}
        self._build_pattern()

    def _build_pattern(self) -> None:
        """Translate the named pattern into the step -> hits map."""
        pattern = PATTERNS[self.pattern_name]
        self.instruments = {}
        for instrument_name, step_list in pattern.items():
            for step in step_list:
                self.instruments.setdefault(int(step), []).append((instrument_name, 1.0))

    def _step_time(self, step: int, bpm: float) -> float:
        """Return the absolute start time (seconds) for a given step, with swing."""
        # A bar = 4 beats; step_duration = bar_duration / steps.
        beat_duration = 60.0 / float(bpm)
        bar_duration = 4.0 * beat_duration
        step_duration = bar_duration / float(self.steps)
        # Swing: delay odd 8th-note steps. For 16-step patterns an "8th note"
        # spans 2 steps, so odd 8th notes are steps 2,6,10,14 (i.e. step % 4 == 2).
        base_time = step * step_duration
        if self.swing > 0.0 and step % 4 == 2:
            base_time += self.swing * (step_duration / 2.0)
        return base_time

    def render(self, bpm: float, bars: int, sample_rate: int = 44100) -> np.ndarray:
        """Render ``bars`` bars of the pattern at ``bpm`` BPM."""
        sr = int(sample_rate)
        beat_duration = 60.0 / float(bpm)
        bar_duration = 4.0 * beat_duration
        total_duration = bar_duration * float(bars)
        n = int(round(total_duration * sr))
        out = np.zeros(n, dtype=np.float64)
        # Instantiate each unique drum once and reuse.
        cache: dict[str, _DrumBase] = {}
        for bar in range(bars):
            bar_start = bar * bar_duration
            for step in range(self.steps):
                hits = self.instruments.get(step, [])
                if not hits:
                    continue
                step_t = self._step_time(step, bpm) + bar_start
                for instrument_name, velocity in hits:
                    key = instrument_name
                    if key not in cache:
                        cls = DRUM_REGISTRY.get(key)
                        if cls is None:
                            # Unknown instrument name (e.g. "tambourine"): skip gracefully.
                            continue
                        if cls is HiHat:
                            cache[key] = HiHat(open_hat=(key == "hihat_open"), seed=0)
                        else:
                            cache[key] = cls()
                    drum = cache[key]
                    # Hit duration: roughly one step, but at least 0.15s.
                    hit_dur = max(bar_duration / self.steps, 0.15)
                    rendered = drum.render_hit(velocity=velocity, duration=hit_dur, sample_rate=sr)
                    start_i = int(round(step_t * sr))
                    end_i = min(n, start_i + rendered.size)
                    if end_i <= start_i:
                        continue
                    out[start_i:end_i] += rendered[: end_i - start_i]
        # Normalise the final mix to avoid clipping when many hits overlap.
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1.0:
            out = out / peak
        return np.clip(out, -1.0, 1.0).astype(np.float64)
