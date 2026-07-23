"""
utils/thumbnail_engine.py — cria thumbnails profissionais para Shorts e vídeos horizontais.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

log = logging.getLogger(__name__)

# Paleta Pata Jazz (dark, acolhedora, jazz)
PALETTE = {
    "bg": "#0f0f23",
    "accent": "#f4a261",
    "text": "#f8f8ff",
    "subtle": "#2a2a40",
    "gradient_start": "#1a1a3e",
    "gradient_end": "#0f0f23",
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


def extract_frame_from_video(video_path: Path, timestamp: str = "00:00:01") -> Image.Image | None:
    """Extrai um frame específico do vídeo usando FFmpeg."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        
        cmd = [
            "ffmpeg",
            "-ss", timestamp,
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            "-y",
            tmp_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            img = Image.open(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)
            return img
        else:
            log.warning("FFmpeg falhou ao extrair frame: %s", result.stderr)
            Path(tmp_path).unlink(missing_ok=True)
            return None
    except Exception as e:
        log.error("Erro ao extrair frame do vídeo: %s", e)
        return None


def enhance_thumbnail_image(img: Image.Image) -> Image.Image:
    """Aplica melhorias de imagem para destacar a thumbnail."""
    # Aumenta saturação e contraste
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.3)  # +30% saturação
    
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)  # +20% contraste
    
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.1)  # +10% brilho
    
    # Aplica leve sharpen
    img = img.filter(ImageFilter.SHARPEN)
    
    return img


def create_gradient_background(width: int, height: int) -> Image.Image:
    """Cria um fundo com gradiente suave."""
    img = Image.new("RGB", (width, height), PALETTE["gradient_start"])
    draw = ImageDraw.Draw(img)
    
    for y in range(height):
        r = int(
            int(PALETTE["gradient_start"][1:3], 16) * (1 - y/height) + 
            int(PALETTE["gradient_end"][1:3], 16) * (y/height)
        )
        g = int(
            int(PALETTE["gradient_start"][3:5], 16) * (1 - y/height) + 
            int(PALETTE["gradient_end"][3:5], 16) * (y/height)
        )
        b = int(
            int(PALETTE["gradient_start"][5:7], 16) * (1 - y/height) + 
            int(PALETTE["gradient_end"][5:7], 16) * (y/height)
        )
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    return img


def make_horizontal_thumbnail(
    hook: str,
    emoji: str,
    output: Path,
    brand: str = "Pata Jazz",
    video_path: Path | None = None,
) -> None:
    """Thumbnail 1280x720 para vídeos longos horizontais."""
    width, height = 1280, 720
    
    # Tenta usar frame do vídeo se disponível
    background = None
    if video_path and video_path.exists():
        background = extract_frame_from_video(video_path, "00:00:02")
        if background:
            background = background.resize((width, height), Image.Resampling.LANCZOS)
            background = enhance_thumbnail_image(background)
            # Aplica overlay escuro para melhor legibilidade
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 128))
            background = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")
    
    if not background:
        background = create_gradient_background(width, height)
    
    img = background
    draw = ImageDraw.Draw(img)

    font_large, font_small = _load_fonts()

    # Borda com glow effect
    for i in range(3, 0, -1):
        draw.rounded_rectangle(
            [40 - i*2, 40 - i*2, width - 40 + i*2, height - 40 + i*2],
            radius=40,
            outline=(*PALETTE["accent"][1:], int(50 * i / 3)),
            width=2
        )
    
    draw.rounded_rectangle(
        [40, 40, width - 40, height - 40], radius=40, outline=PALETTE["subtle"], width=4
    )

    # Emoji com shadow
    bbox = draw.textbbox((0, 0), emoji, font=font_large)
    tw = bbox[2] - bbox[0]
    x_center = (width - tw) // 2
    
    # Shadow
    draw.text((x_center + 4, 104), emoji, font=font_large, fill=(0, 0, 0, 128))
    # Principal
    draw.text((x_center, 100), emoji, font=font_large, fill=PALETTE["accent"])

    # Hook com wrap e shadow
    lines = textwrap.wrap(hook, width=22)
    y = 280
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        
        # Shadow
        draw.text((x + 2, y + 2), line, font=font_small, fill=(0, 0, 0, 180))
        # Principal
        draw.text((x, y), line, font=font_small, fill=PALETTE["text"])
        y += 70

    # Marca com destaque
    bbox = draw.textbbox((0, 0), brand, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, height - 120), brand, font=font_small, fill=PALETTE["accent"])

    img.save(output, quality=95)
    log.info("Thumbnail horizontal salva: %s", output)


def make_short_thumbnail(
    hook: str,
    emoji: str,
    output: Path,
    brand: str = "Pata Jazz",
    video_path: Path | None = None,
) -> None:
    """Thumbnail 1080x1920 para Shorts verticais."""
    width, height = 1080, 1920
    
    # Tenta usar frame do vídeo se disponível
    background = None
    if video_path and video_path.exists():
        background = extract_frame_from_video(video_path, "00:00:01")
        if background:
            # Crop central para formato vertical
            bg_width, bg_height = background.size
            target_ratio = width / height
            
            if bg_width / bg_height > target_ratio:
                # Vídeo é mais largo, crop horizontal
                new_width = int(bg_height * target_ratio)
                left = (bg_width - new_width) // 2
                background = background.crop((left, 0, left + new_width, bg_height))
            else:
                # Vídeo é mais alto, crop vertical
                new_height = int(bg_width / target_ratio)
                top = (bg_height - new_height) // 2
                background = background.crop((0, top, bg_width, top + new_height))
            
            background = background.resize((width, height), Image.Resampling.LANCZOS)
            background = enhance_thumbnail_image(background)
            # Aplica overlay escuro para melhor legibilidade
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 100))
            background = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")
    
    if not background:
        background = create_gradient_background(width, height)
    
    img = background
    draw = ImageDraw.Draw(img)

    font_large, font_small = _load_fonts()

    # Borda sutil
    draw.rounded_rectangle(
        [60, 60, width - 60, height - 60], radius=60, outline=PALETTE["subtle"], width=6
    )

    # Emoji grande com shadow
    bbox = draw.textbbox((0, 0), emoji, font=font_large)
    tw = bbox[2] - bbox[0]
    x_center = (width - tw) // 2
    
    # Shadow
    draw.text((x_center + 6, 526), emoji, font=font_large, fill=(0, 0, 0, 128))
    # Principal
    draw.text((x_center, 520), emoji, font=font_large, fill=PALETTE["accent"])

    # Hook com wrap e shadow
    lines = textwrap.wrap(hook, width=18)
    y = 760
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        
        # Shadow
        draw.text((x + 3, y + 3), line, font=font_small, fill=(0, 0, 0, 180))
        # Principal
        draw.text((x, y), line, font=font_small, fill=PALETTE["text"])
        y += 90

    # Marca com destaque
    bbox = draw.textbbox((0, 0), brand, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, height - 220), brand, font=font_small, fill=PALETTE["accent"])

    img.save(output, quality=95)
    log.info("Thumbnail de Short salva: %s", output)
