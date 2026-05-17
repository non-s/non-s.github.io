"""Drawing helpers shared between `generate_video.py` and `generate_shorts.py`.

Both scripts use Pillow for frame composition and the same handful of
font / drawing utilities. Centralised here so a fix to (say) the font
fallback chain propagates to both pipelines.
"""
from __future__ import annotations

import logging
from pathlib import Path

import requests
from PIL import ImageFont

log = logging.getLogger(__name__)

# Standard system font search paths on ubuntu-latest GitHub Actions runners.
_BOLD_FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
_REGULAR_FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def get_font(size: int, bold: bool = False):
    """Pick the first installed TTF and load it at `size`.

    Falls back to Pillow's default bitmap font if nothing is found —
    useful for local dev on systems without the Liberation/Noto fonts.
    """
    for path in (_BOLD_FONTS if bold else _REGULAR_FONTS):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill, outline=None, outline_width=2):
    """Pillow has no shortcut for outlined rounded rects — wrap the call."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=radius,
        fill=fill,
        outline=outline,
        width=outline_width,
    )


def wrap_text(draw, text, font, max_width):
    """Greedy word-wrap for a Pillow ImageDraw context. Returns a list of lines."""
    words = text.split()
    lines, line = [], []
    for word in words:
        test = " ".join(line + [word])
        if draw.textbbox((0, 0), test, font=font)[2] > max_width and line:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    return lines


_DOWNLOAD_UA = "GlobalBR-Bot/2.0"


def download_image(url: str, dest: Path, timeout: int = 12) -> bool:
    """GET an image into `dest`; True if the body is ≥2 KB and HTTP 200.

    Returns False on every error path (including small responses) so the
    caller can fall back to a placeholder gracefully.
    """
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": _DOWNLOAD_UA})
        if r.status_code == 200 and len(r.content) > 2000:
            dest.write_bytes(r.content)
            return True
    except Exception as e:
        log.debug(f"Image download failed: {e}")
    return False
