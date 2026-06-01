"""
utils/brand_card.py — Render a 1-second branded title card at the
start of every Short, plus a matching outro card at the end.

Why this exists
---------------
Recognisable Shorts channels can open every video with the SAME 1-2 second
animated brand stamp. The repetition is conscious — viewers learn
to associate that exact stamp with reliable content, and the
algorithm reads "this is part of a series" through the visual
hash similarity across videos.

What we ship
------------
Two pre-rendered PNGs:
  * `intro_card.png` — channel handle + tagline on the brand-color
    band, drawn over a darkened version of the first b-roll frame.
  * `outro_card.png` — sign-off + handle + "see you tomorrow".

These get prepended/appended to the b-roll FFmpeg concat chain so
every Short is `intro(0.8 s) + body + outro(2 s)` visually, with
matching audio (the persona's intro/outro lines from
utils/intro_outro). All free, all in-repo.

Cache: rendered once per (persona_hash + voice) pair and reused.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import asdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from utils.host_persona import HostPersona, load as load_persona
from utils.video_common import draw_rounded_rect, get_font

log = logging.getLogger(__name__)

BRAND_CARD_CACHE = Path(os.environ.get("BRAND_CARD_CACHE",
                                         "_data/brand_card_cache"))
SHORT_W, SHORT_H = 1080, 1920

# Brand palette — kept here as constants so the operator can adjust
# the channel's look in one place. Values are RGB.
BRAND_PRIMARY   = (0, 195, 255)        # Cyan-blue: signature highlight
BRAND_ACCENT    = (255, 200, 0)         # Mustard: secondary highlight
BRAND_DARK      = (8, 8, 18)            # Near-black: backgrounds
BRAND_TEXT      = (245, 245, 255)       # Off-white: text
BRAND_DIM       = (160, 165, 190)       # Muted: secondary text


def _persona_hash(persona: HostPersona) -> str:
    blob = "|".join(str(v) for v in asdict(persona).values())
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def render_intro_card(persona: HostPersona | None = None,
                       output_path: Path | None = None) -> Path:
    """Render the static intro card PNG. Cached on disk.

    The card is intentionally LIGHT on detail — a high-contrast brand
    block at the top, the host name + handle as the focal point, and
    a thin coloured rule. Plays for ~0.8 s so it must read instantly.
    """
    persona = persona or load_persona()
    out = output_path or (BRAND_CARD_CACHE / f"intro_{_persona_hash(persona)}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 5 * 1024:
        return out

    img = Image.new("RGB", (SHORT_W, SHORT_H), BRAND_DARK)
    draw = ImageDraw.Draw(img)

    # Top brand band — full-width strip of brand primary.
    band_h = 14
    draw.rectangle([(0, 240), (SHORT_W, 240 + band_h)], fill=BRAND_PRIMARY)

    # Big handle.
    handle_font = get_font(168, bold=True)
    handle_text = f"@{persona.handle}"
    bbox = draw.textbbox((0, 0), handle_text, font=handle_font)
    hx = (SHORT_W - bbox[2]) // 2
    hy = (SHORT_H - bbox[3]) // 2 - 220
    # Drop shadow.
    draw.text((hx + 5, hy + 5), handle_text, font=handle_font, fill=(0, 0, 0))
    draw.text((hx, hy), handle_text, font=handle_font, fill=BRAND_TEXT)

    # Host introduction line.
    sub_font = get_font(72, bold=True)
    sub_text = f"With {persona.name}"
    bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
    sx = (SHORT_W - bbox[2]) // 2
    sy = hy + 200
    draw.text((sx, sy), sub_text, font=sub_font, fill=BRAND_PRIMARY)

    # Tagline at the bottom.
    tag_font = get_font(46)
    bbox = draw.textbbox((0, 0), persona.tagline, font=tag_font)
    tx = (SHORT_W - bbox[2]) // 2
    ty = SHORT_H - 360
    draw.text((tx, ty), persona.tagline, font=tag_font, fill=BRAND_DIM)

    img.save(str(out), "PNG", optimize=True)
    log.info("  🪧 Intro card rendered: %s", out.name)
    return out


def render_outro_card(persona: HostPersona | None = None,
                       output_path: Path | None = None) -> Path:
    """Render the static outro card PNG. Cached on disk."""
    persona = persona or load_persona()
    out = output_path or (BRAND_CARD_CACHE / f"outro_{_persona_hash(persona)}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 5 * 1024:
        return out

    img = Image.new("RGB", (SHORT_W, SHORT_H), BRAND_DARK)
    draw = ImageDraw.Draw(img)

    # Mirror brand band on the bottom instead of top.
    band_h = 14
    draw.rectangle([(0, SHORT_H - 254), (SHORT_W, SHORT_H - 240)],
                    fill=BRAND_PRIMARY)

    # Big sign-off line as the focal point.
    sign_font = get_font(108, bold=True)
    sign_text = "SEE YOU TOMORROW"
    bbox = draw.textbbox((0, 0), sign_text, font=sign_font)
    sx = (SHORT_W - bbox[2]) // 2
    sy = (SHORT_H - bbox[3]) // 2 - 200
    draw.text((sx + 5, sy + 5), sign_text, font=sign_font, fill=(0, 0, 0))
    draw.text((sx, sy), sign_text, font=sign_font, fill=BRAND_TEXT)

    # Host signature.
    host_font = get_font(72, bold=True)
    host_text = f"— {persona.name}"
    bbox = draw.textbbox((0, 0), host_text, font=host_font)
    hx = (SHORT_W - bbox[2]) // 2
    hy = sy + 180
    draw.text((hx, hy), host_text, font=host_font, fill=BRAND_PRIMARY)

    # Handle as a footer.
    handle_font = get_font(54, bold=True)
    handle_text = f"@{persona.handle}"
    bbox = draw.textbbox((0, 0), handle_text, font=handle_font)
    hx = (SHORT_W - bbox[2]) // 2
    hy = SHORT_H - 360
    draw.text((hx, hy), handle_text, font=handle_font, fill=BRAND_DIM)

    img.save(str(out), "PNG", optimize=True)
    log.info("  🪧 Outro card rendered: %s", out.name)
    return out


def get_intro_outro_cards(persona: HostPersona | None = None) -> tuple[Path, Path]:
    """Return paths to the cached intro + outro PNGs, rendering on demand."""
    persona = persona or load_persona()
    return render_intro_card(persona), render_outro_card(persona)
