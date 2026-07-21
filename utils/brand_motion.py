"""Animated-layer helpers for the pinned loop clips (chat, 2026-07-21 growth pass).

scripts/generate_brand_scenes.py's stars()/rain() draw one static frame --
fine for the upload thumbnail, but the pinned *video* clip looped that
exact same frame for the Short/mix/live's whole duration, which reads as
inert next to competing lofi channels whose backgrounds actually move
(falling rain, twinkling stars, a spinning record). These functions draw
the same look at a given phase 0.0-1.0 of a loop instead of a fixed
instant, so scripts/generate_brand_loops.py can render N frames that tile
into a seamless, mathematically exact loop: every periodic motion here
(rain scroll, star twinkle, glow pulse, steam drift, turntable spin) is
driven by an integer number of full cycles across the loop, so frame N's
state is bit-for-bit frame 0's -- no crossfade needed to hide the seam,
unlike the real-footage live-clip crossfade technique described in the
README.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter

RAIN_BLUE = (170, 195, 225)


def animated_rain(
    w: int, h: int, n: int, seed: int, phase: float, angle_deg: float = 12, cycles: int = 2
) -> Image.Image:
    """Same look as generate_brand_scenes.rain(), but streaks scroll
    downward over the loop. `phase` is 0.0-1.0 through the loop; each
    streak's y-position is wrapped modulo (h + 200), so phase=1.0 renders
    pixel-identical to phase=0.0 (an integer number of tile-heights of
    scroll has passed)."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rnd = random.Random(seed)
    ang = math.radians(angle_deg)
    dx, dy = math.sin(ang), math.cos(ang)
    tile = h + 200
    scroll = phase * cycles * tile
    for _ in range(n):
        x0 = rnd.randint(-int(h * dx) - 50, w + 50)
        y0 = rnd.randint(0, tile)
        length = rnd.randint(40, 110)
        a = rnd.randint(30, 90)
        width = rnd.choice([1, 1, 2])
        y0 = (y0 + scroll) % tile - 100
        x1, y1 = x0 + dx * length, y0 + dy * length
        d.line([x0, y0, x1, y1], fill=(*RAIN_BLUE, a), width=width)
    return layer


def animated_stars(
    w: int, h: int, n: int, seed: int, phase: float, y_max_ratio: float = 1.0, cycles: int = 3
) -> Image.Image:
    """Same star field as generate_brand_scenes.stars(), twinkling in
    place (brightness oscillates) instead of fixed -- each star gets its
    own phase offset so they don't all pulse in lockstep. `cycles` full
    brightness cycles per loop keeps phase=1.0 identical to phase=0.0."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.randint(0, w), rnd.randint(0, int(h * y_max_ratio))
        r = rnd.choice([1, 1, 1, 2])
        base = rnd.randint(140, 210)
        amp = rnd.randint(30, 55)
        star_phase = rnd.random()
        b = int(base + amp * (0.5 + 0.5 * math.sin(2 * math.pi * (cycles * phase + star_phase))))
        d.ellipse([x, y, x + r, y + r], fill=(b, b, b))
    return layer


def pulsing_glow(
    w: int,
    h: int,
    cx: int,
    cy: int,
    radius: int,
    phase: float,
    color: tuple[int, int, int],
    base_strength: int = 150,
    amp: int = 18,
    cycles: int = 1,
) -> Image.Image:
    """Same look as generate_brand_scenes.amber_glow(), breathing gently
    -- `cycles` full pulses per loop."""
    strength = base_strength + amp * math.sin(2 * math.pi * cycles * phase)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(radius, 0, -6):
        a = max(0, int(strength * (1 - r / radius) ** 2))
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, a))
    return glow.filter(ImageFilter.GaussianBlur(16))


def rising_steam(
    w: int, h: int, sx: float, sy: float, phase: float, cycles: int = 1, rise_height: float = 130, seed: int = 0
) -> Image.Image:
    """Two wisps of steam rising from (sx, sy), looping seamlessly: each
    wisp's vertical offset is `phase` scrolled through one full
    `rise_height` tile (wrapped modulo), so the wisp leaving the top
    re-enters at the bottom in lockstep -- phase=1.0 is identical to
    phase=0.0."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, ox in enumerate((-10, 12)):
        offset = (phase * cycles * rise_height + i * rise_height / 2) % rise_height
        pts = []
        for t in range(40):
            local_y = (t * (rise_height / 40) + offset) % rise_height
            yy = sy - local_y
            xx = sx + ox + math.sin(t * 0.35 + i + phase * 2 * math.pi) * 10
            pts.append((xx, yy))
        d.line(pts, fill=(255, 255, 255, 80), width=3)
    return layer.filter(ImageFilter.GaussianBlur(2))


def turntable_spin_offset(radius: float, phase: float, cycles: int = 1) -> tuple[float, float]:
    """Offset (dx, dy) for the record label's off-center highlight dot,
    orbiting `cycles` full turns per loop -- reads as the platter
    spinning. phase=1.0 gives the same angle as phase=0.0."""
    angle = 2 * math.pi * cycles * phase
    return math.cos(angle) * radius * 0.35, math.sin(angle) * radius * 0.12


def lightning_flash(
    w: int,
    h: int,
    phase: float,
    flash_phases: tuple[float, ...],
    *,
    flash_width: float = 0.012,
    color: tuple[int, int, int] = (232, 238, 255),
) -> Image.Image:
    """A brief full-frame flash overlay for a storm scene.

    `flash_phases` are phase positions (0.0-1.0) within the loop where a
    flash peaks; each one decays sharply over `flash_width` of the loop so
    it reads as an instant of lightning, not a strobing background.
    Distance to each flash phase is measured on the circle (wrapping
    0.0/1.0 together), so this is loop-safe regardless of where a flash is
    placed -- including right at the seam."""
    intensity = 0.0
    for flash_phase in flash_phases:
        distance = abs(phase - flash_phase)
        distance = min(distance, 1.0 - distance)
        local = max(0.0, 1.0 - distance / flash_width)
        intensity = max(intensity, local**3)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if intensity <= 0:
        return layer
    return Image.new("RGBA", (w, h), (*color, int(200 * intensity)))
