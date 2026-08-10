"""
utils/thumbnail_engine.py — cria thumbnails de CTR máximo para o Pata Jazz.

Psicologia visual aplicada (Operação Zeus):
- Rosto/animal com olhar direto + olhos destacados (gatilho de emoção).
- Contraste extremo: fundo escuro + animal claro + texto em laranja/amarelo.
- Texto curto (máx 3 palavras), fonte pesada, legível em mobile.
- Emoji como sinalizador visual.
- Elementos de curiosidade: setas, círculos, expressões de surpresa.
- Variantes A/B/C com cores de alto CTR (vermelho, laranja, amarelo).
"""

from __future__ import annotations

import io
import json
import logging
import random
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from utils.font_config import pil_font_path
from utils.paths import data_dir

log = logging.getLogger(__name__)

_YOUTUBE_THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024  # 2 MB limite da YouTube API


def _save_under_2mb(img: Image.Image, output: Path) -> None:
    """Salva a imagem garantindo que o arquivo final tenha menos de 2 MB."""
    is_png = output.suffix.lower() == ".png"
    fmt = "PNG" if is_png else "JPEG"
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
    buf = io.BytesIO()
    resized.save(buf, format="PNG" if output.suffix.lower() == ".png" else "JPEG", quality=60)
    output.write_bytes(buf.getvalue())
    log.warning("Thumbnail nao coube em 2 MB mesmo apos redimensionar; salvando %.0f KB", buf.tell() / 1024)


# Paletas de alto CTR (fundo escuro + accent quente)
PALETTE = {
    "bg": "#0f0f23",
    "accent": "#f4a261",  # laranja-pessego
    "accent2": "#e9c46a",  # amarelo
    "text": "#f8f8ff",
    "subtle": "#2a2a40",
    "gradient_start": "#1a1a3e",
    "gradient_end": "#0f0f23",
}

PALETTE_B = {
    "bg": "#0f0f23",
    "accent": "#e76f51",  # vermelho-terracota (alto CTR)
    "accent2": "#f4a261",
    "text": "#f8f8ff",
    "subtle": "#2a2a40",
    "gradient_start": "#0f0f23",
    "gradient_end": "#1a1a3e",
}

PALETTE_C = {
    "bg": "#0f0f23",
    "accent": "#f4a261",  # mantem o accent default (escala do emoji muda)
    "accent2": "#e9c46a",
    "text": "#f8f8ff",
    "subtle": "#2a2a40",
    "gradient_start": "#1a1a3e",
    "gradient_end": "#0f0f23",
}


def _palette_for(variant: str) -> dict:
    if variant == "B":
        return PALETTE_B
    if variant == "C":
        return PALETTE_C
    return PALETTE


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return r, g, b


def _load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """Carrega fontes TrueType grandes e pequenas."""
    font_path = pil_font_path()
    try:
        return ImageFont.truetype(font_path, 120), ImageFont.truetype(font_path, 48)
    except Exception as exc:
        raise RuntimeError("Nenhuma fonte TrueType encontrada. Verifique _assets/fonts/Roboto-Bold.ttf.") from exc


def _load_font_path() -> str | None:
    try:
        return pil_font_path()
    except Exception:
        return None


def _fonts_for_variant(variant: str) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    font_path = _load_font_path()
    if font_path is None:
        raise RuntimeError("Nenhuma fonte TrueType encontrada. Verifique _assets/fonts/Roboto-Bold.ttf.")
    # #5: fontes maiores para texto mais ousado e legivel em mobile.
    if variant == "C":
        return ImageFont.truetype(font_path, 280), ImageFont.truetype(font_path, 56)
    if variant == "B":
        return ImageFont.truetype(font_path, 180), ImageFont.truetype(font_path, 72)
    return ImageFont.truetype(font_path, 160), ImageFont.truetype(font_path, 64)


def extract_frame_from_video(video_path: Path, timestamp: str = "00:00:01") -> Image.Image | None:
    """Extrai um frame específico do vídeo usando FFmpeg."""
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        cmd = ["ffmpeg", "-ss", timestamp, "-i", str(video_path), "-vframes", "1", "-q:v", "2", "-y", tmp_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
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
    img = ImageEnhance.Color(img).enhance(1.3)
    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Brightness(img).enhance(1.1)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def create_gradient_background(width: int, height: int, palette: dict | None = None) -> Image.Image:
    """Cria um fundo com gradiente suave (vertical)."""
    pal = palette if palette is not None else PALETTE
    start_img = Image.new("RGB", (width, height), _hex_to_rgb(pal["gradient_start"]))
    end_img = Image.new("RGB", (width, height), _hex_to_rgb(pal["gradient_end"]))
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


_VISION_HOOK_MAX_LEN = 70
_VISION_HOOK_MIN_LEN = 12


def _vision_hook_for_frame(frame_img: Image.Image, fallback_hook: str) -> str:
    """Tenta obter um hook 'scroll-stopping' via Gemini Vision."""
    try:
        from utils.ai_helper import ai_text_with_image

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        tmp_path = Path(tmp.name)
        try:
            frame_img.save(tmp_path, format="PNG")
            prompt = (
                "Look at this video thumbnail frame. Write ONE short, scroll-stopping "
                "YouTube title (max 60 chars, English, cute tone, NO clickbait, NO quotes, "
                "NO emojis) describing what the cat or dog is doing. Return only the title text."
            )
            text = ai_text_with_image(prompt, tmp_path, task="thumbnail_vision")
        finally:
            tmp_path.unlink(missing_ok=True)

        if text:
            cleaned = " ".join(text.split()).strip().strip('"').strip("'")
            if _VISION_HOOK_MIN_LEN <= len(cleaned) <= _VISION_HOOK_MAX_LEN:
                log.info("Hook via Vision: %r (fallback era %r)", cleaned, fallback_hook)
                return cleaned
            log.debug("Hook via Vision fora do tamanho (%d chars): %r", len(cleaned), cleaned)
    except Exception as exc:
        log.debug("Vision hook falhou (fallback text-only): %s", exc)
    return fallback_hook


def _draw_curiosity_indicator(draw, width: int, height: int, palette: dict) -> None:
    """Desenha um indicador sutil de curiosidade (círculo/destaque no canto)."""
    accent = _hex_to_rgb(palette["accent"])
    # Círculo pequeno no canto superior direito para chamar atenção
    draw.ellipse([width - 120, 40, width - 40, 120], outline=(*accent, 180), width=4)


def _draw_arrow(draw, x: int, y: int, size: int, palette: dict) -> None:
    """Desenha uma seta discreta apontando para o centro (curiosidade)."""
    accent = _hex_to_rgb(palette["accent"])
    # Seta simples: triângulo
    draw.polygon([(x, y), (x + size, y + size // 2), (x, y + size)], fill=(*accent, 160))


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
    """Pipeline compartilhado de renderizacao de thumbnail."""
    cfg = layout_config
    pal = _palette_for(variant)
    if variant == "B":
        wrap_width = max(8, cfg.hook_wrap_width - 4)
    elif variant == "C":
        wrap_width = cfg.hook_wrap_width + 6
    else:
        wrap_width = cfg.hook_wrap_width

    background = None
    if video_path and video_path.exists():
        background = extract_frame_from_video(video_path, cfg.frame_timestamp)
        if background:
            if variant == "A":
                hook = _vision_hook_for_frame(background, hook)

            if cfg.crop_target_ratio is not None:
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
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, cfg.overlay_alpha))
            background = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")

    if not background:
        background = create_gradient_background(width, height, pal)

    img = background.convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_large, font_small = _fonts_for_variant(variant)

    # Borda com glow effect
    for i in range(3, 0, -1):
        draw.rounded_rectangle(
            [
                cfg.border_margin - i * 2,
                cfg.border_margin - i * 2,
                width - cfg.border_margin + i * 2,
                height - cfg.border_margin + i * 2,
            ],
            radius=cfg.border_radius,
            outline=(*_hex_to_rgb(pal["accent"]), int(50 * i / 3)),
            width=2,
        )

    draw.rounded_rectangle(
        [cfg.border_margin, cfg.border_margin, width - cfg.border_margin, height - cfg.border_margin],
        radius=cfg.border_radius,
        outline=pal["subtle"],
        width=cfg.border_width,
    )

    # Indicador de curiosidade (canto superior direito)
    _draw_curiosity_indicator(draw, width, height, pal)

    # Emoji com shadow
    bbox = draw.textbbox((0, 0), emoji, font=font_large)
    tw = bbox[2] - bbox[0]
    x_center = (width - tw) // 2

    sx, sy = cfg.emoji_shadow_offset
    draw.text((x_center + sx, cfg.emoji_y + sy), emoji, font=font_large, fill=(0, 0, 0, 128))
    draw.text((x_center, cfg.emoji_y), emoji, font=font_large, fill=pal["accent"])

    # #5: Hook curto e impactante - truncado para max 30 chars (era 40)
    # para caber em 2 linhas grandes que cobrem ~40% da tela.
    display_hook = hook
    if len(display_hook) > 30:
        display_hook = display_hook[:27].rstrip() + "..."
    lines = textwrap.wrap(display_hook, width=wrap_width)
    y = cfg.hook_y_start
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2

        draw.text((x + 2, y + 2), line, font=font_small, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font_small, fill=pal["text"])
        y += cfg.hook_line_height

    # Marca com destaque
    bbox = draw.textbbox((0, 0), brand, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, cfg.brand_y), brand, font=font_small, fill=pal["accent"])

    _save_under_2mb(img.convert("RGB"), output)


def make_short_thumbnail(
    hook: str,
    emoji: str,
    output: Path,
    brand: str = "Pata Jazz",
    video_path: Path | None = None,
    variant: str = "A",
) -> None:
    """Thumbnail 1080x1920 para Shorts verticais.

    #5: texto maior e mais ousado - fontes aumentadas (era 120/48, agora
    160/64) e hook truncado para max 30 chars (era 40) para caber em 2
    linhas grandes que cobrem ~40% da tela. CTR de thumbnail e o #1
    fator de alcance em canal novo.
    """
    width, height = 1080, 1920
    cfg = _LayoutConfig(
        border_margin=50,
        border_radius=50,
        border_width=8,
        emoji_y=380,
        emoji_shadow_offset=(8, 8),
        hook_y_start=680,
        hook_wrap_width=12,
        hook_line_height=110,
        brand_y=height - 180,
        crop_target_ratio=width / height,
        overlay_alpha=120,
        frame_timestamp=f"00:00:{random.randint(2, 15):02d}",
    )
    _render_thumbnail(width, height, hook, emoji, output, brand, video_path, cfg, variant=variant)
    log.info("Thumbnail de Short salva: %s (variante %s)", output, variant)


def make_long_thumbnail(
    hook: str,
    emoji: str,
    output: Path,
    brand: str = "Pata Jazz",
    video_path: Path | None = None,
    variant: str = "A",
) -> None:
    """Thumbnail 1920x1080 (16:9) para long-form horizontal Loop & Relax."""
    width, height = 1920, 1080
    cfg = _LayoutConfig(
        border_margin=80,
        border_radius=40,
        border_width=8,
        emoji_y=150,
        emoji_shadow_offset=(8, 8),
        hook_y_start=430,
        hook_wrap_width=40,
        hook_line_height=100,
        brand_y=height - 190,
        crop_target_ratio=width / height,
        overlay_alpha=110,
        frame_timestamp=f"00:{random.randint(1, 9):02d}:{random.randint(2, 59):02d}",
    )
    _render_thumbnail(width, height, hook, emoji, output, brand, video_path, cfg, variant=variant)
    log.info("Thumbnail long-form salva: %s (variante %s)", output, variant)


def create_all_variants(
    hook: str,
    emoji: str,
    output_dir: Path,
    brand: str = "Pata Jazz",
    video_path: Path | None = None,
    kind: str = "short",
) -> list[Path]:
    """Gera as 3 variantes A/B/C de thumbnail para teste de CTR."""
    paths: list[Path] = []
    for variant in ("A", "B", "C"):
        output = output_dir / f"thumb_{variant}.jpg"
        if kind == "short":
            make_short_thumbnail(hook, emoji, output, brand, video_path, variant=variant)
        else:
            make_long_thumbnail(hook, emoji, output, brand, video_path, variant=variant)
        paths.append(output)
    return paths


_MIN_VARIANT_SAMPLES = 2


def winning_thumbnail_variant() -> str:
    """Retorna a variante de thumbnail vencedora baseada em analytics.

    Lê data_dir() / video_tags.json e data_dir() / analytics.json, cruza
    video_id com thumbnail_variant e calcula a média de views por variante.
    Retorna a variante com maior média, desde que tenha pelo menos
    _MIN_VARIANT_SAMPLES amostras. Em caso de empate, falta de dados ou
    arquivos corrompidos/ausentes, retorna "A".
    """
    try:
        tags_path = data_dir() / "video_tags.json"
        analytics_path = data_dir() / "analytics.json"
        if not tags_path.exists() or not analytics_path.exists():
            return "A"

        tags = json.loads(tags_path.read_text(encoding="utf-8"))
        analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
        all_videos = analytics.get("all_videos", [])
        if not all_videos:
            return "A"

        view_by_id = {v.get("video_id"): v.get("views", 0) for v in all_videos}
        sums: dict[str, list[int]] = {"A": [], "B": [], "C": []}
        for video_id, metadata in tags.items():
            variant = metadata.get("thumbnail_variant", "A") if isinstance(metadata, dict) else "A"
            if variant not in sums:
                continue
            views = view_by_id.get(video_id)
            if views is not None:
                sums[variant].append(int(views))

        averages = {
            variant: sum(values) / len(values)
            for variant, values in sums.items()
            if len(values) >= _MIN_VARIANT_SAMPLES
        }
        if not averages:
            return "A"
        return max(averages, key=averages.get)  # type: ignore[arg-type]
    except Exception:
        return "A"
