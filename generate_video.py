#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_video.py — Gera vídeos de notícias para o YouTube
============================================================
Design profissional estilo telejornal: gradiente tech, lower-thirds,
barra de progresso animada, thumbnail otimizado para CTR.
"""

import os, re, json, asyncio, textwrap, subprocess, logging, hashlib, math
from pathlib import Path
from datetime import datetime, timezone

import feedparser
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Config ─────────────────────────────────────────────────────
VIDEOS_DIR   = Path("_videos")
LOG_FILE     = "generate_video.log"
VOICE        = "en-US-AriaNeural"
MAX_PER_RUN  = 1                      # 1 por hora = 24/dia
VIDEO_W, VIDEO_H = 1920, 1080

# Paleta de cores — identidade TechBR
BG_DARK      = (8, 8, 18)
BG_MID       = (14, 14, 28)
ACCENT_BLUE  = (0, 195, 255)
ACCENT_CYAN  = (0, 240, 200)
RED_LIVE     = (220, 50, 50)
TEXT_WHITE   = (245, 245, 255)
TEXT_GRAY    = (160, 165, 190)
TEXT_DIM     = (90, 95, 115)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Fontes ─────────────────────────────────────────────────────
def get_font(size: int, bold: bool = False, italic: bool = False):
    candidates_bold = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    pool = candidates_bold if bold else candidates_reg
    for path in pool:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# ── Utilitários de desenho ─────────────────────────────────────
def draw_rounded_rect(draw, xy, radius, fill, outline=None, outline_width=2):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                            outline=outline, width=outline_width)

def draw_gradient_rect(img, x0, y0, x1, y1, color_top, color_bot):
    draw = ImageDraw.Draw(img)
    for i in range(y1 - y0):
        t = i / max(y1 - y0 - 1, 1)
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        draw.line([(x0, y0 + i), (x1, y0 + i)], fill=(r, g, b))

def draw_tech_grid(img, alpha=18):
    """Desenha grid de pontos tech no fundo."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    spacing = 48
    for x in range(0, VIDEO_W, spacing):
        for y in range(0, VIDEO_H, spacing):
            d.ellipse([x-1, y-1, x+1, y+1], fill=(0, 195, 255, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

def draw_glow_line(draw, x0, y0, x1, y1, color, width=3):
    """Linha com efeito glow (3 camadas)."""
    r, g, b = color
    draw.line([(x0, y0), (x1, y1)], fill=(r, g, b, 60), width=width + 4)
    draw.line([(x0, y0), (x1, y1)], fill=(r, g, b, 130), width=width + 2)
    draw.line([(x0, y0), (x1, y1)], fill=(r, g, b, 255), width=width)

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, line = [], []
    for word in words:
        test = ' '.join(line + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and line:
            lines.append(' '.join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(' '.join(line))
    return lines

# ── Script de narração ─────────────────────────────────────────
def build_script(title: str, description: str, source: str, tags: list) -> str:
    clean = re.sub(r'<[^>]+>', '', description).strip()
    clean = re.sub(r'\s+', ' ', clean)[:600]
    tag_str = ', '.join(tags[:3]) if tags else 'technology'

    return f"""Welcome to TechBR News — your source for the latest in {tag_str}.

Today's story: {title}.

{clean}

This report comes to you from {source}. You can read the original article and find more tech coverage on TechBR News at our website, linked in the description.

If you found this useful, please hit like and subscribe — we publish new tech stories every single hour, so you'll never miss what's happening in the world of technology.

Stay informed. Stay ahead. This is TechBR News."""

# ── TTS ────────────────────────────────────────────────────────
async def text_to_speech(text: str, output_path: Path):
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE, rate="+8%")
    await communicate.save(str(output_path))

# ── Download de imagem ─────────────────────────────────────────
def download_image(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "TechBR-Bot/1.0"})
        if r.status_code == 200 and len(r.content) > 1000:
            dest.write_bytes(r.content)
            return True
    except Exception as e:
        log.debug(f"Image download failed: {e}")
    return False

# ── Frame de vídeo — design profissional ──────────────────────
def create_video_frame(title: str, source: str, image_path: Path | None,
                       frame_num: int, total_frames: int,
                       category: str = "TECH") -> Image.Image:
    """Frame estilo telejornal profissional."""
    # Base escura
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (*BG_DARK, 255))

    # Gradiente de fundo
    draw_gradient_rect(img, 0, 0, VIDEO_W, VIDEO_H,
                       BG_DARK, (12, 10, 35))

    # Grid de pontos (sutil)
    img = draw_tech_grid(img, alpha=12)

    # ── Imagem de background ──
    if image_path and image_path.exists():
        try:
            bg = Image.open(image_path).convert("RGB")
            # Crop inteligente — foco no centro
            bw, bh = bg.size
            target_ratio = VIDEO_W / VIDEO_H
            current_ratio = bw / bh
            if current_ratio > target_ratio:
                new_w = int(bh * target_ratio)
                offset = (bw - new_w) // 2
                bg = bg.crop((offset, 0, offset + new_w, bh))
            else:
                new_h = int(bw / target_ratio)
                offset = (bh - new_h) // 2
                bg = bg.crop((0, offset, bw, offset + new_h))
            bg = bg.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
            # Overlay gradiente escuro (mais leve no topo, mais escuro na base)
            overlay = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(overlay)
            for i in range(VIDEO_H):
                alpha = int(100 + 130 * (i / VIDEO_H))
                ov_draw.line([(0, i), (VIDEO_W, i)], fill=(0, 0, 10, alpha))
            img = Image.alpha_composite(bg.convert("RGBA"), overlay)
            img = img.convert("RGB")
        except Exception:
            pass

    draw = ImageDraw.Draw(img)

    # ── TOP BAR ──────────────────────────────────────────────
    # Fundo da barra superior
    draw.rectangle([(0, 0), (VIDEO_W, 88)], fill=(0, 0, 0, 210))

    # Linha de brilho na base da barra
    for i in range(3):
        alpha = 80 - i * 25
        draw.line([(0, 88 + i), (VIDEO_W, 88 + i)],
                  fill=(*ACCENT_BLUE, alpha))

    # Logo "⚡ TECHBR NEWS"
    font_logo = get_font(44, bold=True)
    draw.text((50, 20), "TECHBR", font=font_logo, fill=ACCENT_BLUE)
    draw.text((222, 20), "NEWS", font=font_logo, fill=TEXT_WHITE)

    # Separador vertical
    draw.rectangle([(210, 22), (213, 66)], fill=(*ACCENT_BLUE, 180))

    # Badge LIVE / categoria
    badge_x = 340
    draw_rounded_rect(draw, (badge_x, 24, badge_x + 120, 64),
                      radius=6, fill=RED_LIVE)
    draw.text((badge_x + 14, 32), "● LIVE", font=get_font(26, bold=True),
              fill=TEXT_WHITE)

    # Data e hora
    now_str = datetime.now().strftime("%b %d, %Y  %H:%M")
    font_date = get_font(28)
    bbox = draw.textbbox((0, 0), now_str, font=font_date)
    draw.text((VIDEO_W - bbox[2] - 50, 30), now_str,
              font=font_date, fill=TEXT_GRAY)

    # ── PROGRESS BAR ─────────────────────────────────────────
    progress = frame_num / max(total_frames - 1, 1)
    bar_y = 88
    draw.rectangle([(0, bar_y), (VIDEO_W, bar_y + 5)], fill=(25, 25, 45))
    prog_w = int(VIDEO_W * progress)
    if prog_w > 0:
        # Gradiente na barra de progresso
        for px in range(prog_w):
            t = px / VIDEO_W
            r = int(ACCENT_BLUE[0] + (ACCENT_CYAN[0] - ACCENT_BLUE[0]) * t)
            g = int(ACCENT_BLUE[1] + (ACCENT_CYAN[1] - ACCENT_BLUE[1]) * t)
            b = int(ACCENT_BLUE[2] + (ACCENT_CYAN[2] - ACCENT_BLUE[2]) * t)
            draw.line([(px, bar_y), (px, bar_y + 4)], fill=(r, g, b))
        # Ponto brilhante no final da barra
        px = prog_w - 1
        draw.ellipse([(px - 5, bar_y - 3), (px + 5, bar_y + 7)],
                     fill=TEXT_WHITE)

    # ── LOWER THIRD (área de conteúdo) ───────────────────────
    lt_y = VIDEO_H - 310
    lt_h = 280

    # Fundo semitransparente com gradiente
    for i in range(lt_h):
        t = 1 - (i / lt_h) ** 0.5
        alpha = int(220 * t)
        draw.line([(0, lt_y + i), (VIDEO_W, lt_y + i)],
                  fill=(0, 0, 8, alpha))

    # Barra vertical de acento (esquerda)
    for i in range(3):
        alpha = 255 - i * 60
        draw.rectangle([(i * 3, lt_y), (i * 3 + 2, VIDEO_H - 50)],
                       fill=(*ACCENT_BLUE, alpha))

    # Badge de categoria
    cat_x, cat_y = 30, lt_y + 12
    cat_text = category.upper()
    cat_font = get_font(26, bold=True)
    cat_bbox = draw.textbbox((0, 0), cat_text, font=cat_font)
    cat_w = cat_bbox[2] + 20
    draw_rounded_rect(draw, (cat_x, cat_y, cat_x + cat_w, cat_y + 38),
                      radius=5, fill=ACCENT_BLUE)
    draw.text((cat_x + 10, cat_y + 6), cat_text, font=cat_font,
              fill=(0, 0, 0))

    # Título principal
    font_title = get_font(62, bold=True)
    title_lines = wrap_text(draw, title, font_title, VIDEO_W - 120)
    ty = lt_y + 62
    for line in title_lines[:3]:
        draw.text((30, ty), line, font=font_title, fill=TEXT_WHITE)
        ty += 74

    # Linha separadora
    sep_y = VIDEO_H - 95
    draw.line([(30, sep_y), (VIDEO_W - 30, sep_y)],
              fill=(*ACCENT_BLUE, 60), width=1)

    # Rodapé: fonte e URL
    font_footer = get_font(30)
    draw.text((30, sep_y + 12), f"📰  {source}",
              font=font_footer, fill=TEXT_GRAY)

    font_url = get_font(28, bold=True)
    url_text = "non-s.github.io  |  Subscribe ↑"
    bbox_url = draw.textbbox((0, 0), url_text, font=font_url)
    draw.text((VIDEO_W - bbox_url[2] - 30, sep_y + 14),
              url_text, font=font_url, fill=ACCENT_CYAN)

    return img.convert("RGB")

# ── Thumbnail profissional ─────────────────────────────────────
def create_thumbnail(title: str, image_path: Path | None, output: Path,
                     category: str = "TECH NEWS"):
    """Thumbnail 1280×720 otimizado para CTR do YouTube."""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), BG_DARK)

    # Gradiente de fundo
    for i in range(H):
        t = i / H
        r = int(BG_DARK[0] * (1 - t) + 20 * t)
        g = int(BG_DARK[1] * (1 - t) + 8 * t)
        b = int(BG_DARK[2] * (1 - t) + 55 * t)
        img_draw_temp = ImageDraw.Draw(img)
        img_draw_temp.line([(0, i), (W, i)], fill=(r, g, b))

    # Imagem de fundo (lado direito, 60% da largura)
    if image_path and image_path.exists():
        try:
            bg = Image.open(image_path).convert("RGB")
            bg = bg.resize((W, H), Image.LANCZOS)
            # Mask gradiente: opaco à direita, transparente à esquerda
            mask = Image.new("L", (W, H), 0)
            mask_draw = ImageDraw.Draw(mask)
            for x in range(W):
                t = max(0, (x - W * 0.25) / (W * 0.75))
                t = min(1, t)
                alpha = int(185 * t)
                mask_draw.line([(x, 0), (x, H)], fill=alpha)
            img.paste(bg, (0, 0), mask)
        except Exception:
            pass

    draw = ImageDraw.Draw(img)

    # Overlay escuro no lado esquerdo para legibilidade
    for x in range(int(W * 0.7)):
        t = 1 - x / (W * 0.7)
        alpha = int(160 * t ** 0.5)
        draw.line([(x, 0), (x, H)], fill=(0, 0, 10, alpha))

    # Faixa lateral esquerda colorida
    for i in range(10):
        alpha = 255 - i * 22
        draw.rectangle([(i * 2, 0), (i * 2 + 1, H)],
                       fill=(*ACCENT_BLUE, alpha))

    # Badge categoria (topo esquerdo)
    badge_font = get_font(30, bold=True)
    badge_bbox = draw.textbbox((0, 0), category, font=badge_font)
    bw = badge_bbox[2] + 24
    draw_rounded_rect(draw, (28, 28, 28 + bw, 72), radius=8, fill=RED_LIVE)
    draw.text((40, 36), category, font=badge_font, fill=TEXT_WHITE)

    # Título principal — grande e impactante
    font_t = get_font(80, bold=True)
    font_t_small = get_font(68, bold=True)
    title_lines = wrap_text(draw, title, font_t, int(W * 0.68))
    # Se muito longo, usa fonte menor
    if len(title_lines) > 3:
        title_lines = wrap_text(draw, title, font_t_small, int(W * 0.68))
        font_used = font_t_small
        line_h = 82
    else:
        font_used = font_t
        line_h = 96

    ty = 100
    for line in title_lines[:4]:
        # Sombra do texto
        draw.text((32, ty + 3), line, font=font_used,
                  fill=(0, 0, 0))
        draw.text((30, ty), line, font=font_used, fill=TEXT_WHITE)
        ty += line_h

    # Linha separadora
    draw.rectangle([(28, H - 110), (int(W * 0.65), H - 107)],
                   fill=ACCENT_BLUE)

    # Branding TechBR na base
    font_brand = get_font(36, bold=True)
    draw.text((28, H - 92), "TECHBR", font=font_brand, fill=ACCENT_BLUE)
    draw.text((168, H - 92), "NEWS", font=font_brand, fill=TEXT_WHITE)

    font_sub = get_font(26)
    draw.text((28, H - 48), "non-s.github.io  •  Tech every hour",
              font=font_sub, fill=TEXT_GRAY)

    img.save(str(output), "JPEG", quality=95, optimize=True)
    log.info(f"  🖼  Thumbnail: {output.name}")

# ── Monta vídeo com FFmpeg ─────────────────────────────────────
def create_video(title: str, source: str, image_path: Path | None,
                 audio_path: Path, output_path: Path,
                 category: str = "TECH") -> bool:
    tmp_dir = output_path.parent / f"tmp_{output_path.stem}"
    tmp_dir.mkdir(exist_ok=True)

    # Duração do áudio
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True
    )
    try:
        duration = float(result.stdout.strip())
    except Exception:
        duration = 60.0

    fps = 24
    total_frames = int(duration * fps)
    log.info(f"  🎬 Gerando {total_frames} frames ({duration:.1f}s)...")

    # Gera frames (keyframes com interpolação)
    n_render = min(total_frames, 60)  # max 60 frames renderizados
    for i in range(n_render):
        frame_num = int(i * total_frames / n_render)
        frame = create_video_frame(title, source, image_path,
                                   frame_num, total_frames, category)
        frame.save(str(tmp_dir / f"frame_{i:05d}.png"))

    # Concat list
    concat_file = tmp_dir / "frames.txt"
    with open(concat_file, "w") as f:
        dur_each = duration / n_render
        for i in range(n_render):
            f.write(f"file 'frame_{i:05d}.png'\n")
            f.write(f"duration {dur_each:.4f}\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file.name,
        "-i", str(audio_path.resolve()),
        "-vf", f"scale={VIDEO_W}:{VIDEO_H},fps={fps}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            cwd=str(tmp_dir))
    if result.returncode != 0:
        log.error(f"FFmpeg error: {result.stderr[-600:]}")
        return False

    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    log.info(f"  ✅ Vídeo gerado: {output_path.name}")
    return True

# ── English title builder ────────────────────────────────────────
def build_english_title(title: str, category: str) -> str:
    """Generate SEO-optimized English YouTube title."""
    pt_en = [
        ("inteligência artificial", "artificial intelligence"),
        ("aprendizado de máquina", "machine learning"),
        ("código aberto", "open source"),
        ("lançamento", "launch"), ("lança", "launches"), ("lançou", "launched"),
        ("atualização", "update"), ("atualiza", "updates"), ("atualizou", "updated"),
        ("anúncio", "announcement"), ("anuncia", "announces"), ("anunciou", "announced"),
        ("revelação", "reveal"), ("revela", "reveals"), ("revelou", "revealed"),
        ("crescimento", "growth"), ("cresce", "grows"), ("cresceu", "grew"),
        ("investimento", "investment"), ("investe", "invests"),
        ("aquisição", "acquisition"), ("adquire", "acquires"), ("adquiriu", "acquired"),
        ("parceria", "partnership"), ("acordo", "deal"),
        ("empresa", "company"), ("empresas", "companies"),
        ("governo", "government"), ("governos", "governments"),
        ("usuários", "users"), ("usuário", "user"),
        ("bilhões", "billion"), ("milhões", "million"), ("milhares", "thousands"),
        ("segurança", "security"), ("privacidade", "privacy"),
        ("vazamento", "leak"), ("ataque", "attack"), ("ataques", "attacks"),
        ("tecnologia", "technology"), ("tecnologias", "technologies"),
        ("celular", "smartphone"), ("computador", "computer"),
        ("tela", "screen"), ("processador", "processor"), ("bateria", "battery"),
        ("novo", "new"), ("nova", "new"), ("novos", "new"), ("novas", "new"),
        ("primeiro", "first"), ("primeira", "first"),
        ("último", "latest"), ("última", "latest"),
        ("próximo", "next"), ("próxima", "next"),
        ("gratuito", "free"), ("grátis", "free"), ("pago", "paid"),
        ("preço", "price"), ("mercado", "market"), ("vendas", "sales"),
        ("recorde", "record"), ("histórico", "historic"),
        ("mundo", "world"), ("Brasil", "Brazil"), ("EUA", "USA"),
        ("robô", "robot"), ("elétrico", "electric"),
        ("aprovado", "approved"), ("bloqueado", "blocked"), ("banido", "banned"),
        ("fusão", "merger"), ("dados", "data"), ("nuvem", "cloud"),
        ("queda", "drop"), ("caiu", "fell"), ("subiu", "rose"),
    ]
    result = title
    for pt, en in pt_en:
        result = re.sub(r'\\b' + re.escape(pt) + r'\\b', en, result, flags=re.IGNORECASE)
    clean = result.strip()
    if len(clean) > 82:
        clean = clean[:79] + "..."
    return f"[{category}] {clean} | TechBR News"

# ── YouTube SEO Metadata ────────────────────────────────────────
def save_metadata(slug, title, description, source, source_url, tags,
                  thumbnail, video):
    category = guess_category(tags, title)
    yt_title = build_english_title(title, category)

    clean_desc = re.sub(r'<[^>]+>', '', description).strip()
    clean_desc = re.sub(r'\\s+', ' ', clean_desc)[:400]
    year = datetime.now().year

    yt_desc = (
        f"{clean_desc}\n\n"
        "━" * 24 + "\n"
        f"U0001F4F0 FULL STORY → {source_url}\n"
        f"U0001F310 Source: {source}\n\n"
        "━" * 24 + "\n"
        "U0001F514 SUBSCRIBE for hourly tech news → https://youtube.com/@techbrnews\n"
        "U0001F30D TechBR News — Breaking tech stories, 24 hours a day\n\n"
        "━" * 24 + "\n"
        "⏱ CHAPTERS\n"
        "0:00 Introduction\n"
        "0:12 Main story\n"
        "1:00 Details & context\n"
        "1:45 Wrap-up\n\n"
        "━" * 24 + "\n"
        f"© {year} TechBR News. Original articles belong to their respective sources.\n"
    )

    cat_tags = {
        "AI": ["machine learning", "ChatGPT", "LLM", "OpenAI", "Google AI", "AI tools", "artificial intelligence news"],
        "SECURITY": ["cybersecurity", "data breach", "hacking news", "privacy", "malware", "cyber attack"],
        "BUSINESS": ["tech business", "startup funding", "IPO", "tech stocks", "acquisition", "venture capital"],
        "BIG TECH": ["Apple news", "Google news", "Microsoft", "Meta", "Amazon", "big tech"],
        "HARDWARE": ["smartphone news", "iPhone", "Android", "laptop", "processor", "chip news"],
        "TECH": ["technology news", "software", "internet", "digital", "programming", "developer"],
    }
    base_tags = [
        "tech news", "technology news", "TechBR News", "breaking tech",
        f"tech news {year}", "latest technology", "innovation",
        "digital world", "technology today",
    ]
    extra_tags = cat_tags.get(category, cat_tags["TECH"])
    post_tags = [t.replace(' ', '').lower() for t in tags if t and len(t) > 2]
    all_tags = list(dict.fromkeys(base_tags + extra_tags + post_tags))[:30]

    metadata = {
        "title": yt_title,
        "description": yt_desc,
        "tags": all_tags,
        "category_id": "28",
        "privacy": "public",
        "thumbnail": str(thumbnail),
        "video": str(video),
        "source_url": source_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = video.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    return metadata
# ── Utilitários ────────────────────────────────────────────────
def video_exists(slug: str) -> bool:
    return (VIDEOS_DIR / f"{slug}.mp4").exists() or \
           (VIDEOS_DIR / f"{slug}.done").exists()

def guess_category(tags: list, title: str) -> str:
    text = (title + " ".join(tags)).lower()
    if any(w in text for w in ["ai", "artificial", "machine learning", "gpt", "llm"]):
        return "AI"
    if any(w in text for w in ["security", "hack", "cyber", "breach", "malware"]):
        return "SECURITY"
    if any(w in text for w in ["startup", "funding", "ipo", "acquisition", "billion"]):
        return "BUSINESS"
    if any(w in text for w in ["apple", "google", "microsoft", "meta", "amazon"]):
        return "BIG TECH"
    if any(w in text for w in ["phone", "iphone", "android", "hardware", "chip"]):
        return "HARDWARE"
    return "TECH"

# ── Principal ──────────────────────────────────────────────────
def main():
    VIDEOS_DIR.mkdir(exist_ok=True)
    posts_dir = Path("_posts")
    if not posts_dir.exists():
        log.error("_posts/ não encontrado")
        return

    posts = sorted(posts_dir.glob("*.md"), reverse=True)
    generated = 0

    for post_file in posts:
        if generated >= MAX_PER_RUN:
            break

        slug = post_file.stem
        if video_exists(slug):
            continue

        content = post_file.read_text(encoding="utf-8")
        fm = {}
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                for line in content[3:end].splitlines():
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        fm[k.strip()] = v.strip().strip('"')

        title       = fm.get("title", slug.replace("-", " ").title())
        description = fm.get("description", "")
        source      = fm.get("source_name", "TechBR News")
        source_url  = fm.get("source_url", "https://non-s.github.io")
        image_url   = fm.get("image", "")
        tags_raw    = fm.get("tags", "[]")
        try:
            tags = json.loads(tags_raw.replace("'", '"'))
        except Exception:
            tags = ["tech", "technology"]

        category = guess_category(tags, title)
        log.info(f"📹 [{category}] Gerando: {title[:60]}...")

        tmp = Path(f"/tmp/yt_{slug}")
        tmp.mkdir(exist_ok=True)

        # Download da imagem
        img_path = None
        if image_url:
            img_dest = tmp / "cover.jpg"
            if download_image(image_url, img_dest):
                img_path = img_dest

        # TTS
        script = build_script(title, description, source, tags)
        mp3_path = tmp / "narration.mp3"
        try:
            asyncio.run(text_to_speech(script, mp3_path))
            log.info(f"  🎙️  TTS gerado: {mp3_path.stat().st_size/1024:.0f} KB")
        except Exception as e:
            log.error(f"  ❌ TTS falhou: {e}")
            continue

        # Thumbnail
        thumb_path = VIDEOS_DIR / f"{slug}_thumb.jpg"
        create_thumbnail(title, img_path, thumb_path, category)

        # Vídeo
        video_path = VIDEOS_DIR / f"{slug}.mp4"
        ok = create_video(title, source, img_path, mp3_path, video_path, category)
        if not ok:
            continue

        # Metadados
        save_metadata(slug, title, description, source, source_url,
                      tags, thumb_path, video_path)

        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        generated += 1
        log.info(f"  ✅ {generated}/{MAX_PER_RUN} concluído: {slug}")

    log.info(f"\n🏁 {generated} vídeo(s) gerado(s).")

if __name__ == "__main__":
    main()
