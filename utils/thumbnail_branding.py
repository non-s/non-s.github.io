"""Stamp the Amber Hours look onto a raw b-roll thumbnail still.

generate_lofi_short.py's and generate_lofi_mix.py's _extract_thumbnail()
grab a bare ffmpeg frame from the rendered video -- no branding, no text,
just whatever the b-roll happened to look like at that timestamp. That
frame is what a viewer sees next to every other lofi channel's thumbnail,
so it needs to visibly say "Amber Hours" the way _assets/branding/
thumbnail_1280x720.png (the live stream's thumbnail) already does: night
sky, skyline silhouette, amber glow. This module composites that same look
onto the per-video still, in place, so Shorts and the horizontal mix carry
one consistent identity instead of an unbranded frame grab. The live
thumbnail itself is a hand-made static asset and is untouched here.

Approved as a design direction in chat on 2026-07-18 (mockups generated
with the same palette lifted from thumbnail_1280x720.png); text is drawn
with plain vector shapes rather than emoji glyphs since a raster image
can't rely on the runner having a color-emoji font installed.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from utils.lofi_branding import HOOK_BY_MOOD

log = logging.getLogger(__name__)

PURPLE_TOP = (42, 32, 63)
PURPLE_MID = (35, 27, 53)
AMBER_MID = (241, 157, 85)
CREAM = (255, 217, 168)
NIGHT_BLUE = (24, 19, 41)

_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def _hook_words(mood: str) -> str:
    """Short 2-3 word thumbnail hook, derived from the same table branded_title() uses."""
    hook, _emoji = HOOK_BY_MOOD.get(mood.lower(), (mood, ""))
    stripped = hook[: -len(" Anime Lofi")] if hook.endswith(" Anime Lofi") else hook
    return stripped.strip() or "Cozy"


def _vgrad(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    im = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        im.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return im.resize((w, h))


def _stars(draw: ImageDraw.ImageDraw, w: int, h: int, n: int, seed: int) -> None:
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.choice([1, 1, 2])
        b = rnd.randint(150, 255)
        draw.ellipse([x, y, x + r, y + r], fill=(b, b, b))


def _amber_glow(w: int, h: int, cx: int, cy: int, radius: int) -> Image.Image:
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(radius, 0, -6):
        a = int(150 * (1 - r / radius) ** 2)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*AMBER_MID, a))
    return glow.filter(ImageFilter.GaussianBlur(16))


def _skyline(w: int, h: int, base_y: int, seed: int = 7, max_h_ratio: float = 0.22) -> Image.Image:
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
                    d.rectangle([wx, wy, wx + bw * 0.08, wy + bh * 0.06], fill=CREAM)
                wy += bh * 0.18
            wx += bw * 0.18
        x += bw + rnd.randint(6, 18)
    return im


def _moon(w: int, h: int, cx: int, cy: int, r: int) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CREAM)
    d.ellipse([cx - r + int(r * 0.35), cy - r, cx + r + int(r * 0.35), cy + r], fill=(0, 0, 0, 0))
    return im


def _draw_wordmark(im: Image.Image, xy: tuple[int, int], size: int, *, align: str = "left") -> None:
    """`xy` is the top-left corner for align="left" (default); for
    align="right" it's the top-*right* corner instead -- the text is
    measured and shifted left so it still ends exactly at xy[0], for
    layouts that put the wordmark in a right-hand corner."""
    d = ImageDraw.Draw(im, "RGBA")
    font = _font(size)
    x, y = xy
    if align == "right":
        x -= int(d.textlength("AMBER HOURS", font=font))
    d.text((x, y), "AMBER HOURS", font=font, fill=CREAM, stroke_width=max(2, size // 14), stroke_fill=PURPLE_TOP)


# Every video used to get the exact same thumbnail composition -- same
# corner for the accent art, same corner for the text -- which reads as
# repetitive across a channel page or search results grid full of them.
# Both brand_short_thumbnail() and brand_mix_thumbnail() now pick one of a
# few layouts at random per video (or take an explicit `layout` for tests/
# the retroactive rebrand script) so the grid doesn't look like one
# template copy-pasted N times. Every layout still obeys the same two
# hard invariants the tests below pin down: the short's exact center pixel
# is always real, unbranded footage, and the mix's exact center pixel is
# always inside the real b-roll inset window -- only where the decoration
# and text sit around that untouched center changes.
SHORT_LAYOUTS = ("bottom", "top")
MIX_LAYOUTS = ("classic", "mirror")


def brand_short_thumbnail(thumb_path: Path, mood: str, layout: str | None = None) -> None:
    """In-place: overlay a scrim + skyline/moon accent + hook text onto the
    real full-bleed vertical still (1080x1920) _extract_thumbnail() already
    grabbed. The footage stays the dominant visual; only a strip carries the
    brand -- at the bottom for layout="bottom" (text bottom-left, accent
    top-right), or flipped for layout="top" (text top-left, accent
    bottom-right). `layout` defaults to a random pick from SHORT_LAYOUTS."""
    layout = layout or random.choice(SHORT_LAYOUTS)
    base = Image.open(thumb_path).convert("RGB")
    w, h = base.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    top_layout = layout == "top"

    scrim_h = int(h * 0.32)
    if top_layout:
        scrim = _vgrad(w, scrim_h, NIGHT_BLUE, (0, 0, 0)).convert("RGBA")
        alpha_col = Image.new("L", (1, scrim_h))
        for y in range(scrim_h):
            alpha_col.putpixel((0, y), int(200 * (1 - y / max(scrim_h - 1, 1))))
        scrim.putalpha(alpha_col.resize((w, scrim_h)))
        overlay.paste(scrim, (0, 0), scrim)
        glow_cy, moon_cy = int(h * 0.9), int(h * 0.92)
    else:
        scrim = _vgrad(w, scrim_h, (0, 0, 0), NIGHT_BLUE).convert("RGBA")
        alpha_col = Image.new("L", (1, scrim_h))
        for y in range(scrim_h):
            alpha_col.putpixel((0, y), int(200 * (y / max(scrim_h - 1, 1))))
        scrim.putalpha(alpha_col.resize((w, scrim_h)))
        overlay.paste(scrim, (0, h - scrim_h), scrim)
        glow_cy, moon_cy = int(h * 0.1), int(h * 0.08)

    overlay = Image.alpha_composite(overlay, _amber_glow(w, h, int(w * 0.86), glow_cy, int(w * 0.35)))
    overlay = Image.alpha_composite(overlay, _moon(w, h, int(w * 0.86), moon_cy, int(w * 0.05)))
    overlay = Image.alpha_composite(overlay, _skyline(w, h, h, seed=hash(mood) & 0xFFFF, max_h_ratio=0.13))

    composited = Image.alpha_composite(base.convert("RGBA"), overlay)
    d = ImageDraw.Draw(composited, "RGBA")
    _draw_wordmark(composited, (int(w * 0.05), int(h * 0.03)), int(h * 0.028))

    hook = _hook_words(mood).upper()
    hook_font = _font(int(h * 0.055))
    hook_y = int(h * 0.12) if top_layout else int(h * 0.70)
    d.multiline_text(
        (int(w * 0.06), hook_y),
        hook.replace(" ", "\n") if len(hook) > 10 else hook,
        font=hook_font,
        fill=CREAM,
        stroke_width=max(3, int(h * 0.006)),
        stroke_fill=PURPLE_TOP,
        spacing=int(h * 0.01),
    )

    composited.convert("RGB").save(thumb_path, quality=90)


def brand_mix_thumbnail(thumb_path: Path, mood: str, layout: str | None = None) -> None:
    """In-place: rebuild the horizontal still (1920x1080) as a poster --
    illustrated skyline/moon/amber-glow frame (matching the live thumbnail)
    with the real b-roll still inset as a rounded window, hook text + brand
    wordmark over the frame. layout="classic" (default pool member) puts the
    accent glow/moon top-right, wordmark top-left, hook badge bottom-left;
    layout="mirror" flips the accent to top-left and the wordmark/badge to
    the right-hand corners. The inset photo window's position doesn't move
    between layouts, so the real footage always stays under the exact
    center of the frame either way. `layout` defaults to a random pick from
    MIX_LAYOUTS."""
    layout = layout or random.choice(MIX_LAYOUTS)
    mirror = layout == "mirror"
    photo = Image.open(thumb_path).convert("RGB")
    w, h = photo.size

    canvas = _vgrad(w, h, PURPLE_TOP, PURPLE_MID).convert("RGBA")
    d = ImageDraw.Draw(canvas, "RGBA")
    _stars(d, w, h, int(w * h / 9000), seed=hash(mood) & 0xFFFF)
    glow_cx = int(w * 0.14) if mirror else int(w * 0.86)
    moon_cx = int(w * 0.2) if mirror else int(w * 0.8)
    canvas = Image.alpha_composite(canvas, _amber_glow(w, h, glow_cx, int(h * 0.42), int(w * 0.24)))
    canvas = Image.alpha_composite(canvas, _moon(w, h, moon_cx, int(h * 0.16), int(w * 0.035)))
    canvas = Image.alpha_composite(canvas, _skyline(w, h, int(h * 0.92), seed=(hash(mood) & 0xFFFF) + 1))

    panel = (int(w * 0.22), int(h * 0.19), int(w * 0.76), int(h * 0.76))
    pw, ph = panel[2] - panel[0], panel[3] - panel[1]
    photo_fit = photo.copy()
    src_ratio, dst_ratio = photo.width / photo.height, pw / ph
    if src_ratio > dst_ratio:
        new_w = int(photo.height * dst_ratio)
        x0 = (photo.width - new_w) // 2
        photo_fit = photo.crop((x0, 0, x0 + new_w, photo.height))
    else:
        new_h = int(photo.width / dst_ratio)
        y0 = (photo.height - new_h) // 2
        photo_fit = photo.crop((0, y0, photo.width, y0 + new_h))
    photo_fit = photo_fit.resize((pw, ph))

    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=int(min(pw, ph) * 0.05), fill=255)
    canvas.paste(photo_fit, (panel[0], panel[1]), mask)

    d = ImageDraw.Draw(canvas, "RGBA")
    hook = _hook_words(mood).upper()
    hook_font = _font(int(h * 0.035))
    badge_w = min(int(w * 0.4), len(hook) * int(h * 0.024) + int(w * 0.06))

    if mirror:
        _draw_wordmark(canvas, (int(w * 0.95), int(h * 0.05)), int(h * 0.07), align="right")
        badge = (int(w * 0.95) - badge_w, int(h * 0.82), int(w * 0.95), int(h * 0.9))
    else:
        _draw_wordmark(canvas, (int(w * 0.05), int(h * 0.05)), int(h * 0.07))
        badge = (int(w * 0.05), int(h * 0.82), int(w * 0.05) + badge_w, int(h * 0.9))
    d.rounded_rectangle(badge, radius=int(h * 0.02), fill=(200, 56, 58))
    d.text((badge[0] + int(w * 0.015), badge[1] + int(h * 0.015)), hook, font=hook_font, fill=CREAM)

    canvas.convert("RGB").save(thumb_path, quality=90)
