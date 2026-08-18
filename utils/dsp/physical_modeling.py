"""Physical modeling for strings (Karplus-Strong / waveguide).

Karplus-Strong is the simplest physical-model string synthesis: a short
noise burst is fed into a delay line whose length equals the desired
period, and the delay line is closed through a low-pass filter. The result
is a decaying periodic tone whose pitch tracks the delay length — the
same technique used by the classic Yamaha DX-series "plucked string" voice.

We also implement an extended waveguide with dispersion and damping
filters for richer timbres.

Public API:
- ``KarplusStrong`` — plucked string synthesizer.
- ``WaveguideString`` — extended waveguide with first-order damping,
  dispersion allpass, and bridge pickup position.
"""

from __future__ import annotations

import numpy as np


class KarplusStrong:
    """Karplus-Strong plucked string.

    Parameters
    ----------
    decay : float
        Feedback coefficient of the delay line (0.99 = long sustain, 0.5
        = fast decay). Values close to 1 produce natural string decay.
    blend : float
        Blend factor of the low-pass filter (0 = hard LPF, 1 = bypass).
        Lower values produce a duller tone.
    """

    def __init__(self, decay: float = 0.996, blend: float = 0.5, seed: int = 0) -> None:
        self.decay = float(np.clip(decay, 0.0, 0.9999))
        self.blend = float(np.clip(blend, 0.0, 1.0))
        self.seed = int(seed)

    def render(self, freq: float, duration: float, sr: int, velocity: float = 1.0) -> np.ndarray:
        n = int(round(duration * sr))
        if n <= 0 or freq <= 0.0:
            return np.zeros(1, dtype=np.float64)
        # Delay length in samples — this defines the pitch.
        delay = max(2, int(round(sr / freq)))
        # Seed the delay line with a short noise burst (the "pluck").
        rng = np.random.default_rng(self.seed)
        burst_len = max(1, min(delay, int(0.003 * sr)))  # 3ms attack noise
        buffer = np.zeros(delay + n, dtype=np.float64)
        burst = rng.standard_normal(burst_len) * velocity
        buffer[:burst_len] = burst
        # Karplus-Strong: y[i] = decay * (blend * y[i-delay] + (1-blend) * y[i-delay+1])
        # — a one-pole LPF in the feedback loop.
        out = np.zeros(n, dtype=np.float64)
        for i in range(delay, delay + n):
            prev = buffer[i - delay]
            prev2 = buffer[i - delay + 1]
            buffer[i] = self.decay * (self.blend * prev + (1.0 - self.blend) * prev2)
            out[i - delay] = buffer[i]
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)


class WaveguideString:
    """Extended waveguide string with damping and dispersion.

    Adds a first-order damping filter (controls high-frequency decay
    independently of the loop gain) and an all-pass dispersion filter
    (slight inharmonicity, characteristic of real strings). A bridge
    pickup position allows varying the tone color (closer to the bridge
    = brighter, "sul ponticello").

    Parameters
    ----------
    decay : float
        Loop gain (0.99 = long, 0.5 = short).
    damping : float
        First-order damping coefficient (0.0 = none, 0.9 = strong HF decay).
    dispersion : float
        All-pass dispersion amount (0.0 = none, 0.5 = strong inharmonicity).
    bridge_pos : float
        Pickup position along the string (0.0 = nut, 0.5 = middle, 1.0
        = bridge). Affects which harmonics are emphasised.
    """

    def __init__(
        self,
        decay: float = 0.996,
        damping: float = 0.3,
        dispersion: float = 0.0,
        bridge_pos: float = 0.3,
        seed: int = 0,
    ) -> None:
        self.decay = float(np.clip(decay, 0.0, 0.9999))
        self.damping = float(np.clip(damping, 0.0, 0.95))
        self.dispersion = float(np.clip(dispersion, 0.0, 0.9))
        self.bridge_pos = float(np.clip(bridge_pos, 0.0, 1.0))
        self.seed = int(seed)

    def render(self, freq: float, duration: float, sr: int, velocity: float = 1.0) -> np.ndarray:
        n = int(round(duration * sr))
        if n <= 0 or freq <= 0.0:
            return np.zeros(1, dtype=np.float64)
        delay = max(2, int(round(sr / freq)))
        # Two delay lines: one going each direction. The bridge_pos controls
        # where the output is sampled (comb filtering the harmonics).
        rng = np.random.default_rng(self.seed)
        burst_len = max(1, min(delay, int(0.003 * sr)))
        left = np.zeros(delay + n, dtype=np.float64)
        right = np.zeros(delay + n, dtype=np.float64)
        left[:burst_len] = rng.standard_normal(burst_len) * velocity
        right[:burst_len] = rng.standard_normal(burst_len) * velocity
        # Damping filter: y[i] = (1-d)*x[i] + d*y[i-1]
        damp_state_l = 0.0
        damp_state_r = 0.0
        # Dispersion all-pass: y[i] = -a*x[i] + x[i-1] + a*y[i-1]
        a = self.dispersion
        disp_state_l = 0.0
        disp_state_r = 0.0
        pickup_offset = max(1, int(delay * self.bridge_pos))
        out = np.zeros(n, dtype=np.float64)
        for i in range(delay, delay + n):
            # Left-going wave: pick from right delay line (reflection).
            src_r = right[i - delay]
            damped = (1.0 - self.damping) * src_r + self.damping * damp_state_l
            damp_state_l = damped
            disp = -a * damped + disp_state_l + a * disp_state_l
            disp_state_l = damped
            left[i] = self.decay * disp
            # Right-going wave: pick from left delay line (reflection).
            src_l = left[i - delay]
            damped_r = (1.0 - self.damping) * src_l + self.damping * damp_state_r
            damp_state_r = damped_r
            disp_r = -a * damped_r + disp_state_r + a * disp_state_r
            disp_state_r = damped_r
            right[i] = self.decay * disp_r
            # Pickup at bridge_pos: comb filter by adding delayed copy.
            out_idx = i - delay
            if out_idx >= 0 and out_idx < n:
                pickup_l = left[i] if i + pickup_offset < left.size else 0.0
                pickup_r = right[i] if i + pickup_offset < right.size else 0.0
                # Output is the sum of the two waves at the pickup point.
                out[out_idx] = 0.5 * (pickup_l + pickup_r)
        peak = float(np.max(np.abs(out))) if out.size else 1.0
        if peak > 1e-12:
            out = out / peak
        return out.astype(np.float64)
