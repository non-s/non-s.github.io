#!/usr/bin/env python3
"""Render the pinned b-roll clips as seamless *animated* loops (chat, growth
pass 2026-07-21).

Every format's pinned clip (`_assets/video/pinned_short_clip.mp4`,
`pinned_mix_clip.mp4`, `pinned_live_clips/rain_window_01.mp4`) used to be a
single static frame stretched to video with ffmpeg -stream_loop -- the
audit that kicked off this pass flagged that as the single biggest
differentiator gap against channels whose backgrounds actually move
(falling rain, twinkling stars, a spinning record). This renders each
scene as `LOOP_FRAMES` frames instead of one, using utils/brand_motion.py's
phase-driven layers so frame `LOOP_FRAMES` is bit-for-bit frame 0 -- no
crossfade needed, unlike the real-footage live-clip technique -- then
encodes each sequence with ffmpeg into the same file the existing
pipeline already loops via `-stream_loop -1` (generate_lofi_short.py,
generate_lofi_mix.py, scripts/live_stream_dynamic.py). The upload
thumbnail stays the separate static PNG in _assets/branding/ (unchanged);
only the video content gains motion.

Shares its drawing vocabulary/palette with scripts/generate_brand_scenes.py
(the static-PNG thumbnail generator) so the two stay visually consistent;
only the animated layers (rain, stars, glow, steam, turntable) come from
utils/brand_motion.py.

Not part of the publish pipeline; run by hand when the art needs a
refresh, then commit the resulting mp4s (ffmpeg must be on PATH).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_brand_scenes import (  # noqa: E402
    AMBER_MID,
    CREAM,
    NIGHT_BLUE,
    PURPLE_DEEP,
    PURPLE_MID,
    PURPLE_TOP,
    moon,
    rounded_badge,
    skyline,
    vgrad,
    wordmark,
)
from utils.brand_motion import (  # noqa: E402
    animated_rain,
    animated_stars,
    pulsing_glow,
    rising_steam,
    turntable_spin_offset,
)

log = logging.getLogger("generate_brand_loops")
logging.basicConfig(level=logging.INFO)

LOOP_FPS = 20
LOOP_SECONDS = 4
LOOP_FRAMES = (
    LOOP_FPS * LOOP_SECONDS
)  # 80 -- long enough not to feel like a obvious repeat, short enough to render fast
_RAIN_PX_PER_S = 260  # roughly matches generate_lofi_short.py's zoompan pacing -- readable, not a blur


def _rain_cycles(h: int) -> int:
    tile = h + 200
    return max(1, round(_RAIN_PX_PER_S * LOOP_SECONDS / tile))


def _pot_and_mug(
    canvas: Image.Image,
    w: int,
    h: int,
    phase: float,
    *,
    pot_x,
    pot_y,
    pot_w,
    pot_h,
    mug_x,
    mug_y,
    mug_w,
    mug_h,
    seed: int,
) -> None:
    """Static potted plant + steaming mug -- identical geometry to
    generate_brand_scenes.build_shorts(), only the steam animates."""
    d = ImageDraw.Draw(canvas, "RGBA")
    d.polygon(
        [
            (pot_x - pot_w * 0.4, pot_y),
            (pot_x + pot_w * 0.4, pot_y),
            (pot_x + pot_w * 0.32, pot_y + pot_h),
            (pot_x - pot_w * 0.32, pot_y + pot_h),
        ],
        fill=NIGHT_BLUE,
    )
    import random as _random

    rnd = _random.Random(seed)
    for _ in range(7):
        lx = pot_x + rnd.randint(-int(pot_w * 0.3), int(pot_w * 0.3))
        ly = pot_y
        lr = rnd.randint(int(pot_w * 0.18), int(pot_w * 0.3))
        d.ellipse([lx - lr, ly - lr * 1.6, lx + lr, ly - lr * 0.2], fill=(60, 110, 90))

    d.rounded_rectangle([mug_x - mug_w / 2, mug_y, mug_x + mug_w / 2, mug_y + mug_h], radius=6, fill=CREAM)
    d.arc(
        [mug_x + mug_w * 0.35, mug_y + mug_h * 0.15, mug_x + mug_w * 0.75, mug_y + mug_h * 0.85],
        -90,
        90,
        fill=CREAM,
        width=4,
    )
    steam = rising_steam(w, h, mug_x, mug_y, phase, cycles=1, rise_height=h * 0.07, seed=seed)
    canvas.alpha_composite(steam) if canvas.mode == "RGBA" else canvas.paste(steam, (0, 0), steam)


def build_shorts_frame(phase: float) -> Image.Image:
    """1080x1920 vertical -- rainy window over the skyline, animated."""
    w, h = 1080, 1920
    canvas = vgrad(w, h, PURPLE_DEEP, PURPLE_TOP).convert("RGBA")

    canvas = Image.alpha_composite(canvas, animated_stars(w, h, 140, seed=101, phase=phase, y_max_ratio=0.55))
    canvas = Image.alpha_composite(
        canvas,
        pulsing_glow(w, h, int(w * 0.62), int(h * 0.62), int(w * 0.62), phase, AMBER_MID, base_strength=120, amp=14),
    )
    canvas = Image.alpha_composite(canvas, moon(w, h, int(w * 0.22), int(h * 0.16), int(w * 0.075)))
    canvas = Image.alpha_composite(canvas, skyline(w, h, int(h * 0.74), seed=42, max_h_ratio=0.24))
    canvas = Image.alpha_composite(
        canvas, animated_rain(w, h, 260, seed=7, phase=phase, angle_deg=14, cycles=_rain_cycles(h))
    )

    sill_top = int(h * 0.78)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rectangle([0, sill_top, w, h], fill=(*PURPLE_DEEP, 235))
    d.rectangle([0, sill_top, w, sill_top + int(h * 0.012)], fill=(*NIGHT_BLUE, 255))

    _pot_and_mug(
        canvas,
        w,
        h,
        phase,
        pot_x=int(w * 0.14),
        pot_y=int(h * 0.86),
        pot_w=int(w * 0.16),
        pot_h=int(h * 0.07),
        mug_x=int(w * 0.82),
        mug_y=int(h * 0.855),
        mug_w=int(w * 0.11),
        mug_h=int(h * 0.035),
        seed=3,
    )

    wordmark(canvas, (int(w * 0.07), int(h * 0.035)), int(h * 0.032))
    rounded_badge(canvas, (int(w * 0.07), int(h * 0.1), int(w * 0.4), int(h * 0.032)), "RAINY NIGHT LOFI")

    return canvas.convert("RGB")


def build_mix_frame(phase: float) -> Image.Image:
    """1920x1080 horizontal -- turntable + headphones listening nook, animated."""
    w, h = 1920, 1080
    canvas = vgrad(w, h, PURPLE_DEEP, PURPLE_MID).convert("RGBA")

    canvas = Image.alpha_composite(
        canvas, animated_stars(w, h, int(w * h / 7000), seed=202, phase=phase, y_max_ratio=0.6)
    )
    canvas = Image.alpha_composite(
        canvas,
        pulsing_glow(w, h, int(w * 0.5), int(h * 0.78), int(w * 0.42), phase, AMBER_MID, base_strength=140, amp=16),
    )
    canvas = Image.alpha_composite(canvas, moon(w, h, int(w * 0.88), int(h * 0.18), int(w * 0.028)))
    canvas = Image.alpha_composite(canvas, skyline(w, h, int(h * 0.86), seed=88, max_h_ratio=0.32))

    d = ImageDraw.Draw(canvas, "RGBA")
    desk_top = int(h * 0.80)
    desk = vgrad(w, h - desk_top, (58, 40, 34), (34, 22, 20)).convert("RGBA")
    canvas.paste(desk, (0, desk_top), desk)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rectangle([0, desk_top, w, desk_top + int(h * 0.006)], fill=(*AMBER_MID, 200))

    tt_cx, tt_cy = int(w * 0.28), int(h * 0.905)
    tt_r = int(h * 0.15)
    d.rounded_rectangle(
        [tt_cx - tt_r * 1.35, tt_cy - tt_r * 0.5, tt_cx + tt_r * 1.35, tt_cy + tt_r * 0.65],
        radius=14,
        fill=(24, 18, 22),
    )
    d.ellipse([tt_cx - tt_r, tt_cy - tt_r * 0.55, tt_cx + tt_r, tt_cy + tt_r * 0.45], fill=(10, 8, 18))
    for rr in range(int(tt_r * 0.25), int(tt_r), 10):
        d.ellipse(
            [tt_cx - rr, tt_cy - tt_r * 0.05 - rr * 0.4, tt_cx + rr, tt_cy - tt_r * 0.05 + rr * 0.4],
            outline=(60, 52, 78),
            width=1,
        )
    label_dx, label_dy = turntable_spin_offset(tt_r * 0.16, phase, cycles=1)
    d.ellipse(
        [
            tt_cx - tt_r * 0.16 + label_dx,
            tt_cy - tt_r * 0.17 + label_dy,
            tt_cx + tt_r * 0.16 + label_dx,
            tt_cy + tt_r * 0.09 + label_dy,
        ],
        fill=AMBER_MID,
    )
    arm_base = (tt_cx + tt_r * 0.95, tt_cy - tt_r * 0.42)
    arm_tip = (tt_cx + tt_r * 0.05, tt_cy - tt_r * 0.12)
    d.line([arm_base, arm_tip], fill=(210, 200, 190), width=6)
    d.ellipse([arm_base[0] - 10, arm_base[1] - 10, arm_base[0] + 10, arm_base[1] + 10], fill=(210, 200, 190))

    rec_x, rec_y = int(w * 0.42), int(h * 0.94)
    for i in range(4):
        ox, oy = i * 7, -i * 3
        d.rounded_rectangle(
            [rec_x + ox - 70, rec_y + oy - 90, rec_x + ox + 70, rec_y + oy + 6],
            radius=6,
            fill=(18 + i * 4, 14 + i * 3, 24 + i * 4),
            outline=(70, 60, 62),
            width=2,
        )
    d.ellipse([rec_x - 28, rec_y - 96, rec_x + 32, rec_y - 40], fill=CREAM)
    d.ellipse([rec_x - 6, rec_y - 74, rec_x + 10, rec_y - 58], fill=(24, 18, 22))

    hp_cx, hp_cy = int(w * 0.72), int(h * 0.895)
    hp_r = int(h * 0.075)
    d.arc([hp_cx - hp_r, hp_cy - hp_r * 1.9, hp_cx + hp_r, hp_cy - hp_r * 0.3], 180, 360, fill=CREAM, width=14)
    for ex in (hp_cx - hp_r, hp_cx + hp_r):
        d.rounded_rectangle(
            [ex - int(hp_r * 0.32), hp_cy - int(hp_r * 0.55), ex + int(hp_r * 0.32), hp_cy + int(hp_r * 0.55)],
            radius=int(hp_r * 0.3),
            fill=CREAM,
        )
        d.rounded_rectangle(
            [ex - int(hp_r * 0.18), hp_cy - int(hp_r * 0.35), ex + int(hp_r * 0.18), hp_cy + int(hp_r * 0.35)],
            radius=int(hp_r * 0.18),
            fill=(30, 24, 26),
        )

    pot_x, pot_y = int(w * 0.92), int(h * 0.93)
    pot_w2 = int(w * 0.045)
    d.polygon(
        [
            (pot_x - pot_w2, pot_y),
            (pot_x + pot_w2, pot_y),
            (pot_x + pot_w2 * 0.75, pot_y + pot_w2 * 1.6),
            (pot_x - pot_w2 * 0.75, pot_y + pot_w2 * 1.6),
        ],
        fill=(24, 18, 22),
    )
    import random as _random

    rnd = _random.Random(9)
    for _ in range(6):
        lx = pot_x + rnd.randint(-int(pot_w2 * 0.6), int(pot_w2 * 0.6))
        lr = rnd.randint(int(pot_w2 * 0.4), int(pot_w2 * 0.7))
        d.ellipse([lx - lr, pot_y - lr * 1.8, lx + lr, pot_y - lr * 0.2], fill=(60, 110, 90))

    wordmark(canvas, (int(w * 0.045), int(h * 0.06)), int(h * 0.065))
    rounded_badge(canvas, (int(w * 0.045), int(h * 0.15), int(w * 0.24), int(h * 0.06)), "LOFI MIX")

    return canvas.convert("RGB")


def build_live_frame(phase: float) -> Image.Image:
    """1280x720 horizontal -- rainy window over the skyline (the 24/7 live
    loop's own scene, wider than the Shorts version so the plant and mug
    sit at the two bottom corners instead of stacked)."""
    w, h = 1280, 720
    canvas = vgrad(w, h, PURPLE_DEEP, PURPLE_TOP).convert("RGBA")

    canvas = Image.alpha_composite(canvas, animated_stars(w, h, 130, seed=303, phase=phase, y_max_ratio=0.6))
    canvas = Image.alpha_composite(
        canvas,
        pulsing_glow(w, h, int(w * 0.55), int(h * 0.55), int(w * 0.4), phase, AMBER_MID, base_strength=120, amp=14),
    )
    canvas = Image.alpha_composite(canvas, moon(w, h, int(w * 0.14), int(h * 0.2), int(w * 0.05)))
    canvas = Image.alpha_composite(canvas, skyline(w, h, int(h * 0.86), seed=51, max_h_ratio=0.28))
    canvas = Image.alpha_composite(
        canvas, animated_rain(w, h, 220, seed=13, phase=phase, angle_deg=14, cycles=_rain_cycles(h))
    )

    sill_top = int(h * 0.86)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rectangle([0, sill_top, w, h], fill=(*PURPLE_DEEP, 235))
    d.rectangle([0, sill_top, w, sill_top + int(h * 0.012)], fill=(*NIGHT_BLUE, 255))

    _pot_and_mug(
        canvas,
        w,
        h,
        phase,
        pot_x=int(w * 0.08),
        pot_y=int(h * 0.9),
        pot_w=int(w * 0.09),
        pot_h=int(h * 0.11),
        mug_x=int(w * 0.9),
        mug_y=int(h * 0.905),
        mug_w=int(w * 0.08),
        mug_h=int(h * 0.06),
        seed=11,
    )

    wordmark(canvas, (int(w * 0.05), int(h * 0.05)), int(h * 0.075))
    rounded_badge(canvas, (int(w * 0.05), int(h * 0.16), int(w * 0.32), int(h * 0.075)), "RAINY NIGHT LOFI")

    return canvas.convert("RGB")


def _encode_loop(frames_dir: Path, out_path: Path) -> bool:
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(LOOP_FPS),
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-vf",
        "format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        log.error("ffmpeg exited %d: %s", result.returncode, result.stderr[-2000:])
        return False
    return out_path.exists() and out_path.stat().st_size > 0


def render_loop(build_fn, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brand_loop_") as tmp:
        tmp_dir = Path(tmp)
        for i in range(LOOP_FRAMES):
            phase = i / LOOP_FRAMES
            frame = build_fn(phase)
            frame.save(tmp_dir / f"frame_{i:04d}.png")
        ok = _encode_loop(tmp_dir, out_path)
    if ok:
        log.info("wrote %s (%d frames, %ss loop)", out_path, LOOP_FRAMES, LOOP_SECONDS)
    return ok


def main() -> int:
    if shutil.which("ffmpeg") is None:
        log.error("ffmpeg not found on PATH -- install it before running this script.")
        return 1

    targets = [
        (build_shorts_frame, ROOT / "_assets" / "video" / "pinned_short_clip.mp4"),
        (build_mix_frame, ROOT / "_assets" / "video" / "pinned_mix_clip.mp4"),
        (build_live_frame, ROOT / "_assets" / "video" / "pinned_live_clips" / "rain_window_01.mp4"),
    ]
    ok = True
    for build_fn, out_path in targets:
        ok = render_loop(build_fn, out_path) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
