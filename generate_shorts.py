#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_shorts.py — Gera YouTube Shorts verticais a partir de notícias do blog
================================================================================
Formato: vídeo vertical 1080x1920, 45-55 segundos, uma história por Short.
Máximo 3 Shorts por execução para respeitar limites de API.

Estrutura de cada Short:
  Intro       ~3s    "GlobalBR News — breaking story"
  Título      ~5s    Título em destaque
  Ponto 1    ~10s    Primeiro bullet point
  Ponto 2    ~10s    Segundo bullet point
  Ponto 3    ~10s    Terceiro bullet point
  CTA         ~5s    "Follow for more — link in bio"

Total alvo: ~43-55 segundos (dentro do limite de 60s do YouTube Shorts)
"""

import os, re, json, asyncio, subprocess, logging, shutil, sys, time, urllib.parse, contextlib
from pathlib import Path
from datetime import datetime, timezone

import requests
from PIL import Image, ImageDraw, ImageFont

# fcntl is POSIX-only; we use it to serialise queue access against
# fetch_news.py. Guarded for local Windows dev — the CI runner is Linux.
try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from utils.ai_helper import ai_text as _ai_text
from utils.text import humanize_for_tts

# ── Config ────────────────────────────────────────────────────────
VIDEOS_DIR      = Path("_videos")
SHORTS_DONE_FILE = VIDEOS_DIR / "shorts_done.json"
LOG_FILE        = "generate_shorts.log"
# Cap of shorts produced per run. Overridable via env var so the
# workflow can tune it without editing this file. Defaults to 3 —
# matches youtube-bot.yml schedule (1 run/day × 3 shorts = 3/day).
MAX_SHORTS_PER_RUN = int(os.environ.get("MAX_SHORTS_PER_RUN", "3"))
SHORT_W, SHORT_H = 1080, 1920  # vertical 9:16

# Paleta de cores — identidade GlobalBR
BG_DARK      = (8, 8, 18)
ACCENT_BLUE  = (0, 195, 255)
ACCENT_CYAN  = (0, 240, 200)
RED_LIVE     = (220, 50, 50)
TEXT_WHITE   = (245, 245, 255)
TEXT_GRAY    = (160, 165, 190)

# Cores por categoria
CATEGORY_COLORS = {
    "AI":          (0, 195, 255),
    "SECURITY":    (220, 50, 50),
    "BUSINESS":    (255, 165, 0),
    "BIG TECH":    (0, 200, 120),
    "HARDWARE":    (160, 80, 255),
    "TECH":        (0, 195, 255),
    "WORLD":       (255, 200, 0),
    "POLITICS":    (200, 80, 80),
    "WAR":         (220, 50, 50),
    "SCIENCE":     (0, 180, 255),
    "HEALTH":      (0, 200, 120),
    "SPORTS":      (255, 140, 0),
    "FOOD":        (255, 180, 0),
    "ENVIRONMENT": (0, 200, 80),
    "TRAVEL":      (0, 200, 200),
    "ENTERTAINMENT": (180, 0, 220),
}

VOICE_SHORT = "en-US-JennyNeural"

SHORTS_HASHTAGS = "#Shorts #NewsShorts #BreakingNews #GlobalBRNews #WorldNews #ShortNews"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Fontes / utilitários compartilhados com generate_video.py ─────
from utils.video_common import (
    get_font,
    draw_rounded_rect,
    wrap_text,
    download_image as _download_image_common,
)


def clean_text(text: str, max_chars: int = 500) -> str:
    t = re.sub(r'<[^>]+>', ' ', text)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:max_chars]


# ── Extrai 3 bullet points da descrição ───────────────────────────
def extract_key_points(description: str) -> list[str]:
    """Extract 3 concise key points from a story description."""
    desc = clean_text(description, 800)
    sentences = re.split(r'(?<=[.!?])\s+', desc)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    points = []
    for s in sentences[:6]:
        # Truncate long sentences to keep them punchy
        if len(s) > 100:
            s = s[:97] + "..."
        points.append(s)
        if len(points) == 3:
            break

    # Don't pad with boilerplate — empty slots are better than literal
    # "Stay tuned for more updates on this story." on the thumbnail.
    return points[:3]


# ── Categorizar post ──────────────────────────────────────────────
def guess_category(tags: list, title: str) -> str:
    """Pick a broad YouTube-style category label.

    Tag-driven first (the post already carries `categories:`), then
    keyword heuristics for tech sub-niches. Returns an uppercase label.
    """
    text = (title + " " + " ".join(tags)).lower()
    tag_set = {t.lower().strip() for t in (tags or [])}

    cat_aliases = {
        "POLITICS":      {"politics", "politicians", "elections", "government"},
        "WAR":           {"war", "conflict", "ukraine", "gaza", "israel", "russia"},
        "WORLD":         {"world", "international", "diplomacy"},
        "BUSINESS":      {"business", "economy", "finance", "markets"},
        "SCIENCE":       {"science", "research", "space", "physics", "biology"},
        "HEALTH":        {"health", "medicine", "wellness", "medical"},
        "ENVIRONMENT":   {"environment", "climate", "sustainability"},
        "ENTERTAINMENT": {"entertainment", "movies", "music", "celebrity"},
        "SPORTS":        {"sports", "football", "soccer", "basketball", "tennis"},
        "TRAVEL":        {"travel", "tourism", "destinations"},
        "FOOD":          {"food", "restaurant", "cooking", "cuisine"},
    }
    for label, keys in cat_aliases.items():
        if tag_set & keys:
            return label

    if (re.search(r'\bai\b', text) or
            any(w in text for w in ["artificial intelligence", "machine learning",
                                     "gpt", "llm", "openai", "anthropic",
                                     "gemini", "claude", "deepmind", "mistral"])):
        return "AI"
    if any(w in text for w in ["cybersecurity", "cyber attack", "cyberattack",
                                "data breach", "malware", "ransomware",
                                "vulnerability", "zero-day", "phishing",
                                "exploit", "hacking", "hacked", "spyware"]):
        return "SECURITY"
    if any(w in text for w in ["startup", "funding", "series a", "series b",
                                "series c", "ipo", "acquisition", "venture capital",
                                "unicorn"]):
        return "BUSINESS"
    if any(w in text for w in ["apple", "google", "microsoft", "meta",
                                "amazon", "nvidia", "tesla", "samsung"]):
        return "BIG TECH"
    if any(w in text for w in ["phone", "iphone", "android", "hardware",
                                "chip", "gpu", "laptop", "processor", "display"]):
        return "HARDWARE"
    if any(w in text for w in ["war", "military", "missile", "army", "navy",
                                "combat", "troops", "weapon", "pentagon"]):
        return "WAR"
    return "TECH"


# ── TTS ───────────────────────────────────────────────────────────
TTS_TIMEOUT_S = float(os.environ.get("TTS_TIMEOUT_S", "45"))


async def text_to_speech(text: str, output_path: Path, voice: str = VOICE_SHORT):
    """
    Render `text` to `output_path` (MP3) via Microsoft Edge-TTS.

    Wrapped in asyncio.wait_for so a hung WebSocket can't pin the whole
    Short generation. The previous version (no timeout) would silently
    hang for up to the workflow's full 30-min budget if edge-tts's CDN
    blipped — that meant zero Shorts shipped that day. We raise on
    timeout so the caller logs the failure and moves on to the next
    story.
    """
    import edge_tts
    # Shorts have a tight 60s budget so we still nudge the rate up a
    # little — but +8% sounded panicked. +3% keeps it brisk without
    # losing the human-paced feel.
    communicate = edge_tts.Communicate(text, voice, rate="+3%", pitch="+0Hz")
    await asyncio.wait_for(
        communicate.save(str(output_path)),
        timeout=TTS_TIMEOUT_S,
    )


def _ai_shorts_meta(title: str, description: str, category: str) -> dict:
    """Generate a magnetic YouTube Shorts title + thumbnail hook + tags.

    Returns dict with: yt_title (max 80 chars, no #Shorts suffix — caller
    adds it), thumbnail_hook (3-5 punchy words), extra_tags (list).
    Returns {} on parse failure — caller falls back to defaults.
    """
    prompt = (
        f"You are a YouTube Shorts growth strategist. Generate metadata for a 60-second "
        f"news Short. Respond ONLY as valid JSON.\n\n"
        f"Story title: {title}\n"
        f"Category: {category}\n"
        f"Description: {description[:400]}\n\n"
        f"Rules for YT_TITLE (max 80 chars, no '#Shorts' suffix — system adds it):\n"
        f"  - Curiosity hook. Specifics (name, number, twist) beat vague phrasing.\n"
        f"  - Question or surprising statement works well. No ALL CAPS title.\n"
        f"  - DO NOT just copy the headline — rewrite it as something that makes "
        f"someone stop scrolling.\n"
        f"  - Good shapes: 'Why X just happened', 'The {category.lower()} story nobody saw coming', "
        f"'X says Y — and it changes everything', 'How [thing] really works'.\n\n"
        f"Rules for THUMBNAIL_HOOK (3-5 words, max 28 chars, ALL CAPS OK):\n"
        f"  - Punchy phrase that dominates the vertical thumbnail. Different from yt_title.\n"
        f"  - Examples: 'TRUMP SHOCKS WALL ST', 'GAZA CEASEFIRE BREAKS', 'AI BEATS DOCTORS'.\n\n"
        f"Rules for EXTRA_TAGS (3 items):\n"
        f"  - Real entities from this story (a person, a place, a company). Lowercase.\n\n"
        f'Return this exact JSON: {{"yt_title":"...","thumbnail_hook":"...","extra_tags":["...","...","..."]}}'
    )
    raw = _ai_text(prompt, seed=abs(hash(title)) % 9999, timeout=18, json_mode=True)
    if not raw:
        return {}
    try:
        clean = re.sub(r'```(?:json)?\s*|\s*```', '', raw).strip()
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m:
            return json.loads(m.group(), strict=False)
    except Exception as e:
        log.warning(f"AI Shorts meta parse error: {e}")
    return {}


# ── Script de narração do Short ───────────────────────────────────
def _ai_shorts_hook(title: str, points: list[str], category: str) -> str:
    """Generate a powerful hook sentence for a YouTube Short using AI."""
    prompt = (
        f"Write a single powerful hook sentence (max 20 words) for a YouTube Short about this news story.\n\n"
        f"Story: {title}\n"
        f"Category: {category}\n"
        f"Key facts: {' '.join(points[:2])}\n\n"
        f"CRITICAL: The script MUST start with a powerful hook in the FIRST sentence — a shocking statistic, "
        f"provocative question, or urgent fact that makes viewers stop scrolling. Examples:\n"
        f'- "Did you know [shocking fact]?"\n'
        f'- "This just happened and it changes everything:"\n'
        f'- "[Number] people were affected when..."\n'
        f'- "Breaking: [dramatic summary in 10 words]"\n\n'
        f"The hook must appear in the very first 3 seconds of audio. Do NOT start with introductions "
        f'like "Hi" or "Welcome" or "Today we\'ll talk about".\n\n'
        f"Return ONLY the hook sentence, nothing else."
    )
    return _ai_text(prompt, seed=abs(hash(title)) % 9999, timeout=15)


def build_short_script(title: str, points: list[str], category: str) -> str:
    """
    Build a ~43-55 second narration script for a YouTube Short.
    Breakdown:
      Hook    ~3s   (15 words) — AI-generated powerful opener
      Title   ~5s   (25 words)
      Point 1 ~10s  (50 words)
      Point 2 ~10s  (50 words)
      Point 3 ~10s  (50 words)
      CTA     ~5s   (25 words)
    """
    cat_label = {
        "AI": "in artificial intelligence",
        "SECURITY": "in cybersecurity",
        "BUSINESS": "in business",
        "BIG TECH": "in big tech",
        "HARDWARE": "in hardware",
        "WAR": "in world conflict",
        "WORLD": "in world news",
        "TECH": "in technology",
    }.get(category.upper(), "in the news")

    # Try AI hook first, fall back to template hook
    ai_hook = _ai_shorts_hook(title, points, category)
    hook = ai_hook if ai_hook and len(ai_hook) > 10 else f"Breaking news {cat_label} — GlobalBR News has you covered."

    script = f"""{hook}

{title}

Here is what you need to know.

First: {points[0]}

Second: {points[1]}

Third: {points[2]}

Follow GlobalBR News for hourly updates and click the link in our bio to read the full story. Subscribe so you never miss what matters."""

    return script


# ── AI background via Pollinations ───────────────────────────────
def generate_ai_background(title: str, category: str, dest: Path) -> bool:
    """Generate a 1080x1920 vertical background via Pollinations.ai (free)."""
    scene_map = {
        "AI":          "futuristic neural network visualization, glowing circuit brain, blue neon tech, vertical composition",
        "SECURITY":    "dark cyber hacker atmosphere, glowing code streams, ominous red and blue, vertical",
        "BUSINESS":    "futuristic city financial district, glowing skyscrapers, stock market data, vertical",
        "BIG TECH":    "sleek tech devices glowing, modern minimalist product lighting, vertical",
        "HARDWARE":    "advanced microchip circuit board close-up, glowing blue, ultra sharp, vertical",
        "WAR":         "dramatic military scene, smoke and fire, helicopter silhouette, golden hour, vertical",
        "WORLD":       "dramatic globe earth from space, city skyline at night, epic scale, vertical",
        "POLITICS":    "government building columns with dramatic sky, powerful atmosphere, vertical",
        "SCIENCE":     "stunning NASA space view, galaxy nebula, cosmic colors, vertical",
        "HEALTH":      "futuristic medical lab glowing blue, DNA helix, clean white light, vertical",
        "ENVIRONMENT": "dramatic nature landscape, stormy sky over ocean, earth crisis, vertical",
        "TECH":        "futuristic smart city, holographic displays, neon blue tech, vertical",
    }
    scene = scene_map.get(category.upper(), scene_map["TECH"])
    short_title = title[:60]
    prompt = (
        f"{scene}, ultra-high quality, cinematic dramatic lighting, "
        f"vivid saturated colors, photorealistic, 4K, sharp focus, "
        f"professional news broadcast aesthetic, inspired by: {short_title}"
    )
    encoded = urllib.parse.quote(prompt)
    # Mix wall clock into the seed so consecutive Shorts in the same
    # category don't fall on the same Pollinations background.
    seed = (abs(hash(prompt)) + int(datetime.now().timestamp())) % 999999
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={SHORT_W}&height={SHORT_H}&nologo=true&seed={seed}&model=flux"
    )
    try:
        log.info(f"  Generating AI background via Pollinations.ai...")
        r = requests.get(url, timeout=90, headers={"User-Agent": "GlobalBR-Bot/3.0"})
        r.raise_for_status()
        dest.write_bytes(r.content)
        log.info(f"  AI background saved ({len(r.content) // 1024} KB)")
        return True
    except Exception as e:
        log.warning(f"  Pollinations failed ({e}), using fallback background")
        return False


# Shorts use a 15s timeout (single image, more important not to fail).
def download_image(url: str, dest: Path) -> bool:
    return _download_image_common(url, dest, timeout=15)


# ── Frame vertical do Short ───────────────────────────────────────
def create_short_frame(title: str, category: str, points: list[str],
                       source: str, bg_path: Path | None) -> Image.Image:
    """
    Create a single 1080x1920 vertical frame for a YouTube Short.
    Layout (top to bottom):
      - AI background + dark overlay
      - Category badge (top ~10%)
      - Story title (center, ~25-55%)
      - 3 bullet points (middle, ~55-80%)
      - GlobalBR News branding (bottom ~85-95%)
    """
    img = Image.new("RGB", (SHORT_W, SHORT_H), BG_DARK)

    # ── Background ───────────────────────────────────────────────
    if bg_path and bg_path.exists():
        try:
            bg = Image.open(bg_path).convert("RGB")
            bw, bh = bg.size
            # Crop to 9:16 vertical ratio
            target_ratio = SHORT_W / SHORT_H
            img_ratio = bw / bh
            if img_ratio > target_ratio:
                # Too wide: crop sides
                new_w = int(bh * target_ratio)
                off = (bw - new_w) // 2
                bg = bg.crop((off, 0, off + new_w, bh))
            else:
                # Too tall: crop top/bottom
                new_h = int(bw / target_ratio)
                off = (bh - new_h) // 2
                bg = bg.crop((0, off, bw, off + new_h))
            bg = bg.resize((SHORT_W, SHORT_H), Image.LANCZOS)
            img.paste(bg)
        except Exception:
            pass

    # ── Dark overlay for readability ─────────────────────────────
    overlay = Image.new("RGBA", (SHORT_W, SHORT_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Gradient: lighter at top, darker in text zones
    for i in range(SHORT_H):
        t = i / SHORT_H
        # Top 15%: moderate overlay
        # Middle 60%: heavy overlay for text
        # Bottom 20%: heavy overlay for branding
        if t < 0.15:
            alpha = 120
        elif t < 0.75:
            alpha = int(160 + 50 * ((t - 0.15) / 0.60))
        else:
            alpha = 210
        od.line([(0, i), (SHORT_W, i)], fill=(0, 0, 10, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    cat_color = CATEGORY_COLORS.get(category.upper(), ACCENT_BLUE)
    padding = 48

    # ── Category badge (top area) ─────────────────────────────────
    cat_text = category.upper()
    cat_font = get_font(52, bold=True)
    cbbox = draw.textbbox((0, 0), cat_text, font=cat_font)
    badge_w = cbbox[2] + 48
    badge_h = cbbox[3] + 24
    badge_x = (SHORT_W - badge_w) // 2
    badge_y = 120
    draw_rounded_rect(draw,
                      (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h),
                      radius=14, fill=(*cat_color, 230))
    draw.text((badge_x + 24, badge_y + 12), cat_text, font=cat_font,
              fill=(0, 0, 0))

    # ── LIVE dot ─────────────────────────────────────────────────
    live_font = get_font(38, bold=True)
    live_y = badge_y + badge_h + 28
    live_text = "● LIVE"
    lbbox = draw.textbbox((0, 0), live_text, font=live_font)
    lx = (SHORT_W - lbbox[2]) // 2
    draw.text((lx, live_y), live_text, font=live_font, fill=RED_LIVE)

    # ── Story title (large, centered) ────────────────────────────
    title_start_y = int(SHORT_H * 0.22)
    title_font = get_font(72, bold=True)
    title_max_w = SHORT_W - padding * 2
    title_lines = wrap_text(draw, title, title_font, title_max_w)

    # If title too long, use smaller font
    if len(title_lines) > 4:
        title_font = get_font(58, bold=True)
        title_lines = wrap_text(draw, title, title_font, title_max_w)

    line_height = 88
    total_title_h = len(title_lines[:4]) * line_height
    ty = title_start_y
    for line in title_lines[:4]:
        lbbox = draw.textbbox((0, 0), line, font=title_font)
        lx = (SHORT_W - lbbox[2]) // 2
        # Shadow
        draw.text((lx + 3, ty + 3), line, font=title_font, fill=(0, 0, 0))
        # Text
        draw.text((lx, ty), line, font=title_font, fill=TEXT_WHITE)
        ty += line_height

    # ── Divider line ─────────────────────────────────────────────
    div_y = ty + 24
    draw.line([(padding, div_y), (SHORT_W - padding, div_y)],
              fill=(*cat_color, 150), width=3)

    # ── 3 bullet points ───────────────────────────────────────────
    bullet_start_y = div_y + 36
    bullet_font = get_font(46)
    bullet_bold_font = get_font(46, bold=True)
    bullet_max_w = SHORT_W - padding * 2 - 60  # 60 for bullet icon
    bullet_labels = ["01", "02", "03"]
    bullet_spacing = 16  # vertical gap between bullets

    by = bullet_start_y
    for idx, point in enumerate(points[:3]):
        # Bullet number badge
        num_font = get_font(36, bold=True)
        num_text = bullet_labels[idx]
        nbbox = draw.textbbox((0, 0), num_text, font=num_font)
        num_w = nbbox[2] + 16
        num_h = nbbox[3] + 10
        draw_rounded_rect(draw, (padding, by, padding + num_w, by + num_h),
                          radius=8, fill=cat_color)
        draw.text((padding + 8, by + 5), num_text, font=num_font, fill=(0, 0, 0))

        # Bullet text
        blines = wrap_text(draw, point, bullet_font, bullet_max_w)
        text_x = padding + num_w + 16
        text_y = by
        for bline in blines[:3]:
            draw.text((text_x, text_y), bline, font=bullet_font, fill=TEXT_WHITE)
            text_y += 52

        by = max(by + num_h + bullet_spacing, text_y + bullet_spacing)

    # ── Bottom branding ───────────────────────────────────────────
    brand_y = int(SHORT_H * 0.88)

    # Horizontal line
    draw.line([(padding, brand_y), (SHORT_W - padding, brand_y)],
              fill=(*ACCENT_BLUE, 80), width=2)

    # Logo text
    logo_font = get_font(54, bold=True)
    brand_y2 = brand_y + 24
    draw.text((padding, brand_y2), "GLOBAL", font=logo_font, fill=ACCENT_BLUE)
    gbbox = draw.textbbox((0, 0), "GLOBAL", font=logo_font)
    sep_x = padding + gbbox[2] + 12
    draw.rectangle([(sep_x, brand_y2 + 4), (sep_x + 4, brand_y2 + gbbox[3] - 4)],
                   fill=(*ACCENT_BLUE, 180))
    draw.text((sep_x + 16, brand_y2), "BR NEWS", font=logo_font, fill=TEXT_WHITE)

    # Source
    src_font = get_font(36)
    src_y = brand_y2 + 68
    draw.text((padding, src_y), f"Source: {source}", font=src_font, fill=TEXT_GRAY)

    # CTA
    cta_font = get_font(38, bold=True)
    cta_text = "Follow for more  |  non-s.github.io"
    cta_y = src_y + 48
    ctabbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    ctx = (SHORT_W - ctabbox[2]) // 2
    draw.text((ctx, cta_y), cta_text, font=cta_font, fill=ACCENT_CYAN)

    # Date stamp
    date_font = get_font(32)
    date_str = datetime.now().strftime("%b %d, %Y")
    dbbox = draw.textbbox((0, 0), date_str, font=date_font)
    dx = SHORT_W - dbbox[2] - padding
    draw.text((dx, brand_y + 8), date_str, font=date_font, fill=TEXT_GRAY)

    return img.convert("RGB")


# ── Thumbnail do Short ────────────────────────────────────────────
# Static thumbnail shipped with the repo. Every Short uses this same
# JPEG as its YouTube thumbnail — the channel keeps a consistent
# brand grid on /shorts. We can swap it by replacing the PNG; no code
# change needed.
STATIC_THUMB_PATH = Path(__file__).parent / "scripts" / "assets" / "thumbnail_static.png"


def create_short_thumbnail(frame_img: Image.Image, output: Path):
    """
    Write the YouTube thumbnail. By design, every Short uses the same
    static brand thumbnail at STATIC_THUMB_PATH so the channel grid
    stays uniform. If that file is missing for any reason, fall back
    to saving the rendered frame so we never publish without a thumb.
    """
    if STATIC_THUMB_PATH.exists():
        try:
            thumb = Image.open(STATIC_THUMB_PATH).convert("RGB")
            # YouTube recommends <=2 MB, 16:9 or vertical — JPEG quality
            # 90 lands at ~120 KB for our 1080x1920 source.
            thumb.save(str(output), "JPEG", quality=90, optimize=True)
            log.info(f"  Thumbnail (static brand): {output.name}")
            return
        except Exception as exc:
            log.warning(
                f"  ⚠ Failed to load static thumb at {STATIC_THUMB_PATH}: {exc}. "
                "Falling back to per-Short frame."
            )
    thumb = frame_img.copy()
    thumb.save(str(output), "JPEG", quality=92, optimize=True)
    log.info(f"  Thumbnail (rendered fallback): {output.name}")


# ── Combina imagem + áudio com FFmpeg ─────────────────────────────
def create_short_video(frame_path: Path, audio_path: Path,
                       output_path: Path) -> bool:
    """
    Use FFmpeg to create a vertical Short MP4:
    - Loop the static frame image for the duration of the audio
    - 1080x1920, 30fps, yuv420p
    - Audio from edge-tts MP3
    """
    # Get audio duration
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True,
    )
    try:
        duration = float(result.stdout.strip())
    except Exception:
        duration = 50.0  # fallback

    log.info(f"  Audio duration: {duration:.1f}s")

    # Enforce 60s max (YouTube Shorts requirement)
    if duration > 59.5:
        log.warning(f"  Audio is {duration:.1f}s — trimming to 59s for Shorts compliance")
        duration = 59.0

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(frame_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
               f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2,fps=30",
        "-t", str(duration),
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.error(f"FFmpeg error: {result.stderr[-800:]}")
        return False

    log.info(f"  Video created: {output_path.name} ({output_path.stat().st_size // 1024} KB)")
    return True


# ── Tracking: quais posts já foram transformados em Short ────────
def load_shorts_done() -> set:
    VIDEOS_DIR.mkdir(exist_ok=True)
    if SHORTS_DONE_FILE.exists():
        try:
            data = json.loads(SHORTS_DONE_FILE.read_text(encoding="utf-8"))
            return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()
    return set()


def save_shorts_done(done: set):
    SHORTS_DONE_FILE.write_text(
        json.dumps(sorted(done), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Metadados no formato upload_youtube.py ────────────────────────
def build_short_metadata(story: dict, video_path: Path,
                         thumb_path: Path,
                         ai_meta: dict | None = None) -> dict:
    """
    Build the JSON metadata payload that upload_youtube.py consumes.
    Required keys downstream: title, description, tags, category_id,
                              privacy, thumbnail, video.

    SEO inputs (already authored by fetch_news.py's prompt and carried
    on the queue entry):

      story["title"]          — seo_title, 40-55 chars, front-loaded
      story["yt_tags"]        — 5 lowercase tags (entities + evergreen)
      story["yt_description"] — 2-3 sentences ending with "#Shorts ..."

    YouTube hard limits we respect:
      - title:        100 chars total (we soft-cap before adding the
                      mandatory #Shorts suffix)
      - description:  5000 chars (we emit ~500)
      - tags:         500 chars combined across the list

    `ai_meta` is kept as a backwards-compat hook for when the queue
    didn't ship SEO fields yet — we'll fall through to its yt_title /
    extra_tags / thumbnail_hook keys. Anything from the queue wins.
    """
    base_title = (story.get("title") or "").strip()
    category   = story.get("category", "world")
    source     = story.get("source", "GlobalBR News")

    ai_meta = ai_meta or {}
    legacy_ai_title = (ai_meta.get("yt_title") or "").strip()
    if not base_title and 15 < len(legacy_ai_title) <= 80:
        base_title = legacy_ai_title
    if not base_title:
        base_title = "World news update"

    # Reserve room for the " #Shorts" suffix (8 chars). YouTube weighs
    # the first 50-60 chars heavily, so we cap at 88 + suffix = 96.
    SUFFIX = " #Shorts"
    cap = 100 - len(SUFFIX)
    if len(base_title) > cap:
        base_title = base_title[: cap - 1].rstrip(" .,;:—-") + "…"
    yt_title = f"{base_title}{SUFFIX}"

    # ── Description: prefer the AI-authored yt_description, which is
    # already keyword-front-loaded and capped at exactly 4 hashtags
    # (#Shorts #WorldNews #<geo> #<topic>) by fetch_news.py. Fall back
    # to synthesising one from the story we have on hand — same rule:
    # **exactly 4 hashtags**, no more (>15 = YouTube ignores all,
    # stuffing = suppression signal).
    geo_tag   = story.get("geo_hashtag") or "Global"
    topic_tag = story.get("topic_hashtag") or "Breaking"
    hashtag_block = f"#Shorts #WorldNews #{geo_tag} #{topic_tag}"

    yt_desc = (story.get("yt_description") or "").strip()
    if not yt_desc:
        lead = story.get("description") or story.get("script") or ""
        yt_desc = (
            f"{base_title}. {lead}".strip()[:380] +
            f"\n\nSource: {source}\n{hashtag_block}"
        )
    # Belt-and-braces: if the AI text already ends with hashtags, trust
    # it (fetch_news.py enforces the same 4-tag rule). Otherwise append
    # the canonical hashtag block.
    if "#Shorts" not in yt_desc:
        yt_desc = yt_desc.rstrip() + "\n" + hashtag_block
    yt_desc = yt_desc[:5000]

    # ── Tags. Queue-authored entity tags first (they're search-driven),
    # then evergreen channel tags. Cap at 15 — well under YouTube's
    # 500-char combined budget while leaving room for the long ones.
    queue_tags = [t for t in (story.get("yt_tags") or []) if isinstance(t, str)]
    legacy_extra = [t for t in (ai_meta.get("extra_tags") or []) if isinstance(t, str)]
    evergreen = [
        "shorts", "news", "breaking news", "world news",
        category.lower(), f"{category.lower()} news",
        "globalbr news", "latest news", "today news",
    ]
    seen: set[str] = set()
    all_tags: list[str] = []
    combined_len = 0
    for tag in queue_tags + legacy_extra + evergreen:
        t = tag.strip().lower().lstrip("#")
        if not t or t in seen:
            continue
        # YouTube counts: each tag, plus 1 char per separator. Stop
        # before we breach the 500-char total.
        if combined_len + len(t) + 1 > 500 or len(all_tags) >= 15:
            break
        all_tags.append(t)
        seen.add(t)
        combined_len += len(t) + 1

    return {
        "title":          yt_title,
        "description":    yt_desc,
        "tags":           all_tags,
        "category_id":    "25",      # News & Politics
        "privacy":        "public",
        "thumbnail":      str(thumb_path),
        "video":          str(video_path),
        "story_slug":     story.get("slug", ""),
        "created_at":     datetime.now(timezone.utc).isoformat(),
        "thumbnail_hook": (ai_meta.get("thumbnail_hook") or story.get("thumbnail_text", "")).strip(),
        # Fields the uploader uses for the pinned first-comment + the
        # per-region playlist. Carrying them through metadata.json keeps
        # the generate / upload contract explicit.
        "source":         source,
        "source_url":     story.get("source_url", ""),
        "geo_hashtag":    story.get("geo_hashtag", "Global"),
        "category":       category,
    }


# ── Parse posts ──────────────────────────────────────────────────
QUEUE_FILE = Path("_data/stories_queue.json")


@contextlib.contextmanager
def _queue_file_lock():
    """
    Cross-process advisory lock on the queue file. Held while we
    read-modify-write to mark a story consumed, so a concurrent
    fetch_news.py append doesn't clobber the consumed flag (or vice
    versa). Mirror of fetch_news.py::_file_lock.
    """
    if fcntl is None:
        yield
        return
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = QUEUE_FILE.with_suffix(".json.lock")
    with open(lock_path, "w") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


def _load_queue() -> dict:
    """Read _data/stories_queue.json — schema written by fetch_news.py."""
    if not QUEUE_FILE.exists():
        return {"stories": []}
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning(f"Failed to parse {QUEUE_FILE}: {exc}")
        return {"stories": []}


def _save_queue(queue: dict) -> None:
    """Atomic write — temp file + rename."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(QUEUE_FILE)


def _queue_to_story(qs: dict) -> dict:
    """
    Map a queue entry to the dict shape `generate_short()` expects.
    Falls back to source-feed metadata when the AI fields are missing.
    """
    title = qs.get("seo_title") or qs.get("title", "")
    return {
        "slug":           f'{(qs.get("published_at") or qs.get("fetched_at",""))[:10]}-{qs["id"]}',
        "title":          title,
        "description":    qs.get("lead") or qs.get("description", ""),
        "source":         qs.get("source", "GlobalBR News"),
        "source_url":     qs.get("url", ""),
        "image_url":      qs.get("image_url", ""),
        "tags":           [qs.get("category", "world")],
        "category":       qs.get("category", "world"),
        "date":           (qs.get("published_at") or qs.get("fetched_at", ""))[:10],
        "hook":           qs.get("hook", ""),
        # `script` is the full opinionated voice-over (~30-45 s) authored
        # by fetch_news.py's AI prompt. generate_short() will TTS this
        # directly instead of rebuilding from key_points.
        "script":         qs.get("script", ""),
        "thumbnail_text": qs.get("thumbnail_text", ""),
        "key_points":     qs.get("key_points", []),
        # SEO fields authored by fetch_news.py — used as-is by
        # build_short_metadata. Each is allowed to be empty; the
        # metadata builder falls back to safe defaults.
        "yt_tags":        qs.get("yt_tags", []),
        "yt_description": qs.get("yt_description", ""),
        "geo_hashtag":    qs.get("geo_hashtag", ""),
        "topic_hashtag":  qs.get("topic_hashtag", ""),
        "_queue_id":      qs["id"],  # used to mark consumed after success
    }


def load_pending_stories() -> tuple[list[dict], dict]:
    """
    Return (pending_stories, raw_queue). Pending = not yet consumed AND
    not already shipped to YouTube (`shorts_done` tracks the latter,
    handled by the caller). Stories sorted by AI quality score desc,
    breaking news first.
    """
    queue = _load_queue()
    stories = queue.get("stories", [])
    pending = [s for s in stories if not s.get("consumed")]
    pending.sort(
        key=lambda s: (
            bool(s.get("breaking", False)),
            int(s.get("score", 0) or 0),
            s.get("fetched_at", ""),
        ),
        reverse=True,
    )
    return [_queue_to_story(s) for s in pending], queue


def mark_consumed(queue: dict, queue_id: str) -> None:
    """Mutate queue: flag the matching story as consumed=true (in memory)."""
    if not queue_id:
        log.warning("mark_consumed called with empty queue_id — skipping")
        return
    for s in queue.get("stories", []):
        if s.get("id") == queue_id:
            s["consumed"] = True
            s["consumed_at"] = datetime.now(timezone.utc).isoformat()
            return
    log.warning(f"mark_consumed: story id {queue_id} not found in queue (lost?)")


def commit_consumed(queue_id: str) -> None:
    """
    Atomic read-mark-write: under the cross-process lock, reload the
    queue from disk (a concurrent fetch_news.py may have appended new
    stories since we loaded it), mark this story consumed, save.
    This is the only safe way to persist `consumed: true` when
    fetch_news.py and generate_shorts.py can interleave.
    """
    with _queue_file_lock():
        disk_queue = _load_queue()
        mark_consumed(disk_queue, queue_id)
        _save_queue(disk_queue)


# ── Gera um único Short ───────────────────────────────────────────
def generate_short(story: dict, tmp_dir: Path) -> tuple[Path, Path, dict] | None:
    """
    Generate one Short for a story.
    Returns (video_path, thumb_path, metadata) or None on failure.
    """
    # Defensive .get()s on the story dict — a queue entry with a bad
    # schema would crash the whole run otherwise.
    slug = story.get("slug") or f"unknown-{int(time.time())}"
    date_str = story.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = story.get("title") or "World news update"
    category = story.get("category", "TECH")
    description = story.get("description", "")

    log.info(f"  Generating Short for: [{category}] {title[:60]}")

    # ── 0. AI meta first — frame + thumbnail need the magnetic title ─
    # The queue (from fetch_news.py) already carries an AI-written
    # `title` (seo_title), `script` (opinion voice-over) and
    # `thumbnail_text` (2-4 word punchy overlay). Only call the
    # legacy _ai_shorts_meta as a backstop when those fields are
    # missing — saves one round-trip to Mistral per Short on the
    # happy path.
    queue_script = (story.get("script") or "").strip()
    if queue_script:
        ai_meta = {"yt_title": title}
    else:
        ai_meta = _ai_shorts_meta(title, description, category)
    ai_title = (ai_meta.get("yt_title") or "").strip()
    display_title = ai_title if 15 < len(ai_title) <= 80 else title
    if ai_title and display_title == ai_title:
        log.info(f"  ✨ Shorts AI title: {display_title}")

    # ── 1. Background image (REQUIRED) ────────────────────────────
    # We skip Shorts that can't acquire a real background. Without one
    # the auto-generated thumbnail looks like a grey placeholder on
    # YouTube — terrible CTR and indistinguishable from broken uploads.
    bg_path = tmp_dir / f"bg_{slug}.jpg"

    # Try story's own image first, then Pollinations
    if story["image_url"]:
        img_ok = download_image(story["image_url"], bg_path)
    else:
        img_ok = False

    if not img_ok:
        img_ok = generate_ai_background(title, category, bg_path)

    # Hard requirement: skip Shorts without a usable background image.
    if not img_ok or not bg_path.exists() or bg_path.stat().st_size < 5 * 1024:
        log.warning(
            "  ⏭  Skipping Short — no valid background image (story image and "
            "Pollinations fallback both failed): %s", title[:80],
        )
        return None

    bg_path_final = bg_path

    # ── 2. Extract key points ─────────────────────────────────────
    points = extract_key_points(story["description"])

    # ── 3. Build frame image ──────────────────────────────────────
    # display_title is the magnetic AI title (or original headline as
    # fallback). The frame doubles as the thumbnail source, so this
    # is the single biggest CTR lever for Shorts.
    frame = create_short_frame(
        title=display_title,
        category=category,
        points=points,
        source=story["source"],
        bg_path=bg_path_final,
    )
    frame_path = tmp_dir / f"frame_{slug}.png"
    frame.save(str(frame_path))
    log.info(f"  Frame saved: {frame_path.name}")

    # ── 4. TTS narration ──────────────────────────────────────────
    # Prefer the queue's `script` (full opinionated voice-over from
    # fetch_news.py's AI prompt). Fall back to the legacy template
    # builder if the queue field is empty (e.g. backlog stories
    # written before the script field existed).
    if queue_script:
        raw_script = queue_script
        log.info(f"  ✨ Using AI opinion script from queue ({len(raw_script)} chars)")
    else:
        raw_script = build_short_script(title, points, category)
    script = humanize_for_tts(raw_script)
    audio_path = tmp_dir / f"audio_{slug}.mp3"
    try:
        asyncio.run(text_to_speech(script, audio_path, VOICE_SHORT))
        size_kb = audio_path.stat().st_size / 1024
        log.info(f"  TTS generated ({size_kb:.0f} KB)")
    except Exception as e:
        log.error(f"  TTS failed: {e}")
        return None

    # ── 5. Check duration ─────────────────────────────────────────
    res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True,
    )
    try:
        duration = float(res.stdout.strip())
    except Exception:
        duration = 50.0

    if duration > 60.0:
        log.warning(f"  Script too long ({duration:.1f}s) — will be trimmed by FFmpeg")

    # ── 6. Output paths ───────────────────────────────────────────
    VIDEOS_DIR.mkdir(exist_ok=True)
    video_path = VIDEOS_DIR / f"short-{slug}-{date_str}.mp4"
    thumb_path = VIDEOS_DIR / f"short-{slug}-{date_str}_thumb.jpg"

    # ── 7. Thumbnail ──────────────────────────────────────────────
    create_short_thumbnail(frame, thumb_path)
    # YouTube refuses thumbnails < 2KB and won't show meaningful content
    # for greyscale/empty frames. If the generated frame ended up too
    # small (background failed and renderer produced a tiny image), bail.
    if not thumb_path.exists() or thumb_path.stat().st_size < 5 * 1024:
        log.warning(
            "  ⏭  Skipping Short — thumbnail too small to be visually useful: %s",
            title[:80],
        )
        return None

    # ── 8. FFmpeg: combine image + audio → video ──────────────────
    ok = create_short_video(frame_path, audio_path, video_path)
    if not ok:
        return None

    # ── 9. Metadata JSON ──────────────────────────────────────────
    metadata = build_short_metadata(story, video_path, thumb_path, ai_meta=ai_meta)
    meta_path = video_path.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    log.info(f"  Metadata saved: {meta_path.name}")

    return video_path, thumb_path, metadata


# ── Principal ────────────────────────────────────────────────────
def main():
    # Fail-fast startup validation. _ai_shorts_meta (the legacy backstop)
    # still calls Mistral, and Pollinations doesn't need auth, but the
    # queue's AI-authored script is what makes a Short worth shipping —
    # missing key would mean degrading silently to the legacy path.
    if not os.environ.get("MISTRAL_API_KEY"):
        log.warning(
            "⚠ MISTRAL_API_KEY is not set. Shorts will fall back to "
            "the legacy template-script renderer and may look generic."
        )

    VIDEOS_DIR.mkdir(exist_ok=True)

    if not QUEUE_FILE.exists():
        log.error(f"{QUEUE_FILE} not found — run fetch_news.py first.")
        sys.exit(2)

    shorts_done = load_shorts_done()
    log.info(f"Shorts already done: {len(shorts_done)}")

    candidates, queue = load_pending_stories()
    # Belt-and-braces: queue dedup already excludes consumed stories,
    # but shorts_done covers the case where a story was published to
    # YouTube but the workflow died before marking it consumed.
    candidates = [c for c in candidates if c["slug"] not in shorts_done]

    log.info(f"Queue has {len(candidates)} pending stor{'y' if len(candidates)==1 else 'ies'}.")
    if not candidates:
        log.info("Nothing to do.")
        return

    selected = candidates[:MAX_SHORTS_PER_RUN]
    log.info(f"Creating {len(selected)} Short(s) this run:")
    for i, s in enumerate(selected, 1):
        log.info(f"  {i}. [{s['category']}] {s['title'][:70]}")

    tmp = Path(f"/tmp/yt_shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    tmp.mkdir(exist_ok=True)

    created = 0
    for story in selected:
        result = generate_short(story, tmp)
        if result:
            video_path, thumb_path, metadata = result
            shorts_done.add(story["slug"])
            save_shorts_done(shorts_done)
            # Persist consumption back to the queue under the
            # cross-process lock so a concurrent fetch_news.py append
            # can't undo it. We pass through commit_consumed() instead
            # of the bare _save_queue(queue) — that one would write our
            # stale in-memory copy and overwrite any fetch_news flush.
            commit_consumed(story.get("_queue_id", ""))
            created += 1
            log.info(f"  Short ready: {video_path.name}")
            log.info(f"  YT title: {metadata['title'][:80]}")
        else:
            log.error(f"  Failed to generate Short for: {story.get('slug', '?')}")

    shutil.rmtree(tmp, ignore_errors=True)
    log.info(f"\nDone: {created}/{len(selected)} Short(s) created in {VIDEOS_DIR}/")

    # Observable failure signal: if we were asked to make Shorts and
    # produced zero, exit non-zero so the workflow turns red. Beats
    # "✅ success" on a day where no Short actually shipped.
    if selected and created == 0:
        log.error("❌ All Short generations failed. Exiting non-zero.")
        sys.exit(1)


if __name__ == "__main__":
    main()
