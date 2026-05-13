#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_video.py — Gera vídeos de notícias para o YouTube
============================================================
Usa: edge-tts (voz), Pillow (imagens), FFmpeg (vídeo)
Não precisa de API paga — 100% gratuito.
"""

import os, re, json, asyncio, textwrap, subprocess, logging, hashlib
from pathlib import Path
from datetime import datetime, timezone

import feedparser
import requests
from PIL import Image, ImageDraw, ImageFont

# ── Config ─────────────────────────────────────────────────────
VIDEOS_DIR   = Path("_videos")        # vídeos gerados aguardando upload
ASSETS_DIR   = Path("assets/yt")      # fontes e assets
LOG_FILE     = "generate_video.log"
VOICE        = "en-US-AriaNeural"     # edge-tts voice
MAX_PER_RUN  = 3                      # máx vídeos por execução
VIDEO_W, VIDEO_H = 1920, 1080         # resolução Full HD
FONT_DIR     = Path("/usr/share/fonts/truetype")

# Cores do canal
BG_COLOR     = (10, 10, 20)          # fundo escuro
ACCENT       = (0, 180, 255)         # azul tech
TEXT_COLOR   = (240, 240, 240)
SUBTEXT      = (160, 160, 180)
OVERLAY_BG   = (10, 10, 20, 200)     # semi-transparente

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
def get_font(size: int, bold: bool = False):
    """Busca fonte disponível no sistema."""
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# ── Gera script de narração ────────────────────────────────────
def build_script(title: str, description: str, source: str) -> str:
    """Monta roteiro de ~60-90 segundos."""
    clean_desc = re.sub(r'<[^>]+>', '', description).strip()
    clean_desc = re.sub(r'\s+', ' ', clean_desc)[:500]

    script = f"""Welcome to TechBR News. Here's what's happening in tech today.

{title}.

{clean_desc}

This story comes from {source}. For the full article and more tech news, visit TechBR News at non-s.github.io.

Don't forget to like this video and subscribe for daily tech updates. See you in the next one."""
    return script

# ── TTS com edge-tts ───────────────────────────────────────────
async def text_to_speech(text: str, output_path: Path):
    """Converte texto em áudio MP3 usando edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(output_path))

# ── Download de imagem ─────────────────────────────────────────
def download_image(url: str, dest: Path) -> bool:
    """Baixa imagem da URL."""
    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "TechBR-Bot/1.0"
        })
        if r.status_code == 200 and len(r.content) > 1000:
            dest.write_bytes(r.content)
            return True
    except Exception as e:
        log.debug(f"Image download failed: {e}")
    return False

# ── Cria frame de vídeo ────────────────────────────────────────
def create_video_frame(title: str, source: str, image_path: Path | None,
                       frame_num: int, total_frames: int) -> Image.Image:
    """Cria um frame do vídeo com design profissional."""
    img = Image.new("RGB", (VIDEO_W, VIDEO_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Fundo com gradiente simulado (faixas)
    for i in range(VIDEO_H):
        ratio = i / VIDEO_H
        r = int(BG_COLOR[0] + (20 - BG_COLOR[0]) * ratio)
        g = int(BG_COLOR[1] + (15 - BG_COLOR[1]) * ratio)
        b = int(BG_COLOR[2] + (40 - BG_COLOR[2]) * ratio)
        draw.line([(0, i), (VIDEO_W, i)], fill=(r, g, b))

    # Imagem de fundo (se disponível)
    if image_path and image_path.exists():
        try:
            bg = Image.open(image_path).convert("RGB")
            bg = bg.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
            # Overlay escuro para legibilidade
            overlay = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 160))
            img = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)
        except Exception:
            pass

    # Barra superior — branding
    draw.rectangle([(0, 0), (VIDEO_W, 90)], fill=(0, 0, 0, 200))
    font_brand = get_font(42, bold=True)
    draw.text((50, 22), "⚡ TECHBR NEWS", font=font_brand, fill=ACCENT)
    draw.text((VIDEO_W - 300, 22), datetime.now().strftime("%B %d, %Y"),
              font=get_font(32), fill=SUBTEXT)

    # Barra de progresso
    progress = frame_num / max(total_frames, 1)
    draw.rectangle([(0, 85), (VIDEO_W, 90)], fill=(40, 40, 60))
    draw.rectangle([(0, 85), (int(VIDEO_W * progress), 90)], fill=ACCENT)

    # Caixa do título (bottom third)
    box_y = VIDEO_H - 320
    draw.rectangle([(0, box_y), (VIDEO_W, VIDEO_H)], fill=(0, 0, 0, 210))
    draw.rectangle([(0, box_y), (8, VIDEO_H)], fill=ACCENT)

    # Título com quebra de linha automática
    font_title = get_font(58, bold=True)
    font_source = get_font(34)
    font_cta = get_font(30)

    # Wrap título
    words = title.split()
    lines, line = [], []
    for word in words:
        test = ' '.join(line + [word])
        bbox = draw.textbbox((0, 0), test, font=font_title)
        if bbox[2] > VIDEO_W - 120 and line:
            lines.append(' '.join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(' '.join(line))

    y = box_y + 30
    for l in lines[:3]:
        draw.text((60, y), l, font=font_title, fill=TEXT_COLOR)
        y += 70

    # Fonte
    draw.text((60, VIDEO_H - 90), f"📰 Source: {source}", font=font_source, fill=SUBTEXT)
    draw.text((VIDEO_W - 500, VIDEO_H - 90), "non-s.github.io", font=font_cta, fill=ACCENT)

    # Watermark
    draw.text((60, VIDEO_H - 50), "🔔 Subscribe for daily tech news",
              font=get_font(26), fill=(120, 120, 140))

    return img

# ── Gera thumbnail ─────────────────────────────────────────────
def create_thumbnail(title: str, image_path: Path | None, output: Path):
    """Cria thumbnail YouTube 1280x720."""
    img = Image.new("RGB", (1280, 720), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Gradiente de fundo
    for i in range(720):
        r = int(5 + 25 * (i/720))
        draw.line([(0,i),(1280,i)], fill=(r, 5, 30))

    # Imagem de fundo
    if image_path and image_path.exists():
        try:
            bg = Image.open(image_path).convert("RGB")
            bg = bg.resize((1280, 720), Image.LANCZOS)
            overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 140))
            img = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)
        except Exception:
            pass

    # Barra lateral esquerda colorida
    draw.rectangle([(0, 0), (18, 720)], fill=ACCENT)

    # Badge "TECH NEWS"
    draw.rounded_rectangle([(40, 30), (260, 90)], radius=8, fill=ACCENT)
    draw.text((55, 42), "⚡ TECH NEWS", font=get_font(34, bold=True), fill=(0,0,0))

    # Título
    font_t = get_font(68, bold=True)
    words = title.split()
    lines, line = [], []
    for w in words:
        test = ' '.join(line + [w])
        bbox = draw.textbbox((0,0), test, font=font_t)
        if bbox[2] > 1160 and line:
            lines.append(' '.join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(' '.join(line))

    y = 130
    for l in lines[:4]:
        draw.text((40, y), l, font=font_t, fill=TEXT_COLOR)
        y += 80

    # Logo bottom
    draw.text((40, 655), "TechBR News • non-s.github.io",
              font=get_font(32), fill=SUBTEXT)

    img.save(str(output), "JPEG", quality=95)
    log.info(f"  🖼  Thumbnail: {output.name}")

# ── Cria vídeo com FFmpeg ──────────────────────────────────────
def create_video(title: str, source: str, image_path: Path | None,
                 audio_path: Path, output_path: Path) -> bool:
    """Monta o vídeo final com FFmpeg."""
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

    # Gera frames-chave (apenas 2: início e fim — FFmpeg interpola)
    frames_to_render = min(total_frames, 48)  # máx 48 frames reais
    for i in range(frames_to_render):
        frame = create_video_frame(title, source, image_path,
                                   i, frames_to_render)
        frame.save(str(tmp_dir / f"frame_{i:05d}.png"))

    # Lista de frames com timestamps para FFmpeg
    concat_file = tmp_dir / "frames.txt"
    with open(concat_file, "w") as f:
        for i in range(frames_to_render):
            f.write(f"file 'frame_{i:05d}.png'\n")
            f.write(f"duration {duration / frames_to_render:.4f}\n")

    # FFmpeg: frames + áudio → mp4
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(audio_path),
        "-vf", f"scale={VIDEO_W}:{VIDEO_H},fps={fps}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            cwd=str(tmp_dir))
    if result.returncode != 0:
        log.error(f"FFmpeg error: {result.stderr[-500:]}")
        return False

    # Limpa frames temporários
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    log.info(f"  ✅ Vídeo gerado: {output_path.name}")
    return True

# ── Salva metadados para upload ────────────────────────────────
def save_metadata(slug: str, title: str, description: str,
                  source: str, source_url: str, tags: list,
                  thumbnail: Path, video: Path):
    """Salva JSON com metadados SEO para o upload."""
    # Título otimizado para SEO (max 100 chars)
    yt_title = f"{title[:85]} | TechBR News" if len(title) < 85 else title[:97] + "..."

    # Descrição SEO rica
    yt_desc = f"""{description[:400]}

🔗 Read the full article: {source_url}
📰 Source: {source}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 TechBR News — Daily Tech Updates
Website: https://non-s.github.io
Subscribe for the latest in AI, gadgets, cybersecurity, and startups.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏱️ CHAPTERS
0:00 Introduction
0:15 Main Story
{f"0:{int(len(description.split())/3):02d} Details"}
1:00 Wrap Up

🏷️ TAGS
#TechNews #Technology #AI #Gadgets #TechBR

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Contact: sourcenaiomiocc@gmail.com
© TechBR News {datetime.now().year} — All rights to original articles belong to their respective sources.
"""

    metadata = {
        "title": yt_title,
        "description": yt_desc,
        "tags": tags + ["tech news", "technology", "TechBR", "latest tech",
                        "AI news", "gadgets", "startup news", "cybersecurity"],
        "category_id": "28",  # Science & Technology
        "privacy": "public",
        "thumbnail": str(thumbnail),
        "video": str(video),
        "source_url": source_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = video.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    return metadata

# ── Verifica se vídeo já foi gerado ───────────────────────────
def video_exists(slug: str) -> bool:
    return (VIDEOS_DIR / f"{slug}.mp4").exists() or \
           (VIDEOS_DIR / f"{slug}.done").exists()

# ── Principal ──────────────────────────────────────────────────
def main():
    VIDEOS_DIR.mkdir(exist_ok=True)

    # Lê posts Jekyll existentes para encontrar notícias novas
    posts_dir = Path("_posts")
    if not posts_dir.exists():
        log.error("_posts/ não encontrado")
        return

    # Ordena por data (mais recentes primeiro)
    posts = sorted(posts_dir.glob("*.md"), reverse=True)
    generated = 0

    for post_file in posts:
        if generated >= MAX_PER_RUN:
            break

        slug = post_file.stem
        if video_exists(slug):
            continue

        # Lê frontmatter do post
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

        log.info(f"📹 Gerando vídeo: {title[:60]}...")

        tmp = Path(f"/tmp/yt_{slug}")
        tmp.mkdir(exist_ok=True)

        # Download da imagem
        img_path = None
        if image_url:
            img_dest = tmp / "cover.jpg"
            if download_image(image_url, img_dest):
                img_path = img_dest

        # TTS
        script   = build_script(title, description, source)
        mp3_path = tmp / "narration.mp3"
        try:
            asyncio.run(text_to_speech(script, mp3_path))
            log.info(f"  🎙️  TTS gerado: {mp3_path.stat().st_size/1024:.0f} KB")
        except Exception as e:
            log.error(f"  ❌ TTS falhou: {e}")
            continue

        # Thumbnail
        thumb_path = VIDEOS_DIR / f"{slug}_thumb.jpg"
        create_thumbnail(title, img_path, thumb_path)

        # Vídeo
        video_path = VIDEOS_DIR / f"{slug}.mp4"
        ok = create_video(title, source, img_path, mp3_path, video_path)
        if not ok:
            continue

        # Metadados SEO
        save_metadata(slug, title, description, source, source_url,
                      tags, thumb_path, video_path)

        # Marca como gerado
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        generated += 1
        log.info(f"  ✅ {generated}/{MAX_PER_RUN} concluído: {slug}")

    log.info(f"\n🏁 {generated} vídeo(s) gerado(s).")

if __name__ == "__main__":
    main()
