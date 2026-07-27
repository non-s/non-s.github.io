"""
utils/thumbnail_engine.py — cria thumbnails profissionais para Shorts e vídeos horizontais.
"""

from __future__ import annotations

import io
import logging
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

log = logging.getLogger(__name__)

_YOUTUBE_THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024  # 2 MB limite da YouTube API


def _save_under_2mb(img: Image.Image, output: Path) -> None:
    """Salva a imagem garantindo que o arquivo final tenha menos de 2 MB.

    A YouTube API rejeita thumbnails maiores que 2 MB (MediaUploadSizeError).
    Reduz a qualidade JPEG progressivamente; se ainda assim exceder o limite,
    redimensiona mantendo aspecto ate caber.

    Para PNG (lossless), o parametro ``quality`` e ignorado - o loop de
    qualidades 95->30 nao reduz o tamanho, so desperdica CPU. Pula direto
    para o redimensionamento se a primeira tentativa PNG nao couber.
    """
    is_png = output.suffix.lower() == ".png"
    fmt = "PNG" if is_png else "JPEG"
    # Para PNG, so testa uma vez (quality e ignorado); para JPEG, itera.
    qualities = (95,) if is_png else (95, 85, 75, 60, 45, 30)
    for quality in qualities:
        buf = io.BytesIO()
        img.save(buf, format=fmt, quality=quality)
        if buf.tell() <= _YOUTUBE_THUMBNAIL_MAX_BYTES:
            output.write_bytes(buf.getvalue())
            log.info("Thumbnail salva (%s, quality=%s, %.0f KB)", output.name, quality, buf.tell() / 1024)
            return
        if not is_png:
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

# Variante B para A/B testing de thumbnails: accent trocado (vermelho-terracota
# em vez do laranja-pessego default) e gradiente invertido. Hook wrap_width
# menor (texto maior, mais impacto visual) e aplicado no caller via cfg.
PALETTE_B = {
    "bg": "#0f0f23",
    "accent": "#e76f51",
    "text": "#f8f8ff",
    "subtle": "#2a2a40",
    "gradient_start": "#0f0f23",
    "gradient_end": "#1a1a3e",
}

# Variante C: hook truncado (texto menor, wrap_width maior) + emoji gigante
# (fonte 2x maior). Usa a paleta default de A, mas com emoji maior para
# gerar impacto visual diferente sem mudar cores.
PALETTE_C = {
    "bg": "#0f0f23",
    "accent": "#f4a261",
    "text": "#f8f8ff",
    "subtle": "#2a2a40",
    "gradient_start": "#1a1a3e",
    "gradient_end": "#0f0f23",
}


def _palette_for(variant: str) -> dict:
    """Seleciona a paleta pela variante (A=default, B=accent trocado/gradiente
    invertido, C=mesma paleta de A mas emoji maior via _emoji_font_size)."""
    if variant == "B":
        return PALETTE_B
    if variant == "C":
        return PALETTE_C
    return PALETTE


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


def _load_font_path() -> str | None:
    """Retorna o caminho da primeira fonte TrueType disponivel, ou None."""
    candidates = [
        "arial.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for font_path in candidates:
        try:
            ImageFont.truetype(font_path, 16)
            return font_path
        except Exception:
            continue
    return None


def _fonts_for_variant(variant: str) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """Carrega fontes com tamanho adequado por variante.

    Variante C usa emoji 2x maior (font_large 2x) e hook menor (font_small
    reduzido) para impacto visual diferente sem mudar a paleta.
    """
    font_path = _load_font_path()
    if font_path is None:
        raise RuntimeError(
            "Nenhuma fonte TrueType encontrada. Instale DejaVu/arial ou configure PIL_IMAGE_FONT_PATH."
        )
    if variant == "C":
        # Emoji 2x maior, hook menor.
        return ImageFont.truetype(font_path, 240), ImageFont.truetype(font_path, 40)
    return ImageFont.truetype(font_path, 120), ImageFont.truetype(font_path, 48)


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


def create_gradient_background(width: int, height: int, palette: dict | None = None) -> Image.Image:
    """Cria um fundo com gradiente suave (vertical).

    Gera duas imagens solidas com as cores de inicio e fim, depois mistura
    usando uma mascara em gradiente (Image.linear_gradient, Pillow >=9.1).
    Muito mais rapido que o loop linha-a-linha anterior.
    """
    pal = palette if palette is not None else PALETTE
    start_img = Image.new("RGB", (width, height), _hex_to_rgb(pal["gradient_start"]))
    end_img = Image.new("RGB", (width, height), _hex_to_rgb(pal["gradient_end"]))
    # linear_gradient("L") gera 256x256; redimensiona para o tamanho final
    # e usa como mascara alpha para o paste do end_img sobre o start_img.
    mask = Image.linear_gradient("L").resize((width, height))
    start_img.paste(end_img, (0, 0), mask)
    return start_img


@dataclass
class _LayoutConfig:
    border_margin: int
    border_radius: int
    border_width: int
    emoji_y: int
    emoji_shadow_offset: tuple[int, int]
    hook_y_start: int
    hook_wrap_width: int
    hook_line_height: int
    brand_y: int
    crop_target_ratio: float | None
    overlay_alpha: int
    frame_timestamp: str


def _render_thumbnail(
    width: int,
    height: int,
    hook: str,
    emoji: str,
    output: Path,
    brand: str,
    video_path: Path | None,
    layout_config: _LayoutConfig,
    variant: str = "A",
) -> None:
    """Pipeline compartilhado de renderizacao de thumbnail.

    ``variant`` ("A" default, "B" ou "C") seleciona a paleta/fonte:
    - A: paleta default, fonte 120/48.
    - B: accent trocado + gradiente invertido, wrap width menor (texto
      maior, mais impacto visual).
    - C: hook truncado (wrap_width maior, texto menor) + emoji gigente
      (fonte 2x maior) — mesmo esquema de paleta de A.
    """
    cfg = layout_config
    pal = _palette_for(variant)
    if variant == "B":
        wrap_width = max(8, cfg.hook_wrap_width - 4)
    elif variant == "C":
        # Hook menor (texto maior via wrap_width maior = mais chars por
        # linha, fonte pequena).
        wrap_width = cfg.hook_wrap_width + 6
    else:
        wrap_width = cfg.hook_wrap_width

    # Tenta usar frame do vídeo se disponível
    background = None
    if video_path and video_path.exists():
        background = extract_frame_from_video(video_path, cfg.frame_timestamp)
        if background:
            if cfg.crop_target_ratio is not None:
                # Crop central para o formato alvo
                bg_width, bg_height = background.size
                target_ratio = cfg.crop_target_ratio

                if bg_width / bg_height > target_ratio:
                    new_width = int(bg_height * target_ratio)
                    left = (bg_width - new_width) // 2
                    background = background.crop((left, 0, left + new_width, bg_height))
                else:
                    new_height = int(bg_width / target_ratio)
                    top = (bg_height - new_height) // 2
                    background = background.crop((0, top, bg_width, top + new_height))

            background = background.resize((width, height), Image.Resampling.LANCZOS)
            background = enhance_thumbnail_image(background)
            # Aplica overlay escuro para melhor legibilidade
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, cfg.overlay_alpha))
            background = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")

    if not background:
        background = create_gradient_background(width, height, pal)

    # Converte para RGBA para que fills com alpha (shadows) funcionem.
    img = background.convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_large, font_small = _fonts_for_variant(variant)

    # Borda com glow effect
    for i in range(3, 0, -1):
        draw.rounded_rectangle(
            [cfg.border_margin - i*2, cfg.border_margin - i*2,
             width - cfg.border_margin + i*2, height - cfg.border_margin + i*2],
            radius=cfg.border_radius,
            outline=(*_hex_to_rgb(pal["accent"]), int(50 * i / 3)),
            width=2
        )

    draw.rounded_rectangle(
        [cfg.border_margin, cfg.border_margin,
         width - cfg.border_margin, height - cfg.border_margin],
        radius=cfg.border_radius, outline=pal["subtle"], width=cfg.border_width
    )

    # Emoji com shadow
    bbox = draw.textbbox((0, 0), emoji, font=font_large)
    tw = bbox[2] - bbox[0]
    x_center = (width - tw) // 2

    sx, sy = cfg.emoji_shadow_offset
    # Shadow
    draw.text((x_center + sx, cfg.emoji_y + sy), emoji, font=font_large, fill=(0, 0, 0, 128))
    # Principal
    draw.text((x_center, cfg.emoji_y), emoji, font=font_large, fill=pal["accent"])

    # Hook com wrap e shadow
    lines = textwrap.wrap(hook, width=wrap_width)
    y = cfg.hook_y_start
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2

        # Shadow
        draw.text((x + 2, y + 2), line, font=font_small, fill=(0, 0, 0, 180))
        # Principal
        draw.text((x, y), line, font=font_small, fill=pal["text"])
        y += cfg.hook_line_height

    # Marca com destaque
    bbox = draw.textbbox((0, 0), brand, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, cfg.brand_y), brand, font=font_small, fill=pal["accent"])

    _save_under_2mb(img.convert("RGB"), output)


def make_horizontal_thumbnail(
    hook: str,
    emoji: str,
    output: Path,
    brand: str = "Pata Jazz",
    video_path: Path | None = None,
    variant: str = "A",
) -> None:
    """Thumbnail 1280x720 para vídeos longos horizontais."""
    width, height = 1280, 720
    cfg = _LayoutConfig(
        border_margin=40,
        border_radius=40,
        border_width=4,
        emoji_y=100,
        emoji_shadow_offset=(4, 4),
        hook_y_start=280,
        hook_wrap_width=22,
        hook_line_height=70,
        brand_y=height - 120,
        crop_target_ratio=None,
        overlay_alpha=128,
        frame_timestamp="00:00:02",
    )
    _render_thumbnail(width, height, hook, emoji, output, brand, video_path, cfg, variant=variant)
    log.info("Thumbnail horizontal salva: %s (variante %s)", output, variant)


def make_short_thumbnail(
    hook: str,
    emoji: str,
    output: Path,
    brand: str = "Pata Jazz",
    video_path: Path | None = None,
    variant: str = "A",
) -> None:
    """Thumbnail 1080x1920 para Shorts verticais."""
    width, height = 1080, 1920
    cfg = _LayoutConfig(
        border_margin=60,
        border_radius=60,
        border_width=6,
        emoji_y=520,
        emoji_shadow_offset=(6, 6),
        hook_y_start=760,
        hook_wrap_width=18,
        hook_line_height=90,
        brand_y=height - 220,
        crop_target_ratio=width / height,
        overlay_alpha=100,
        frame_timestamp="00:00:01",
    )
    _render_thumbnail(width, height, hook, emoji, output, brand, video_path, cfg, variant=variant)
    log.info("Thumbnail de Short salva: %s (variante %s)", output, variant)
