#!/usr/bin/env python3
"""Render the animated storm scene for the rain/thunder ambience pillar
(growth pass, 2026-07-21).

Same "original Pillow illustration, not stock footage" approach and the
same seamless-loop technique as scripts/generate_brand_loops.py (an
integer number of cycles across the loop, so frame `LOOP_FRAMES` is
bit-for-bit frame 0), reusing that module's animated layers
(utils/brand_motion.py) plus a new lightning_flash for this scene
specifically. A longer loop than the other formats' 4s (14s here) so an
occasional flash doesn't repeat every few seconds; the audio bed
(utils/storm_audio.py) loops on its own, unrelated period, so the two
drift out of phase with each other rather than repeating in lockstep.

Shares the drawing vocabulary/palette conventions of
scripts/generate_brand_scenes.py (vgrad, skyline, wordmark, rounded_badge)
but a deliberately cooler, darker palette and heavier rain -- this is an
overcast storm, not a cozy clear night, so there is no moon or amber glow
here; the skyline's own lit windows are the only warm light left, keeping
a visual thread back to the rest of the channel's identity.

Not part of the publish pipeline; run by hand when the art needs a
refresh, then commit the resulting thumbnail PNG and pinned clip mp4
(ffmpeg must be on PATH). See generate_storm_ambience.py for how these
are consumed.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_brand_scenes import rounded_badge, skyline, vgrad, wordmark  # noqa: E402
from utils.brand_motion import animated_rain, animated_stars, lightning_flash  # noqa: E402

log = logging.getLogger("generate_storm_scene")
logging.basicConfig(level=logging.INFO)

W, H = 1920, 1080
SKY_TOP = (14, 17, 24)
SKY_MID = (32, 38, 50)
CLOUD_DARK = (52, 58, 72)
CREAM = (255, 217, 168)

LOOP_FPS = 20
LOOP_SECONDS = 14  # longer than the other formats' 4s loop -- see module docstring
LOOP_FRAMES = LOOP_FPS * LOOP_SECONDS
FLASH_PHASES = (0.34, 0.81)  # two flashes per 14s loop -- rare, not strobing
_RAIN_PX_PER_S = 420  # faster than the cozy scenes' ~260 -- wind-driven storm rain


def _rain_cycles(h: int) -> int:
    tile = h + 200
    return max(1, round(_RAIN_PX_PER_S * LOOP_SECONDS / tile))


def storm_clouds(w: int, h: int, seed: int, *, base_y_ratio: float = 0.42) -> Image.Image:
    """A few soft, dark cloud masses low in the sky -- same layered-blob
    radial-gradient technique as generate_brand_scenes.amber_glow(), but
    dark and desaturated instead of a warm glow."""
    import random

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rnd = random.Random(seed)
    base_y = int(h * base_y_ratio)
    for _ in range(6):
        cx = rnd.randint(0, w)
        cy = base_y + rnd.randint(-int(h * 0.05), int(h * 0.08))
        r = rnd.randint(int(w * 0.12), int(w * 0.22))
        blob = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(blob)
        for rr in range(r, 0, -8):
            a = int(190 * (1 - rr / r) ** 1.5)
            bd.ellipse([cx - rr, cy - rr * 0.5, cx + rr, cy + rr * 0.5], fill=(*CLOUD_DARK, a))
        layer = Image.alpha_composite(layer, blob.filter(ImageFilter.GaussianBlur(14)))
    return layer


def build_storm_frame(phase: float) -> Image.Image:
    """1920x1080 horizontal -- overcast storm sky over the skyline, rain
    and occasional lightning, animated."""
    canvas = vgrad(W, H, SKY_TOP, SKY_MID).convert("RGBA")

    canvas = Image.alpha_composite(canvas, animated_stars(W, H, 40, seed=411, phase=phase, y_max_ratio=0.3, cycles=4))
    canvas = Image.alpha_composite(canvas, storm_clouds(W, H, seed=17))
    canvas = Image.alpha_composite(canvas, skyline(W, H, int(H * 0.88), seed=63, max_h_ratio=0.3, window_color=CREAM))
    canvas = Image.alpha_composite(
        canvas, animated_rain(W, H, 420, seed=23, phase=phase, angle_deg=22, cycles=_rain_cycles(H))
    )
    canvas = Image.alpha_composite(canvas, lightning_flash(W, H, phase, FLASH_PHASES))

    wordmark(canvas, (int(W * 0.045), int(H * 0.06)), int(H * 0.065))
    rounded_badge(
        canvas,
        (int(W * 0.045), int(H * 0.15), int(W * 0.3), int(H * 0.06)),
        "RAIN & THUNDER",
        fill=(60, 68, 90),
    )

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
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        log.error("ffmpeg exited %d: %s", result.returncode, result.stderr[-2000:])
        return False
    return out_path.exists() and out_path.stat().st_size > 0


def render_loop(out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="storm_loop_") as tmp:
        tmp_dir = Path(tmp)
        for i in range(LOOP_FRAMES):
            phase = i / LOOP_FRAMES
            build_storm_frame(phase).save(tmp_dir / f"frame_{i:04d}.png")
        ok = _encode_loop(tmp_dir, out_path)
    if ok:
        log.info("wrote %s (%d frames, %ss loop)", out_path, LOOP_FRAMES, LOOP_SECONDS)
    return ok


def main() -> int:
    out_dir = ROOT / "_assets" / "branding"
    thumb_path = out_dir / "storm_scene_1920x1080.png"
    out_dir.mkdir(parents=True, exist_ok=True)
    build_storm_frame(0.0).save(thumb_path)
    log.info("wrote %s", thumb_path)

    if shutil.which("ffmpeg") is None:
        log.error("ffmpeg not found on PATH -- skipping pinned clip render (thumbnail was still written).")
        return 1

    clip_path = ROOT / "_assets" / "video" / "pinned_storm_clip.mp4"
    return 0 if render_loop(clip_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
