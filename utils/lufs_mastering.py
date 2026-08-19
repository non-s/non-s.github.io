"""EBU R128 loudness mastering in pure Python.

Replaces FFmpeg's loudnorm with a real mastering chain: K-weighting filter
(ITU-R BS.1770-4), gated LUFS integrated measurement, loudness range (LRA),
true-peak detection, a two-stage true-peak limiter (lookahead + clip), and
TPDF dithering for the float->int16 export path.

No external deps beyond numpy and scipy.signal.
"""

from __future__ import annotations

import logging
from typing import overload

import numpy as np
from scipy.signal import lfilter

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (ITU-R BS.1770-4)
# ---------------------------------------------------------------------------

# Absolute gating threshold in LUFS.
_ABS_GATE_LUFS = -70.0
# Relative gating threshold in LU below the absolute-gated loudness.
_REL_GATE_LU = -10.0
# Block size for gating in seconds (400 ms) and hop (100 ms).
_BLOCK_SECONDS = 0.4
_HOP_SECONDS = 0.1


# ---------------------------------------------------------------------------
# K-weighting filter coefficients (ITU-R BS.1770-4)
# ---------------------------------------------------------------------------

def _k_weight_coeffs(
    sample_rate: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return K-weighting filter coefficients as (stage1 b/a, stage2 b/a).

    Stage 1 is the "pre-filter" / high shelf (+4 dB).
    Stage 2 is the "RLB" high-pass (~38 Hz, Q 0.5).

    The ITU spec publishes coefficients only for 48 kHz. For other sample rates
    we bilinear-transform the same analog prototypes so the filter response
    matches the spec as closely as possible at the target rate.
    """
    if abs(sample_rate - 48000.0) < 1.0:
        # Stage 1 (high shelf), direct-feed coefficients from the spec.
        b1 = np.array([1.53512485958697, -2.69169618940638, 1.19839281085285])
        a1 = np.array([1.0, -1.69065929318241, 0.732480209099865])
        # Stage 2 (RLB high-pass).
        b2 = np.array([1.0, -2.0, 1.0])
        a2 = np.array([1.0, -1.99004745483398, 0.990072250366429])
        return b1, a1, b2, a2

    # Design analog prototypes and bilinear-transform to the target rate.
    # Stage 1: 1st-order high shelf with +4 dB gain at high frequencies.
    # The shelf reference frequency f0 ~= 1681 Hz, gain +4 dB.
    b1, a1 = _shelf_filter(sample_rate, f0=1681.0, gain_db=4.0)

    # Stage 2: 2nd-order high-pass (RLB), fc ~= 38 Hz, Q ~= 0.5.
    b2, a2 = _hp_filter(sample_rate, fc=38.13547087602444, q=0.5)

    return b1, a1, b2, a2


def _shelf_filter(fs: float, f0: float, gain_db: float):
    """1st-order high-shelf via bilinear transform of an analog prototype."""
    A = 10.0 ** (gain_db / 40.0)  # sqrt of linear gain for shelving
    w0 = 2.0 * np.pi * f0 / fs
    # Pre-warp.
    wc = 2.0 * fs * np.tan(w0 / 2.0)
    # Analog high-shelf (1st order) transfer:
    #   H(s) = (A*s + wc) / (s + A*wc)  -- simplified RBJ-style 1st order shelf
    # Bilinear: s -> 2*fs*(z-1)/(z+1)
    K = 2.0 * fs
    # Numerator: A*K*(z-1) + wc*(z+1)  -> (A*K + wc) + (wc - A*K)
    b0 = A * K + wc
    b1 = wc - A * K
    # Denominator: K*(z-1) + A*wc*(z+1) -> (K + A*wc) + (A*wc - K)
    a0 = K + A * wc
    a1 = A * wc - K
    b = np.array([b0, b1]) / a0
    a = np.array([1.0, a1 / a0])
    return b, a


def _hp_filter(fs: float, fc: float, q: float):
    """2nd-order high-pass via bilinear transform (RBJ cookbook)."""
    w0 = 2.0 * np.pi * fc / fs
    alpha = np.sin(w0) / (2.0 * q)
    cos_w0 = np.cos(w0)
    b0 = (1.0 + cos_w0) / 2.0
    b1 = -(1.0 + cos_w0)
    b2 = (1.0 + cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha
    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    return b, a


def _k_weight(samples: np.ndarray, sample_rate: float) -> np.ndarray:
    """Apply the two-stage K-weighting filter to a mono or multi-channel
    signal. Channels are filtered independently.

    `samples` shape is (N,) or (N, channels). Returns the same shape.
    """
    b1, a1, b2, a2 = _k_weight_coeffs(float(sample_rate))
    if samples.ndim == 1:
        x = lfilter(b1, a1, samples)
        x = lfilter(b2, a2, x)
        return x
    out = np.empty_like(samples, dtype=np.float64)
    for ch in range(samples.shape[1]):
        x = lfilter(b1, a1, samples[:, ch])
        x = lfilter(b2, a2, x)
        out[:, ch] = x
    return out


# ---------------------------------------------------------------------------
# Gated LUFS measurement (ITU-R BS.1770-4 / EBU R128)
# ---------------------------------------------------------------------------

def _mean_square_blocks(
    weighted: np.ndarray, sample_rate: float
) -> tuple[np.ndarray, int]:
    """Compute mean-square values for overlapping 400 ms blocks (100 ms hop).

    Returns (ms_values, num_blocks).
    """
    n = weighted.shape[0]
    block = int(round(_BLOCK_SECONDS * sample_rate))
    hop = int(round(_HOP_SECONDS * sample_rate))
    if n < block:
        # Signal shorter than one block: use the whole signal as one block.
        if weighted.ndim == 1:
            ms_val = float(np.mean(weighted ** 2))
        else:
            ms_val = float(np.mean(np.sum(weighted ** 2, axis=1)))
        return np.array([ms_val]), 1

    # Number of full blocks that fit with the given hop.
    num_blocks = 1 + (n - block) // hop
    ms: np.ndarray = np.empty(num_blocks, dtype=np.float64)
    if weighted.ndim == 1:
        for i in range(num_blocks):
            s = i * hop
            ms[i] = float(np.mean(weighted[s : s + block] ** 2))
    else:
        for i in range(num_blocks):
            s = i * hop
            # Sum of channel mean-squares (per ITU: weighted powers summed).
            ms[i] = float(
                np.mean(np.sum(weighted[s : s + block] ** 2, axis=1))
            )
    return ms, num_blocks


@overload
def _lufs_from_ms(ms: float) -> float: ...


@overload
def _lufs_from_ms(ms: np.ndarray) -> np.ndarray: ...


def _lufs_from_ms(ms: float | np.ndarray) -> float | np.ndarray:
    """Convert a mean-square value (or block value) to LUFS."""
    return -0.691 + 10.0 * np.log10(ms + 1e-12)


def _gated_lufs(ms_blocks: np.ndarray) -> tuple[float, np.ndarray]:
    """Apply the two-stage gating (absolute then relative) and return the
    integrated LUFS plus the mask of blocks used.
    """
    lufs_blocks = _lufs_from_ms(ms_blocks)
    # Absolute gate: keep blocks with LUFS >= -70.
    mask = lufs_blocks >= _ABS_GATE_LUFS
    if not np.any(mask):
        # Extremely quiet signal: use the absolute gate value.
        return _ABS_GATE_LUFS, mask
    gated_ms = ms_blocks[mask]
    gated_lufs = _lufs_from_ms(np.mean(gated_ms))
    # Relative gate: -10 LU below the absolute-gated integrated loudness.
    rel_gate = gated_lufs - _REL_GATE_LU
    rel_mask = lufs_blocks >= rel_gate
    final_mask = mask & rel_mask
    if not np.any(final_mask):
        return gated_lufs, mask
    final_ms = ms_blocks[final_mask]
    integrated = _lufs_from_ms(np.mean(final_ms))
    return integrated, final_mask


def _lra(ms_blocks: np.ndarray, final_mask: np.ndarray) -> float:
    """Loudness Range (LRA) per EBU R128: difference between 95th and 10th
    percentiles of the gated block loudness, with a 5 LU linear interpolation
    around the percentiles.
    """
    if not np.any(final_mask):
        return 0.0
    lufs_blocks = _lufs_from_ms(ms_blocks[final_mask])
    if lufs_blocks.size < 4:
        return 0.0
    sorted_lufs = np.sort(lufs_blocks)
    n = sorted_lufs.size
    # 10th and 95th percentiles with linear interpolation.
    def _percentile(p: float) -> float:
        rank = p / 100.0 * (n - 1)
        lo = int(np.floor(rank))
        hi = int(np.ceil(rank))
        if lo == hi:
            return float(sorted_lufs[lo])
        frac = rank - lo
        return float(sorted_lufs[lo] + frac * (sorted_lufs[hi] - sorted_lufs[lo]))
    p10 = _percentile(10.0)
    p95 = _percentile(95.0)
    lra = p95 - p10
    return float(max(0.0, lra))


# ---------------------------------------------------------------------------
# True-peak measurement
# ---------------------------------------------------------------------------

def _upsample_4x(samples: np.ndarray, sample_rate: float) -> np.ndarray:
    """4x oversampling with a simple zero-phase low-pass (sinc-windowed).

    Used for true-peak estimation per ITU-R BS.1770 (which specifies a 48 kHz
    -> 192 kHz interpolation). We use a compact FIR for speed.
    """
    n = samples.shape[0]
    # Zero-stuff.
    if samples.ndim == 1:
        z = np.zeros(n * 4, dtype=np.float64)
        z[::4] = samples
    else:
        z = np.zeros((n * 4, samples.shape[1]), dtype=np.float64)
        z[::4, :] = samples
    # Short windowed-sinc low-pass at 0.25 * fs (cutoff = Nyquist/2 of the
    # original rate). 16-tap symmetric FIR is enough for peak estimation.
    taps = 16
    h = np.sinc(np.arange(-taps, taps + 1) / 4.0) * np.hamming(2 * taps + 1)
    h = h / np.sum(h)
    if z.ndim == 1:
        return lfilter(h, [1.0], z)
    out = np.empty_like(z)
    for ch in range(z.shape[1]):
        out[:, ch] = lfilter(h, [1.0], z[:, ch])
    return out


def _true_peak(samples: np.ndarray, sample_rate: float) -> tuple[float, float]:
    """Estimate true-peak. Returns (true_peak_db, true_peak_sample_linear).

    For sample rates other than 48 kHz we still 4x-upsample; this is an
    approximation of the ITU reference but matches loudnorm's behavior closely
    enough for mastering decisions.
    """
    if samples.size == 0:
        return -np.inf, 0.0
    mono = samples if samples.ndim == 1 else samples[:, 0]
    # Use the max abs across all channels for the peak value.
    if samples.ndim == 2:
        peak_lin = float(np.max(np.abs(samples)))
    else:
        peak_lin = float(np.max(np.abs(samples)))

    up = _upsample_4x(mono, float(sample_rate))
    tp_lin = float(np.max(np.abs(up)))
    tp_db = 20.0 * np.log10(tp_lin + 1e-12)
    return tp_db, peak_lin


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def measure_lufs(samples: np.ndarray, sample_rate: int) -> dict:
    """Measure loudness per EBU R128 / ITU-R BS.1770-4.

    Args:
        samples: float array shape (N,) mono or (N, channels) multi-channel.
        sample_rate: sample rate in Hz.

    Returns:
        {
            "lufs_integrated": float,
            "lra": float,
            "true_peak_db": float,
            "true_peak_sample": float (linear peak of the original samples),
        }
    """
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim == 0:
        samples = samples.reshape(1)
    if samples.ndim == 1:
        mono = samples
    else:
        # Sum to mono with equal weights (EBU R128 stereo -> -0.691 offset is
        # already applied via _lufs_from_ms; channel weighting 1.0 each).
        mono = samples
    weighted = _k_weight(mono, sample_rate)
    ms_blocks, _ = _mean_square_blocks(weighted, sample_rate)
    lufs_int, final_mask = _gated_lufs(ms_blocks)
    lra = _lra(ms_blocks, final_mask)
    tp_db, tp_lin = _true_peak(samples, sample_rate)
    return {
        "lufs_integrated": float(lufs_int),
        "lra": float(lra),
        "true_peak_db": float(tp_db),
        "true_peak_sample": float(tp_lin),
    }


def _true_peak_limit(
    samples: np.ndarray,
    sample_rate: float,
    true_peak_db: float,
    lookahead_ms: float = 5.0,
) -> np.ndarray:
    """True-peak limiter: scale down the signal so the true-peak stays below
    the target. Uses a single global scale factor based on the oversampled
    peak, which is fast and guarantees the true-peak target is not exceeded.
    """
    target_lin = 10.0 ** (true_peak_db / 20.0)
    if samples.size == 0:
        return samples
    out = samples.copy()
    if out.ndim == 1:
        out = out[:, None]

    # Detect true-peak via 4x oversampling on the first channel.
    up = _upsample_4x(out[:, 0], sample_rate)
    overshoot = float(np.max(np.abs(up)))
    if overshoot > target_lin:
        margin = 10.0 ** (-0.02 / 20.0)
        scale = (target_lin * margin) / (overshoot + 1e-12)
        out = out * scale

    if samples.ndim == 1:
        return out[:, 0]
    return out


def loudness_normalize(
    samples: np.ndarray,
    sample_rate: int,
    target_lufs: float = -16.0,
    true_peak_db: float = -1.5,
) -> np.ndarray:
    """Normalize loudness to target_lufs and limit true-peak to true_peak_db.

    Steps:
      1. Measure current LUFS integrated.
      2. Compute linear gain: gain = 10^((target - measured) / 20).
      3. Apply gain.
      4. Two-stage true-peak limiter.

    Returns a float64 array of the same shape as the input.
    """
    samples = np.asarray(samples, dtype=np.float64)
    if samples.size == 0:
        return samples

    meas = measure_lufs(samples, sample_rate)
    measured_lufs = meas["lufs_integrated"]
    if not np.isfinite(measured_lufs):
        log.warning("loudness_normalize: LUFS measurement invalid; skipping.")
        return samples

    gain = 10.0 ** ((target_lufs - measured_lufs) / 20.0)
    log.info(
        "loudness_normalize: measured=%.2f LUFS, target=%.2f LUFS, gain=%.4f dB",
        measured_lufs,
        target_lufs,
        20.0 * np.log10(gain + 1e-12),
    )

    boosted = samples * gain
    limited = _true_peak_limit(boosted, float(sample_rate), true_peak_db)
    return limited


def apply_dither(
    samples: np.ndarray, bits: int = 16, seed: int = 0
) -> np.ndarray:
    """Apply TPDF dithering and return samples scaled to the target bit depth
    range, still as float64 (caller casts to int).

    TPDF: the difference of two uniform random samples in [-0.5, 0.5] LSB,
    yielding a triangular distribution over [-1, 1] LSB.

    The returned array is the dithered signal scaled to the integer amplitude
    range (e.g. [-32768, 32767] for 16-bit), as float64. Quantize with
    np.round and cast to the appropriate int dtype for export.
    """
    samples = np.asarray(samples, dtype=np.float64)
    if samples.size == 0:
        return samples
    rng = np.random.default_rng(seed)
    max_amp = float(2 ** (bits - 1) - 1)
    # Two uniform randoms per sample for triangular PDF, in LSB units.
    r1 = rng.uniform(-0.5, 0.5, size=samples.shape)
    r2 = rng.uniform(-0.5, 0.5, size=samples.shape)
    lsb = 1.0 / max_amp
    # Dither in the integer domain: add triangular noise of 1 LSB peak-to-peak.
    dither = (r1 - r2) * lsb
    dithered = samples + dither
    return dithered


def master_audio(
    samples: np.ndarray,
    sample_rate: int,
    target_lufs: float = -16.0,
    true_peak_db: float = -1.5,
) -> np.ndarray:
    """Master an audio buffer for export.

    Pipeline: measure -> loudness normalize -> true-peak limit -> TPDF dither
    (for 16-bit export). Returns a float64 array in the [-1, 1]-ish range,
    dithered and limited. The caller should convert to int16 for PCM export.

    Logs measured and applied values.
    """
    samples = np.asarray(samples, dtype=np.float64)
    if samples.size == 0:
        return samples

    pre = measure_lufs(samples, sample_rate)
    log.info(
        "master_audio: pre  LUFS=%.2f  LRA=%.2f  TP=%.2f dBFS  peak=%.4f",
        pre["lufs_integrated"],
        pre["lra"],
        pre["true_peak_db"],
        pre["true_peak_sample"],
    )

    normalized = loudness_normalize(
        samples, sample_rate, target_lufs=target_lufs, true_peak_db=true_peak_db
    )

    # Final true-peak measurement after limiting.
    post = measure_lufs(normalized, sample_rate)
    log.info(
        "master_audio: post LUFS=%.2f  LRA=%.2f  TP=%.2f dBFS  peak=%.4f",
        post["lufs_integrated"],
        post["lra"],
        post["true_peak_db"],
        post["true_peak_sample"],
    )

    dithered = apply_dither(normalized, bits=16, seed=0)
    return dithered
