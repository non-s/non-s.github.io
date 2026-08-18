"""FM multi-operador synthesis (DX7-style).

Six operators with configurable frequency ratios, envelopes, feedback loops
and algorithms. The classic Yamaha DX7 used this architecture to produce
rich, expressive tones (electric pianos, bells, brass, etc.) from a handful
of sine operators. This module generalises the idea:

- Each operator is a sine oscillator with its own amplitude envelope (ADSR),
  a frequency ratio relative to the fundamental, and optional feedback
  (self-modulation producing saw-like spectra).
- An "algorithm" is a routing matrix that decides which operators modulate
  which carriers. Several canonical DX7 algorithms are pre-defined.
- The output is the sum of the carrier operators, rendered entirely in
  numpy for C-speed.

This is a pure-Python nod to FM synthesis — it does not aim for sample
accuracy with the DX7, but gives a much richer palette than the simple
two-operator ``osc.fm`` already in the engine.
"""

from __future__ import annotations

import numpy as np

from utils.dsp.envelopes import ADSR


class _Operator:
    """A single FM operator: sine + envelope + feedback.

    Parameters
    ----------
    ratio : float
        Frequency multiplier relative to the fundamental (e.g. 1.0 = unison,
        2.0 = octave above, 0.5 = octave below).
    level : float
        Peak output level (0-1) when acting as a carrier.
    mod_index : float
        Modulation depth when feeding another operator (in Hz). Higher
        values produce brighter spectra with more sidebands.
    feedback : float
        Self-feedback level (0-1) producing a saw-like waveform.
    env : ADSR
        Amplitude envelope for this operator.
    detune_cents : float
        Small pitch offset in cents for chorus/spread effects.
    """

    def __init__(
        self,
        ratio: float = 1.0,
        level: float = 1.0,
        mod_index: float = 0.0,
        feedback: float = 0.0,
        env: ADSR | None = None,
        detune_cents: float = 0.0,
    ) -> None:
        self.ratio = float(ratio)
        self.level = float(level)
        self.mod_index = float(mod_index)
        self.feedback = float(np.clip(feedback, 0.0, 1.0))
        self.env = env if env is not None else ADSR(0.01, 0.2, 0.7, 0.3)
        self.detune_cents = float(detune_cents)

    def render(
        self,
        freq: float,
        duration: float,
        sr: int,
        mod_input: np.ndarray | None = None,
    ) -> np.ndarray:
        """Render this operator's waveform.

        ``mod_input`` is the summed modulation signal from any operators
        feeding this one (phase modulation in radians). If feedback is
        non-zero, the operator feeds its own delayed output back into its
        phase.
        """
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        detune_mul = 2.0 ** (self.detune_cents / 1200.0)
        op_freq = freq * self.ratio * detune_mul
        t = np.arange(n, dtype=np.float64) / float(sr)
        two_pi = 2.0 * np.pi
        phase = two_pi * op_freq * t
        # External modulation (from upstream operators).
        if mod_input is not None and mod_input.size:
            phase = phase + mod_input[:n]
        # Self-feedback: approximate by feeding the previous output sample
        # back into the phase. A vectorised one-sample-delay using np.roll
        # gives a stable, cheap feedback loop (true DX7 used a 1-sample
        # delay line in fixed point).
        if self.feedback > 1e-6:
            fb = np.zeros(n, dtype=np.float64)
            fb_amount = self.feedback * two_pi
            for i in range(1, n):
                fb[i] = fb_amount * np.sin(phase[i - 1] + fb[i - 1])
            phase = phase + fb
        wave = np.sin(phase)
        env = self.env.render(duration, sr)
        if env.size < n:
            env = np.pad(env, (0, n - env.size))
        elif env.size > n:
            env = env[:n]
        return (wave * env * self.level).astype(np.float64)


# Canonical DX7 algorithms as a list of (carrier_indices, mod_matrix) tuples.
# carrier_indices: operators that sum to the final output (0-indexed).
# mod_matrix: list of (modulator_index, target_index) pairs meaning
# "operator A modulates the phase of operator B".
_ALGORITHMS: list[tuple[tuple[int, ...], tuple[tuple[int, int], ...]]] = [
    # Algorithm 1: stack — 6→5→4→3→2→1 (a single chain producing very bright
    # spectra). Classic for plucked/bell tones.
    ((0,), ((5, 4), (4, 3), (3, 2), (2, 1), (1, 0))),
    # Algorithm 2: 1 carrier, two parallel modulators (3→1, 2→1). Good for
    # electric piano when op2 is slow and op3 is a higher harmonic.
    ((0,), ((2, 0), (1, 0))),
    # Algorithm 3: two carriers (1 and 2), each with its own modulator.
    ((0, 1), ((3, 1), (2, 0))),
    # Algorithm 4: three carriers (1, 2, 3) — additive-ish, each with one
    # modulator stacked.
    ((0, 1, 2), ((5, 2), (4, 1), (3, 0))),
    # Algorithm 5: four carriers (1..4) — almost additive synthesis, useful
    # for organs/pads.
    ((0, 1, 2, 3), ()),
    # Algorithm 6: feedback stack 6→1 with feedback on operator 6 — bright
    # lead with self-modulation.
    ((0,), ((5, 4), (4, 3), (3, 2), (2, 1), (1, 0))),
]


class FMSynth:
    """Six-operator FM synthesizer with selectable algorithms.

    Parameters
    ----------
    algorithm : int
        Index into the canonical algorithm table (0..5).
    operators : list[_Operator]
        Exactly 6 operators (extra entries are ignored, missing ones are
        padded with silent defaults). If None, a default bright-bell patch
        is loaded.
    """

    def __init__(self, algorithm: int = 0, operators: list[_Operator] | None = None) -> None:
        if operators is None:
            operators = self._default_patch()
        # Pad/truncate to 6 operators.
        ops = list(operators[:6])
        while len(ops) < 6:
            ops.append(_Operator(level=0.0))
        self.operators = ops
        self.algorithm = int(np.clip(algorithm, 0, len(_ALGORITHMS) - 1))

    @staticmethod
    def _default_patch() -> list[_Operator]:
        """A bright DX7-style electric-piano patch."""
        return [
            _Operator(ratio=1.0, level=0.8, mod_index=0.0, env=ADSR(0.005, 0.3, 0.6, 0.4)),
            _Operator(ratio=1.0, level=0.5, mod_index=1.2, env=ADSR(0.005, 0.2, 0.4, 0.3)),
            _Operator(ratio=2.0, level=0.3, mod_index=0.8, env=ADSR(0.005, 0.15, 0.2, 0.2)),
            _Operator(ratio=3.0, level=0.0),
            _Operator(ratio=4.0, level=0.0),
            _Operator(ratio=0.5, level=0.0),
        ]

    def render(self, freq: float, duration: float, sr: int) -> np.ndarray:
        """Render ``duration`` seconds of FM output at ``freq`` Hz."""
        n = int(round(duration * sr))
        if n <= 0:
            return np.zeros(1, dtype=np.float64)
        carriers, mod_matrix = _ALGORITHMS[self.algorithm]
        # Render each operator; resolve modulation order by iteration so
        # that downstream operators consume the already-rendered modulator
        # signal. Multiple passes handle multi-stage chains.
        rendered: list[np.ndarray | None] = [None] * 6
        for _ in range(3):
            for src, dst in mod_matrix:
                if rendered[src] is None:
                    rendered[src] = self.operators[src].render(freq, duration, sr)
                src_signal = rendered[src]
                if src_signal is None:
                    continue
                if rendered[dst] is None:
                    mod_input: np.ndarray = src_signal * self.operators[src].mod_index
                    rendered[dst] = self.operators[dst].render(
                        freq, duration, sr, mod_input=mod_input
                    )
                else:
                    mod_signal: np.ndarray = src_signal * self.operators[src].mod_index
                    rendered[dst] = self.operators[dst].render(freq, duration, sr, mod_input=mod_signal)
        # Sum carriers.
        out = np.zeros(n, dtype=np.float64)
        for idx in carriers:
            if rendered[idx] is None:
                rendered[idx] = self.operators[idx].render(freq, duration, sr)
            carrier = rendered[idx]
            if carrier is not None:
                out += carrier
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)
