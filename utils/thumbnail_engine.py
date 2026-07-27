"""
utils/thumbnail_engine.py — cria thumbnails profissionais para Shorts e vídeos horizontais.
"""

from __future__ import annotations

import io
import logging
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

log = logging.getLogger(__name__)

_YOUTUBE_THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024  # 2 MB limite da YouTube API


def _save_under_2mb(img: Image.Image, output: Path) -> None:
    """Salva a imagem garantindo que o arquivo final tenha menos de 2 MB.

    A YouTube API rejeita thumbnails maiores que 2 MB (MediaUploadSizeError).
    Reduz a qualidade JPEG progressivamente; se ainda assim exceder o limite,
    redimensiona mantendo aspecto ate caber.
    """
    for quality in (95, 85, 75, 60, 45, 30):
        buf = io.BytesIO()
        img.save(buf, format="PNG" if output.suffix.lower() == ".png" else "JPEG", quality=quality)
        if buf.tell() <= _YOUTUBE_THUMBNAIL_MAX_BYTES:
            output.write_bytes(buf.getvalue())
            log.info("Thumbnail salva (%s, quality=%s, %.0f KB)", output.name, quality, buf.tell() / 1024)
            return
        log.warning("Thumbnail ainda tem %.0f KB em quality=%s; reduzindo...", buf.tell() / 1024, quality)

    # Ultimo recurso: redimensionar mantendo aspecto
    w, h = img.size
    scale = 0.75
    while w >= 200 and h >= 200:
        w, h = int(w * scale), int(h * scale)
        resized = img.resize((w, h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="PNG" if output.suffix.lower() == ".png" else "JPEG", quality=60)
        if buf.tell() <= _YOUTUBE_THUMBNAIL_MAX_BYTES:
            output.write_bytes(buf.getvalue())
            log.info("Thumbnail redimensionada para %dx%d (%.0f KB)", w, h, buf.tell() / 1024)
            return
    # Nao coube mesmo apos redimensionar: salva a menor versao mesmo assim.
    buf = io.BytesIO()
    resized.save(buf, format="PNG" if output.suffix.lower() == ".png" else "JPEG", quality=60)
    output.write_bytes(buf.getvalue())
    log.warning("Thumbnail nao coube em 2 MB mesmo apos redimensionar; salvando %.0f KB", buf.tell() / 1024)

# Paleta Pata Jazz (dark, acolhedora, jazz)
PALETTE = {
    "bg": "#0f0f23",
    "accent": "#f4a261",
    "text": "#f8f8ff",
    "subtle": "#2a2a40",
    "gradient_start": "#1a1a3e",
    "gradient_end": "#0f0f23",
}


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Converte uma cor hex '#rrggbb' em uma tupla (r, g, b)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return r, g, b


def _load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """Tenta carregar fontes comuns; falha com erro claro se nenhuma disponivel.

    Usa ImageFont.truetype com fallback em varias plataformas (Linux CI,
    Windows local). Se nenhuma fonte TrueType estiver disponivel, levanta
    RuntimeError em vez de silenciosamente usar a fonte bitmap default
    (que torna a thumbnail ilegivel).
    """
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
    raise RuntimeError(
        "Nenhuma fonte TrueType encontrada. Instale DejaVu/arial ou configure PIL_IMAGE_FONT_PATH."
    )


def extract_frame_from_video(video_path: Path, timestamp: str = "00:00:01") -> Image.Image | None:
    """Extrai um frame específico do vídeo usando FFmpeg."""
    tmp_path: str | None = None
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
            # Image.open e lazy: carrega o conteudo antes de fechar/unlink.
            img = Image.open(tmp_path)
            img.load()
            return img
        else:
            log.warning("FFmpeg falhou ao extrair frame: %s", result.stderr)
            return None
    except subprocess.TimeoutExpired:
        log.warning("FFmpeg excedeu 30s ao extrair frame de %s", video_path)
        return None
    except Exception as e:
        log.error("Erro ao extrair frame do vídeo: %s", e)
        return None
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def enhance_thumbnail_image(img: Image.Image) -> Image.Image:
    """Aplica melhorias de imagem para destacar a thumbnail."""
    # Aumenta saturação e contraste
    img = ImageEnhance.Color(img).enhance(1.3)  # +30% saturação
    img = ImageEnhance.Contrast(img).enhance(1.2)  # +20% contraste
    img = ImageEnhance.Brightness(img).enhance(1.1)  # +10% brilho

    # Aplica leve sharpen
    img = img.filter(ImageFilter.SHARPEN)

    return img


def create_gradient_background(width: int, height: int) -> Image.Image:
    """Cria um fundo com gradiente suave (vertical).

    Gera duas imagens solidas com as cores de inicio e fim, depois mistura
    usando uma mascara em gradiente (Image.linear_gradient, Pillow >=9.1).
    Muito mais rapido que o loop linha-a-linha anterior.
    """
    start_img = Image.new("RGB", (width, height), _hex_to_rgb(PALETTE["gradient_start"]))
    end_img = Image.new("RGB", (width, height), _hex_to_rgb(PALETTE["gradient_end"]))
    # linear_gradient("L") gera 256x256; redimensiona para o tamanho final
    # e usa como mascara alpha para o paste do end_img sobre o start_img.
    mask = Image.linear_gradient("L").resize((width, height))
    start_img.paste(end_img, (0, 0), mask)
    return start_img


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

    # Converte para RGBA para que fills com alpha (shadows) funcionem.
    img = background.convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_large, font_small = _load_fonts()

    # Borda com glow effect
    for i in range(3, 0, -1):
        draw.rounded_rectangle(
            [40 - i*2, 40 - i*2, width - 40 + i*2, height - 40 + i*2],
            radius=40,
            outline=(*_hex_to_rgb(PALETTE["accent"]), int(50 * i / 3)),
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

    _save_under_2mb(img.convert("RGB"), output)
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

    # Converte para RGBA para que fills com alpha (shadows) funcionem.
    img = background.convert("RGBA")
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

    _save_under_2mb(img.convert("RGB"), output)
    log.info("Thumbnail de Short salva: %s", output)
