#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_video.py — Gera vídeo roundup horário para o YouTube
==============================================================
Formato: 1 vídeo por hora cobrindo 6 histórias → ~10-12 minutos.
Vídeos longos habilitam mid-roll ads (mínimo 8 min), maximizando receita.

Estrutura do vídeo:
  Intro       ~30s   "Welcome to TechBR News Hourly Roundup"
  História 1  ~90s   Título + descrição + fonte
  História 2  ~90s   ...
  …até 6 histórias…
  Outro       ~60s   CTA de inscrição

Total estimado: 6 × 90s + 30s + 60s ≈ 10.5 minutos
"""

import os, re, json, asyncio, subprocess, logging, shutil
from pathlib import Path
from datetime import datetime, timezone

import requests
from PIL import Image, ImageDraw, ImageFont

# ── Config ─────────────────────────────────────────────────────
VIDEOS_DIR        = Path("_videos")
LOG_FILE          = "generate_video.log"
STORIES_PER_VIDEO = 6      # histórias por roundup (~10 min)
MIN_STORIES       = 3      # mínimo para gerar (evita vídeos muito curtos)
MAX_PER_RUN       = 1      # 1 roundup por execução
VIDEO_W, VIDEO_H  = 1920, 1080

# Paleta de cores — identidade TechBR
BG_DARK     = (8, 8, 18)
ACCENT_BLUE = (0, 195, 255)
ACCENT_CYAN = (0, 240, 200)
RED_LIVE    = (220, 50, 50)
TEXT_WHITE  = (245, 245, 255)
TEXT_GRAY   = (160, 165, 190)

# Voz por categoria
VOICE_BY_CATEGORY = {
    "AI":       "en-US-AriaNeural",
    "SECURITY": "en-US-GuyNeural",
    "BUSINESS": "en-US-JennyNeural",
    "BIG TECH": "en-US-DavisNeural",
    "HARDWARE": "en-US-TonyNeural",
    "TECH":     "en-US-AriaNeural",
}
VOICE_DEFAULT = "en-US-AriaNeural"

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
    candidates_bold = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in (candidates_bold if bold else candidates_reg):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# ── Utilitários de desenho ─────────────────────────────────────
def draw_rounded_rect(draw, xy, radius, fill, outline=None, outline_width=2):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                            outline=outline, width=outline_width)

def draw_gradient_bg(img, color_top, color_bot):
    draw = ImageDraw.Draw(img)
    for i in range(VIDEO_H):
        t = i / max(VIDEO_H - 1, 1)
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        draw.line([(0, i), (VIDEO_W, i)], fill=(r, g, b))

def draw_tech_grid(img, alpha=12):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for x in range(0, VIDEO_W, 48):
        for y in range(0, VIDEO_H, 48):
            d.ellipse([x-1, y-1, x+1, y+1], fill=(0, 195, 255, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, line = [], []
    for word in words:
        test = ' '.join(line + [word])
        if draw.textbbox((0, 0), test, font=font)[2] > max_width and line:
            lines.append(' '.join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(' '.join(line))
    return lines

# ── Script de narração roundup ──────────────────────────────────
ORDINALS = ["one", "two", "three", "four", "five", "six", "seven", "eight"]

def clean_text(text: str, max_chars: int = 500) -> str:
    t = re.sub(r'<[^>]+>', ' ', text)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:max_chars]

def build_roundup_script(stories: list[dict]) -> str:
    """
    Script jornalístico para roundup de múltiplas histórias.
    ~90 palavras por história → ~45s por história a 120 wpm.
    6 histórias + intro/outro ≈ 10-12 minutos.
    """
    n = len(stories)
    # Determinar voz/tema dominante do roundup
    cats = [s["category"] for s in stories]
    dominant = max(set(cats), key=cats.count)

    cat_label = {
        "AI": "artificial intelligence",
        "SECURITY": "cybersecurity",
        "BUSINESS": "tech business and startups",
        "BIG TECH": "big tech",
        "HARDWARE": "hardware and devices",
        "TECH": "technology",
    }.get(dominant, "technology")

    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")
    hour_str = now.strftime("%I %p").lstrip("0")

    script = f"""Welcome to TechBR News — your hourly technology roundup.

I'm bringing you {n} of the most important tech stories right now, on {date_str} at {hour_str}.

Stay with me through all {n} stories — each one has something worth knowing. Let's dive in.

"""

    for i, story in enumerate(stories):
        ordinal = ORDINALS[i] if i < len(ORDINALS) else f"number {i + 1}"
        title   = story["title"]
        desc    = clean_text(story["description"], 450)
        source  = story["source"]
        cat     = story["category"].lower()

        # Quebra descrição em intro + detalhe
        sentences = re.split(r'(?<=[.!?])\s+', desc)
        intro  = " ".join(sentences[:2]) if len(sentences) >= 2 else desc
        detail = " ".join(sentences[2:5]) if len(sentences) > 2 else ""

        script += f"""Story {ordinal}: {title}.

{intro}"""

        if detail:
            script += f"""

{detail}"""

        script += f"""

This report comes from {source}. The full article link is in the description below — definitely worth reading if this caught your attention.

"""

    script += f"""And those were today's top {n} stories on TechBR News.

Every single hour we bring you a fresh roundup just like this one — covering artificial intelligence, cybersecurity, startups, gadgets, and everything happening in the world of technology.

If you found value in this video, please like it and subscribe to the channel right now. Hit the notification bell so you get every new roundup the moment it drops.

Share this video with anyone who wants to stay ahead in tech.

This has been TechBR News. Stay curious. Stay informed. See you in one hour."""

    return script

# ── TTS ────────────────────────────────────────────────────────
async def text_to_speech(text: str, output_path: Path, voice: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate="+5%", pitch="+0Hz")
    await communicate.save(str(output_path))

# ── Download de imagem ─────────────────────────────────────────
def download_image(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=10,
                         headers={"User-Agent": "TechBR-Bot/2.0"})
        if r.status_code == 200 and len(r.content) > 2000:
            dest.write_bytes(r.content)
            return True
    except Exception as e:
        log.debug(f"Image download failed: {e}")
    return False

# ── Frame de vídeo ─────────────────────────────────────────────
def create_video_frame(title: str, source: str, image_path: Path | None,
                       frame_num: int, total_frames: int,
                       category: str, story_num: int, total_stories: int) -> Image.Image:
    """Frame com indicador de história X/Y no lower third."""
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (*BG_DARK, 255))
    draw_gradient_bg(img, BG_DARK, (12, 10, 35))
    img = draw_tech_grid(img, alpha=12)

    # Background image
    if image_path and image_path.exists():
        try:
            bg = Image.open(image_path).convert("RGB")
            bw, bh = bg.size
            tr = VIDEO_W / VIDEO_H
            cr = bw / bh
            if cr > tr:
                nw = int(bh * tr); off = (bw - nw) // 2
                bg = bg.crop((off, 0, off + nw, bh))
            else:
                nh = int(bw / tr); off = (bh - nh) // 2
                bg = bg.crop((0, off, bw, off + nh))
            bg = bg.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
            ov = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
            od = ImageDraw.Draw(ov)
            for i in range(VIDEO_H):
                alpha = int(90 + 145 * (i / VIDEO_H))
                od.line([(0, i), (VIDEO_W, i)], fill=(0, 0, 10, alpha))
            img = Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB")
        except Exception:
            pass

    draw = ImageDraw.Draw(img)

    # ── TOP BAR ───────────────────────────────────────────────
    draw.rectangle([(0, 0), (VIDEO_W, 88)], fill=(0, 0, 0, 210))
    for i in range(3):
        draw.line([(0, 88 + i), (VIDEO_W, 88 + i)],
                  fill=(*ACCENT_BLUE, 80 - i * 25))

    # Logo
    draw.text((50, 20), "TECHBR", font=get_font(44, bold=True), fill=ACCENT_BLUE)
    draw.text((222, 20), "NEWS", font=get_font(44, bold=True), fill=TEXT_WHITE)
    draw.rectangle([(210, 22), (213, 66)], fill=(*ACCENT_BLUE, 180))

    # Badge LIVE
    draw_rounded_rect(draw, (340, 24, 460, 64), radius=6, fill=RED_LIVE)
    draw.text((354, 32), "● LIVE", font=get_font(26, bold=True), fill=TEXT_WHITE)

    # Story counter (topo direito)
    if total_stories > 1:
        counter_text = f"STORY {story_num} / {total_stories}"
        cfont = get_font(26, bold=True)
        cbbox = draw.textbbox((0, 0), counter_text, font=cfont)
        cx = VIDEO_W - cbbox[2] - 50
        draw_rounded_rect(draw, (cx - 12, 24, cx + cbbox[2] + 12, 64),
                          radius=6, fill=(20, 20, 40))
        draw.text((cx, 32), counter_text, font=cfont, fill=ACCENT_CYAN)

    # Data/hora (centro)
    now_str = datetime.now().strftime("%b %d, %Y  %H:%M")
    dfont = get_font(26)
    dbbox = draw.textbbox((0, 0), now_str, font=dfont)
    draw.text(((VIDEO_W - dbbox[2]) // 2, 30), now_str, font=dfont, fill=TEXT_GRAY)

    # ── PROGRESS BAR ─────────────────────────────────────────
    progress = frame_num / max(total_frames - 1, 1)
    bar_y = 88
    draw.rectangle([(0, bar_y), (VIDEO_W, bar_y + 5)], fill=(25, 25, 45))
    prog_w = int(VIDEO_W * progress)
    for px in range(prog_w):
        t = px / VIDEO_W
        r = int(ACCENT_BLUE[0] + (ACCENT_CYAN[0] - ACCENT_BLUE[0]) * t)
        g = int(ACCENT_BLUE[1] + (ACCENT_CYAN[1] - ACCENT_BLUE[1]) * t)
        b = int(ACCENT_BLUE[2] + (ACCENT_CYAN[2] - ACCENT_BLUE[2]) * t)
        draw.line([(px, bar_y), (px, bar_y + 4)], fill=(r, g, b))
    if prog_w > 0:
        px = prog_w - 1
        draw.ellipse([(px - 5, bar_y - 3), (px + 5, bar_y + 7)], fill=TEXT_WHITE)

    # ── STORY PROGRESS DOTS ───────────────────────────────────
    if total_stories > 1:
        dot_r = 5
        total_w = total_stories * (dot_r * 2 + 8) - 8
        start_x = (VIDEO_W - total_w) // 2
        dot_y = 110
        for d in range(total_stories):
            dx = start_x + d * (dot_r * 2 + 8)
            color = ACCENT_BLUE if d < story_num else (40, 40, 60)
            draw.ellipse([(dx, dot_y), (dx + dot_r * 2, dot_y + dot_r * 2)],
                         fill=color)

    # ── LOWER THIRD ───────────────────────────────────────────
    lt_y = VIDEO_H - 310
    lt_h = 280
    for i in range(lt_h):
        t = 1 - (i / lt_h) ** 0.5
        alpha = int(230 * t)
        draw.line([(0, lt_y + i), (VIDEO_W, lt_y + i)], fill=(0, 0, 8, alpha))

    # Barra lateral
    for i in range(3):
        draw.rectangle([(i * 3, lt_y), (i * 3 + 2, VIDEO_H - 50)],
                       fill=(*ACCENT_BLUE, 255 - i * 60))

    # Badge categoria
    cat_text = category.upper()
    cfont = get_font(26, bold=True)
    cbbox = draw.textbbox((0, 0), cat_text, font=cfont)
    draw_rounded_rect(draw, (30, lt_y + 12, 30 + cbbox[2] + 20, lt_y + 50),
                      radius=5, fill=ACCENT_BLUE)
    draw.text((40, lt_y + 18), cat_text, font=cfont, fill=(0, 0, 0))

    # Título
    title_font = get_font(60, bold=True)
    title_lines = wrap_text(draw, title, title_font, VIDEO_W - 120)
    ty = lt_y + 62
    for line in title_lines[:3]:
        draw.text((30, ty), line, font=title_font, fill=TEXT_WHITE)
        ty += 72

    # Rodapé
    sep_y = VIDEO_H - 95
    draw.line([(30, sep_y), (VIDEO_W - 30, sep_y)], fill=(*ACCENT_BLUE, 60), width=1)
    draw.text((30, sep_y + 12), f"\U0001f4f0  {source}",
              font=get_font(30), fill=TEXT_GRAY)
    url_text = "non-s.github.io  |  Subscribe ↑"
    ubbox = draw.textbbox((0, 0), url_text, font=get_font(28, bold=True))
    draw.text((VIDEO_W - ubbox[2] - 30, sep_y + 14), url_text,
              font=get_font(28, bold=True), fill=ACCENT_CYAN)

    return img.convert("RGB")

# ── Thumbnail roundup ───────────────────────────────────────────
def create_roundup_thumbnail(stories: list[dict], image_paths: list,
                             output: Path):
    """Thumbnail 1280×720 estilo 'Top N Stories'."""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), BG_DARK)

    # Gradiente de fundo
    draw = ImageDraw.Draw(img)
    for i in range(H):
        t = i / H
        r = int(8 * (1 - t) + 20 * t)
        g = int(8 * (1 - t) + 8 * t)
        b = int(18 * (1 - t) + 55 * t)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    # Imagem de fundo (primeira história com imagem)
    for ip in image_paths:
        if ip and ip.exists():
            try:
                bg = Image.open(ip).convert("RGB").resize((W, H), Image.LANCZOS)
                mask = Image.new("L", (W, H), 0)
                md = ImageDraw.Draw(mask)
                for x in range(W):
                    t = max(0, (x - W * 0.2) / (W * 0.8))
                    md.line([(x, 0), (x, H)], fill=int(min(1, t) * 170))
                img.paste(bg, (0, 0), mask)
            except Exception:
                pass
            break

    draw = ImageDraw.Draw(img)

    # Overlay esquerdo para legibilidade
    for x in range(int(W * 0.72)):
        t = 1 - x / (W * 0.72)
        draw.line([(x, 0), (x, H)], fill=(0, 0, 10, int(165 * t ** 0.5)))

    # Faixa lateral azul
    for i in range(10):
        draw.rectangle([(i * 2, 0), (i * 2 + 1, H)],
                       fill=(*ACCENT_BLUE, 255 - i * 22))

    n = len(stories)

    # Badge TOP N STORIES
    badge_text = f"TOP {n} STORIES"
    bfont = get_font(32, bold=True)
    bbbox = draw.textbbox((0, 0), badge_text, font=bfont)
    draw_rounded_rect(draw, (28, 28, 28 + bbbox[2] + 24, 76), radius=8, fill=RED_LIVE)
    draw.text((40, 38), badge_text, font=bfont, fill=TEXT_WHITE)

    # Título principal (história 1)
    main_title = stories[0]["title"] if stories else "Tech News Roundup"
    tfont = get_font(76, bold=True)
    tlines = wrap_text(draw, main_title, tfont, int(W * 0.67))
    if len(tlines) > 3:
        tfont = get_font(62, bold=True)
        tlines = wrap_text(draw, main_title, tfont, int(W * 0.67))
        lh = 78
    else:
        lh = 92

    ty = 100
    for line in tlines[:3]:
        draw.text((32, ty + 3), line, font=tfont, fill=(0, 0, 0))
        draw.text((30, ty), line, font=tfont, fill=TEXT_WHITE)
        ty += lh

    # Mini lista das histórias seguintes
    if len(stories) > 1:
        list_y = ty + 12
        lfont = get_font(26)
        for i, s in enumerate(stories[1:4], start=2):
            short = s["title"][:55] + ("…" if len(s["title"]) > 55 else "")
            draw.text((30, list_y), f"  {i}.  {short}", font=lfont,
                      fill=(200, 210, 230))
            list_y += 34

    # Separador
    draw.rectangle([(28, H - 110), (int(W * 0.66), H - 107)], fill=ACCENT_BLUE)

    # Branding
    draw.text((28, H - 92), "TECHBR", font=get_font(36, bold=True), fill=ACCENT_BLUE)
    draw.text((168, H - 92), "NEWS", font=get_font(36, bold=True), fill=TEXT_WHITE)
    now_str = datetime.now().strftime("%b %d, %Y — Hourly Roundup")
    draw.text((28, H - 48), now_str, font=get_font(24), fill=TEXT_GRAY)

    img.save(str(output), "JPEG", quality=95, optimize=True)
    log.info(f"  \U0001f5bc  Thumbnail: {output.name}")

# ── Gera vídeo com FFmpeg ───────────────────────────────────────
def create_roundup_video(stories: list[dict], image_paths: list[Path | None],
                         audio_path: Path, output_path: Path) -> bool:
    tmp_dir = output_path.parent / f"tmp_{output_path.stem}"
    tmp_dir.mkdir(exist_ok=True)

    # Duração do áudio
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True,
    )
    try:
        duration = float(result.stdout.strip())
    except Exception:
        duration = 600.0   # fallback 10 min

    fps = 24
    total_frames = int(duration * fps)
    n = len(stories)

    # Distribuição de frames por segmento
    # Intro: 4%, cada história: 76%/n, outro: 20%
    intro_end   = int(total_frames * 0.04)
    outro_start = int(total_frames * 0.80)
    story_span  = outro_start - intro_end
    frames_per_story = story_span // n

    log.info(f"  \U0001f3ac {total_frames} frames ({duration:.0f}s) — {n} histórias")

    n_render = min(total_frames, 120)   # até 120 keyframes renderizados
    for i in range(n_render):
        frame_num = int(i * total_frames / n_render)

        # Determina qual história exibir neste frame
        if frame_num < intro_end:
            story_idx = 0
        elif frame_num >= outro_start:
            story_idx = n - 1
        else:
            story_idx = min((frame_num - intro_end) // frames_per_story, n - 1)

        story = stories[story_idx]
        img_path = image_paths[story_idx] if story_idx < len(image_paths) else None

        frame = create_video_frame(
            title         = story["title"],
            source        = story["source"],
            image_path    = img_path,
            frame_num     = frame_num,
            total_frames  = total_frames,
            category      = story["category"],
            story_num     = story_idx + 1,
            total_stories = n,
        )
        frame.save(str(tmp_dir / f"frame_{i:05d}.png"))

    # Concat list
    concat_file = tmp_dir / "frames.txt"
    dur_each = duration / n_render
    with open(concat_file, "w") as f:
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
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(tmp_dir))
    shutil.rmtree(tmp_dir, ignore_errors=True)

    if result.returncode != 0:
        log.error(f"FFmpeg error: {result.stderr[-800:]}")
        return False

    log.info(f"  ✅ Vídeo gerado: {output_path.name}")
    return True

# ── Metadados SEO com capítulos ─────────────────────────────────
def build_metadata(roundup_slug: str, stories: list[dict],
                   thumbnail: Path, video: Path,
                   duration_estimate: float) -> dict:
    n = len(stories)
    year = datetime.now().year
    date_str = datetime.now().strftime("%B %d, %Y")

    yt_title = f"Tech News Roundup — Top {n} Stories | {date_str} | TechBR News"

    # Descrição com capítulos estimados
    intro_s   = 0
    story_dur = int((duration_estimate * 0.76) / n)
    outro_s   = int(duration_estimate * 0.80)

    def fmt_time(s: int) -> str:
        return f"{s // 60}:{s % 60:02d}"

    chapters = f"⏱ CHAPTERS\n{fmt_time(intro_s)} Introduction\n"
    t = 30   # intro ~30s
    for i, story in enumerate(stories, 1):
        short = story["title"][:60] + ("…" if len(story["title"]) > 60 else "")
        chapters += f"{fmt_time(t)} Story {i}: {short}\n"
        t += story_dur
    chapters += f"{fmt_time(outro_s)} Wrap-up & Subscribe"

    stories_summary = "\n".join(
        f"  {i}. {s['title'][:80]}" for i, s in enumerate(stories, 1)
    )

    yt_desc = (
        f"In this hour's TechBR News Roundup we cover {n} stories:\n\n"
        f"{stories_summary}\n\n"
        "━" * 28 + "\n"
        f"\U0001f310 Sources:\n" +
        "\n".join(f"  • Story {i}: {s['source_url']}"
                  for i, s in enumerate(stories, 1)) + "\n\n"
        "━" * 28 + "\n"
        f"{chapters}\n\n"
        "━" * 28 + "\n"
        "\U0001f514 SUBSCRIBE for hourly tech news → https://youtube.com/@techbrnews\n"
        "\U0001f4f0 Read more at → https://non-s.github.io\n\n"
        "━" * 28 + "\n"
        f"© {year} TechBR News. Original articles belong to their respective sources.\n"
        "#TechNews #TechRoundup #Technology #TechBRNews #AINews #Startups"
    )

    # Tags combinadas de todas as histórias
    base_tags = [
        "tech news", "technology news", "TechBR News", f"tech news {year}",
        "tech roundup", "hourly tech news", "breaking tech", "latest technology",
        "tech news today", "technology today",
    ]
    story_tags = []
    for s in stories:
        story_tags.extend(s.get("tags", []))
    cat_tags = {
        "AI":       ["artificial intelligence", "ChatGPT", "LLM", "OpenAI", "AI news"],
        "SECURITY": ["cybersecurity", "data breach", "hacking", "malware"],
        "BUSINESS": ["startup funding", "IPO", "acquisition", "venture capital"],
        "BIG TECH": ["Apple", "Google", "Microsoft", "Meta", "Amazon", "Nvidia"],
        "HARDWARE": ["smartphone", "laptop", "GPU", "processor", "chip"],
        "TECH":     ["software", "internet", "programming", "digital"],
    }
    dominant_cat = max(set(s["category"] for s in stories),
                       key=lambda c: sum(1 for s in stories if s["category"] == c))
    extra = cat_tags.get(dominant_cat, cat_tags["TECH"])
    all_tags = list(dict.fromkeys(base_tags + extra + story_tags))[:30]

    metadata = {
        "title":       yt_title,
        "description": yt_desc,
        "tags":        all_tags,
        "category_id": "28",
        "privacy":     "public",
        "thumbnail":   str(thumbnail),
        "video":       str(video),
        "stories":     [s["slug"] for s in stories],
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }
    meta_path = video.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    return metadata

# ── Utilitários ─────────────────────────────────────────────────
def roundup_slug() -> str:
    return datetime.now().strftime("roundup-%Y-%m-%d-%H")

def roundup_done(slug: str) -> bool:
    return (VIDEOS_DIR / f"{slug}.mp4").exists() or \
           (VIDEOS_DIR / f"{slug}.done").exists() or \
           (VIDEOS_DIR / f"{slug}.json").exists()

def post_has_roundup(post_slug: str) -> bool:
    return (VIDEOS_DIR / f"{post_slug}.roundup").exists()

def mark_posts_as_used(post_slugs: list[str]):
    for slug in post_slugs:
        (VIDEOS_DIR / f"{slug}.roundup").touch()

def guess_category(tags: list, title: str) -> str:
    text = (title + " ".join(tags)).lower()
    if any(w in text for w in ["ai", "artificial intelligence", "machine learning",
                                "gpt", "llm", "openai", "anthropic", "gemini", "claude"]):
        return "AI"
    if any(w in text for w in ["security", "hack", "cyber", "breach", "malware",
                                "ransomware", "vulnerability", "exploit"]):
        return "SECURITY"
    if any(w in text for w in ["startup", "funding", "ipo", "acquisition",
                                "billion", "venture", "raised"]):
        return "BUSINESS"
    if any(w in text for w in ["apple", "google", "microsoft", "meta",
                                "amazon", "nvidia", "tesla"]):
        return "BIG TECH"
    if any(w in text for w in ["phone", "iphone", "android", "hardware",
                                "chip", "gpu", "laptop", "processor"]):
        return "HARDWARE"
    return "TECH"

# ── Principal ───────────────────────────────────────────────────
def main():
    VIDEOS_DIR.mkdir(exist_ok=True)
    posts_dir = Path("_posts")
    if not posts_dir.exists():
        log.error("_posts/ não encontrado")
        return

    slug = roundup_slug()
    if roundup_done(slug):
        log.info(f"Roundup desta hora já existe: {slug}. Nada a fazer.")
        return

    # Coleta posts sem roundup (mais recentes primeiro)
    posts = sorted(posts_dir.glob("*.md"), reverse=True)
    candidates = [p for p in posts if not post_has_roundup(p.stem)]

    if len(candidates) < MIN_STORIES:
        log.info(f"Apenas {len(candidates)} post(s) disponível(is) — mínimo {MIN_STORIES}. Aguardando.")
        return

    # Seleciona até STORIES_PER_VIDEO histórias
    selected = candidates[:STORIES_PER_VIDEO]
    stories  = []

    for post_file in selected:
        raw = post_file.read_text(encoding="utf-8")
        fm  = {}
        if raw.startswith("---"):
            end = raw.find("---", 3)
            if end > 0:
                for line in raw[3:end].splitlines():
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        fm[k.strip()] = v.strip().strip('"')

        title    = fm.get("title", post_file.stem.replace("-", " ").title())
        desc     = fm.get("description", "")
        source   = fm.get("source_name", "TechBR News")
        src_url  = fm.get("source_url", "https://non-s.github.io")
        img_url  = fm.get("image", "")
        tags_raw = fm.get("tags", "[]")
        try:
            tags = json.loads(tags_raw.replace("'", '"'))
        except Exception:
            tags = ["tech"]

        stories.append({
            "slug":       post_file.stem,
            "title":      title,
            "description": desc,
            "source":     source,
            "source_url": src_url,
            "image_url":  img_url,
            "tags":       tags,
            "category":   guess_category(tags, title),
        })

    if len(stories) < MIN_STORIES:
        log.info(f"Stories insuficientes após parsing ({len(stories)}). Aguardando.")
        return

    log.info(f"\U0001f4f9 Roundup '{slug}' — {len(stories)} histórias:")
    for i, s in enumerate(stories, 1):
        log.info(f"  {i}. [{s['category']}] {s['title'][:70]}")

    tmp = Path(f"/tmp/yt_{slug}")
    tmp.mkdir(exist_ok=True)

    # Download de imagens
    image_paths: list[Path | None] = []
    for i, story in enumerate(stories):
        if story["image_url"]:
            dest = tmp / f"img_{i}.jpg"
            image_paths.append(dest if download_image(story["image_url"], dest) else None)
        else:
            image_paths.append(None)

    # Voz dominante para TTS
    cats = [s["category"] for s in stories]
    dominant_cat = max(set(cats), key=cats.count)
    voice = VOICE_BY_CATEGORY.get(dominant_cat, VOICE_DEFAULT)

    # TTS
    script   = build_roundup_script(stories)
    mp3_path = tmp / "narration.mp3"
    try:
        asyncio.run(text_to_speech(script, mp3_path, voice))
        size_kb = mp3_path.stat().st_size / 1024
        log.info(f"  \U0001f399  TTS gerado ({voice}): {size_kb:.0f} KB")
    except Exception as e:
        log.error(f"  ❌ TTS falhou: {e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return

    # Duração estimada do áudio
    res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(mp3_path)],
        capture_output=True, text=True,
    )
    try:
        duration = float(res.stdout.strip())
    except Exception:
        duration = 630.0

    log.info(f"  ⏱  Duração estimada: {duration/60:.1f} min")
    if duration < 6 * 60:
        log.warning(f"  ⚠️  Vídeo abaixo de 6 minutos ({duration/60:.1f} min) — verifique o script")

    # Thumbnail
    thumb_path = VIDEOS_DIR / f"{slug}_thumb.jpg"
    create_roundup_thumbnail(stories, image_paths, thumb_path)

    # Vídeo
    video_path = VIDEOS_DIR / f"{slug}.mp4"
    ok = create_roundup_video(stories, image_paths, mp3_path, video_path)
    if not ok:
        shutil.rmtree(tmp, ignore_errors=True)
        return

    # Metadados SEO com capítulos
    build_metadata(slug, stories, thumb_path, video_path, duration)

    # Marca posts como usados (não serão incluídos em próximo roundup)
    mark_posts_as_used([s["slug"] for s in stories])

    shutil.rmtree(tmp, ignore_errors=True)
    log.info(f"\n\U0001f3c1 Roundup concluído: {slug} ({len(stories)} histórias, ~{duration/60:.1f} min)")


if __name__ == "__main__":
    main()
