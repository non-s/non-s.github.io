#!/usr/bin/env python3
"""One-off generator for the Shorts and Mix brand scenes (chat, 2026-07-21).

An earlier revision had every format (Shorts, mix, live) share the exact
same `_assets/branding/thumbnail_1280x720.png` as both the pinned video
clip and the upload thumbnail, which read as repetitive across the
channel page. This draws two more original illustrations -- reusing the
same drawing vocabulary/palette as utils/thumbnail_branding.py for visual
consistency, but each its own composition, native to its format's aspect
ratio (no cropping/letterboxing needed downstream):

- Shorts (1080x1920, vertical): a rainy window looking out over the
  skyline, warm glow, potted plant + steaming mug on the sill.
- Mix (1920x1080, horizontal): a lofi listening nook -- turntable, a
  stack of vinyl and headphones on a desk, wide skyline behind.

The live's own thumbnail_1280x720.png is untouched -- it already reads
well and wasn't part of what needed to change.

Not part of the publish pipeline; run by hand when the art needs a
refresh, then commit the resulting PNGs (and re-render
_assets/video/pinned_short_clip.mp4 / pinned_mix_clip.mp4 from them --
see generate_lofi_short.py/generate_lofi_mix.py's PINNED_BROLL_CLIP).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]

PURPLE_TOP = (42, 32, 63)
PURPLE_MID = (35, 27, 53)
PURPLE_DEEP = (20, 15, 32)
AMBER_MID = (241, 157, 85)
CREAM = (255, 217, 168)
NIGHT_BLUE = (24, 19, 41)
RAIN_BLUE = (170, 195, 225)

# Same fallback chain as utils/thumbnail_branding.py's _font(): a real
# bold sans on whatever OS renders this, else PIL's built-in default
# rather than failing outright.
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (CI)
    "C:/Windows/Fonts/segoeuib.ttf",  # Windows
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",  # macOS
)


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def vgrad(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    im = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        im.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return im.resize((w, h))


def stars(draw: ImageDraw.ImageDraw, w: int, h: int, n: int, seed: int, y_max_ratio: float = 1.0) -> None:
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.randint(0, w), rnd.randint(0, int(h * y_max_ratio))
        r = rnd.choice([1, 1, 1, 2])
        b = rnd.randint(150, 255)
        draw.ellipse([x, y, x + r, y + r], fill=(b, b, b))


def amber_glow(w: int, h: int, cx: int, cy: int, radius: int, color=AMBER_MID, strength: int = 150) -> Image.Image:
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(radius, 0, -6):
        a = int(strength * (1 - r / radius) ** 2)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, a))
    return glow.filter(ImageFilter.GaussianBlur(16))


def skyline(w: int, h: int, base_y: int, seed: int, max_h_ratio: float = 0.22, window_color=CREAM) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rnd = random.Random(seed)
    x = -20
    while x < w + 20:
        bw = rnd.randint(int(w * 0.05), int(w * 0.11))
        bh = rnd.randint(int(h * max_h_ratio * 0.45), int(h * max_h_ratio))
        d.rectangle([x, base_y - bh, x + bw, base_y + 40], fill=NIGHT_BLUE)
        wx = x + bw * 0.15
        while wx < x + bw - bw * 0.15:
            wy = base_y - bh + bh * 0.15
            while wy < base_y - bh * 0.1:
                if rnd.random() < 0.35:
                    d.rectangle([wx, wy, wx + bw * 0.08, wy + bh * 0.06], fill=window_color)
                wy += bh * 0.18
            wx += bw * 0.18
        x += bw + rnd.randint(6, 18)
    return im


def moon(w: int, h: int, cx: int, cy: int, r: int) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CREAM)
    d.ellipse([cx - r + int(r * 0.35), cy - r, cx + r + int(r * 0.35), cy + r], fill=(0, 0, 0, 0))
    return im


def wordmark(im: Image.Image, xy: tuple[int, int], size: int, align: str = "left") -> None:
    d = ImageDraw.Draw(im, "RGBA")
    f = font(size)
    x, y = xy
    if align == "right":
        x -= int(d.textlength("AMBER HOURS", font=f))
    d.text((x, y), "AMBER HOURS", font=f, fill=CREAM, stroke_width=max(2, size // 14), stroke_fill=PURPLE_TOP)


def rain(w: int, h: int, n: int, seed: int, angle_deg: float = 12) -> Image.Image:
    """Diagonal translucent rain streaks over the whole frame."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rnd = random.Random(seed)
    ang = math.radians(angle_deg)
    dx, dy = math.sin(ang), math.cos(ang)
    for _ in range(n):
        x0 = rnd.randint(-int(h * dx), w)
        y0 = rnd.randint(-100, h)
        length = rnd.randint(40, 110)
        a = rnd.randint(30, 90)
        width = rnd.choice([1, 1, 2])
        x1, y1 = x0 + dx * length, y0 + dy * length
        d.line([x0, y0, x1, y1], fill=(*RAIN_BLUE, a), width=width)
    return layer


def rounded_badge(canvas: Image.Image, xy_wh: tuple[int, int, int, int], text: str, fill=(200, 56, 58)) -> None:
    d = ImageDraw.Draw(canvas, "RGBA")
    x, y, w, h = xy_wh
    d.rounded_rectangle([x, y, x + w, y + h], radius=int(h * 0.22), fill=fill)
    f = font(int(h * 0.5))
    tw = d.textlength(text, font=f)
    d.text((x + (w - tw) / 2, y + h * 0.18), text, font=f, fill=CREAM)


def build_shorts() -> Image.Image:
    """1080x1920 vertical -- rainy window over the skyline."""
    w, h = 1080, 1920
    canvas = vgrad(w, h, PURPLE_DEEP, PURPLE_TOP).convert("RGBA")

    d = ImageDraw.Draw(canvas, "RGBA")
    stars(d, w, h, 140, seed=101, y_max_ratio=0.55)

    canvas = Image.alpha_composite(canvas, amber_glow(w, h, int(w * 0.62), int(h * 0.62), int(w * 0.62), strength=120))
    canvas = Image.alpha_composite(canvas, moon(w, h, int(w * 0.22), int(h * 0.16), int(w * 0.075)))
    canvas = Image.alpha_composite(canvas, skyline(w, h, int(h * 0.74), seed=42, max_h_ratio=0.24))
    canvas = Image.alpha_composite(canvas, rain(w, h, 260, seed=7, angle_deg=14))

    sill_top = int(h * 0.78)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rectangle([0, sill_top, w, h], fill=(*PURPLE_DEEP, 235))
    d.rectangle([0, sill_top, w, sill_top + int(h * 0.012)], fill=(*NIGHT_BLUE, 255))

    pot_x, pot_y = int(w * 0.14), int(h * 0.86)
    pot_w, pot_h = int(w * 0.16), int(h * 0.07)
    d.polygon(
        [
            (pot_x - pot_w * 0.4, pot_y),
            (pot_x + pot_w * 0.4, pot_y),
            (pot_x + pot_w * 0.32, pot_y + pot_h),
            (pot_x - pot_w * 0.32, pot_y + pot_h),
        ],
        fill=NIGHT_BLUE,
    )
    rnd = random.Random(3)
    for _ in range(7):
        lx = pot_x + rnd.randint(-int(pot_w * 0.3), int(pot_w * 0.3))
        ly = pot_y
        lr = rnd.randint(int(pot_w * 0.18), int(pot_w * 0.3))
        d.ellipse([lx - lr, ly - lr * 1.6, lx + lr, ly - lr * 0.2], fill=(60, 110, 90))

    mug_x, mug_y = int(w * 0.82), int(h * 0.855)
    mug_w, mug_h = int(w * 0.11), int(h * 0.035)
    d.rounded_rectangle([mug_x - mug_w / 2, mug_y, mug_x + mug_w / 2, mug_y + mug_h], radius=6, fill=CREAM)
    d.arc(
        [mug_x + mug_w * 0.35, mug_y + mug_h * 0.15, mug_x + mug_w * 0.75, mug_y + mug_h * 0.85],
        -90,
        90,
        fill=CREAM,
        width=4,
    )
    steam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(steam)
    for i, sx in enumerate([mug_x - mug_w * 0.15, mug_x + mug_w * 0.1]):
        pts = []
        for t in range(40):
            yy = mug_y - t * 3
            xx = sx + math.sin(t * 0.35 + i) * 10
            pts.append((xx, yy))
        sd.line(pts, fill=(255, 255, 255, 90), width=3)
    canvas = Image.alpha_composite(canvas, steam.filter(ImageFilter.GaussianBlur(2)))

    wordmark(canvas, (int(w * 0.07), int(h * 0.035)), int(h * 0.032))
    rounded_badge(canvas, (int(w * 0.07), int(h * 0.1), int(w * 0.4), int(h * 0.032)), "RAINY NIGHT LOFI")

    return canvas.convert("RGB")


def build_mix() -> Image.Image:
    """1920x1080 horizontal -- turntable + headphones listening nook."""
    w, h = 1920, 1080
    canvas = vgrad(w, h, PURPLE_DEEP, PURPLE_MID).convert("RGBA")

    d = ImageDraw.Draw(canvas, "RGBA")
    stars(d, w, h, int(w * h / 7000), seed=202, y_max_ratio=0.6)

    canvas = Image.alpha_composite(canvas, amber_glow(w, h, int(w * 0.5), int(h * 0.78), int(w * 0.42), strength=140))
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
    d.ellipse([tt_cx - tt_r * 0.16, tt_cy - tt_r * 0.17, tt_cx + tt_r * 0.16, tt_cy + tt_r * 0.09], fill=AMBER_MID)
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
    rnd = random.Random(9)
    for _ in range(6):
        lx = pot_x + rnd.randint(-int(pot_w2 * 0.6), int(pot_w2 * 0.6))
        lr = rnd.randint(int(pot_w2 * 0.4), int(pot_w2 * 0.7))
        d.ellipse([lx - lr, pot_y - lr * 1.8, lx + lr, pot_y - lr * 0.2], fill=(60, 110, 90))

    wordmark(canvas, (int(w * 0.045), int(h * 0.06)), int(h * 0.065))
    rounded_badge(canvas, (int(w * 0.045), int(h * 0.15), int(w * 0.24), int(h * 0.06)), "LOFI MIX")

    return canvas.convert("RGB")


def main() -> int:
    out_dir = ROOT / "_assets" / "branding"
    out_dir.mkdir(parents=True, exist_ok=True)
    build_shorts().save(out_dir / "shorts_scene_1080x1920.png")
    build_mix().save(out_dir / "mix_scene_1920x1080.png")
    print(f"wrote {out_dir / 'shorts_scene_1080x1920.png'}")
    print(f"wrote {out_dir / 'mix_scene_1920x1080.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
