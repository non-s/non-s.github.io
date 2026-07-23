"""
utils/thumbnail_engine.py — cria thumbnails profissionais para Shorts e vídeos horizontais.
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# Paleta Pata Jazz (dark, acolhedora, jazz)
PALETTE = {
    "bg": "#0f0f23",
    "accent": "#f4a261",
    "text": "#f8f8ff",
    "subtle": "#2a2a40",
}


def _load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """Tenta carregar fontes comuns; cai em default se necessário."""
    candidates = [
        ("arial.ttf", 120, 48),
        ("DejaVuSans.ttf", 120, 48),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 120, 48),
        ("C:/Windows/Fonts/arial.ttf", 120, 48),
    ]
    for font_path, large, small in candidates:
        try:
            return ImageFont.truetype(font_path, large), ImageFont.truetype(font_path, small)
        except Exception:
            continue
    default = ImageFont.load_default()
    return default, default


def make_horizontal_thumbnail(hook: str, emoji: str, output: Path, brand: str = "Pata Jazz") -> None:
    """Thumbnail 1280x720 para vídeos longos horizontais."""
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), PALETTE["bg"])
    draw = ImageDraw.Draw(img)

    font_large, font_small = _load_fonts()

    # Borda sutil
    draw.rounded_rectangle(
        [40, 40, width - 40, height - 40], radius=40, outline=PALETTE["subtle"], width=4
    )

    # Emoji
    bbox = draw.textbbox((0, 0), emoji, font=font_large)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, 100), emoji, font=font_large, fill=PALETTE["accent"])

    # Hook com wrap
    lines = textwrap.wrap(hook, width=22)
    y = 280
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, y), line, font=font_small, fill=PALETTE["text"])
        y += 70

    # Marca
    bbox = draw.textbbox((0, 0), brand, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, height - 120), brand, font=font_small, fill=PALETTE["accent"])

    img.save(output)
    log.info("Thumbnail horizontal salva: %s", output)


def make_short_thumbnail(hook: str, emoji: str, output: Path, brand: str = "Pata Jazz") -> None:
    """Thumbnail 1080x1920 para Shorts verticais."""
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), PALETTE["bg"])
    draw = ImageDraw.Draw(img)

    font_large, font_small = _load_fonts()

    # Borda sutil
    draw.rounded_rectangle(
        [60, 60, width - 60, height - 60], radius=60, outline=PALETTE["subtle"], width=6
    )

    # Emoji grande
    bbox = draw.textbbox((0, 0), emoji, font=font_large)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, 520), emoji, font=font_large, fill=PALETTE["accent"])

    # Hook
    lines = textwrap.wrap(hook, width=18)
    y = 760
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, y), line, font=font_small, fill=PALETTE["text"])
        y += 90

    # Marca
    bbox = draw.textbbox((0, 0), brand, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, height - 220), brand, font=font_small, fill=PALETTE["accent"])

    img.save(output)
    log.info("Thumbnail de Short salva: %s", output)
