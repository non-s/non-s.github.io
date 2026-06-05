#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_shorts.py — Gera videos verticais curtos para o YouTube Shorts
================================================================================
Formato: vídeo vertical 1080x1920, 25-35 segundos, uma história por vídeo.
Máximo 3 vídeos por execução para respeitar limites de API.

Estrutura de cada video (YouTube Shorts):
  Hook        ~3s    Surprising fact, starts immediately
  Fato 1     ~8s    Primeira surpresa
  Fato 2     ~8s    Segunda surpresa
  Fato 3     ~8s    Terceira surpresa (opcional)
  CTA         ~2s    "Subscribe for more animal facts."

Total alvo: ~25-35 segundos. YouTube Shorts premia completion rate
muito mais que duração — videos de 30s com 85% completion batem
videos de 55s com 50% completion. We clip at 35s hard.
"""

import os, re, json, asyncio, subprocess, logging, shutil, sys, time, contextlib
from pathlib import Path
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

# fcntl is POSIX-only; we use it to serialise queue access against
# fetch_animals.py. Guarded for local Windows dev — the CI runner is Linux.
try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from utils.broll import BrollClip, download_clip, fetch_broll_clips
from utils.animal_enrichment import download_commons_image
from utils.captions import (
    group_words_into_phrases,
    transcribe as captions_transcribe,
    write_ass,
)
from utils.digest import load_blocked_slugs
from utils.editorial import rank_candidates, review as editorial_review
from utils.experiments import assign_all_for_production, assign_variant
from utils.growth_strategy import rank_for_growth
from utils.human_voice import score_text as score_human_voice
from utils.host_persona import load as load_persona
from utils.intro_outro import wrap_with_intro_outro
from utils.music_bed import add_music_bed
from utils.script_quality import evaluate as evaluate_script, should_block as quality_should_block
from utils.story_intelligence import audit_hook, audit_title, classify_format
from utils.text import humanize_for_tts
from utils.translation import SUPPORTED_LANGUAGES, translate_story
from utils.video_compose import build_broll_short, build_static_short
from utils.visual_qa import evaluate_frame

# ── Config ────────────────────────────────────────────────────────
# Language axis. "en" is the default channel; setting LANGUAGE=pt-BR
# (or es-ES, es-MX, fr-FR) flips this run into the sibling-channel
# pipeline:
#   • every story passes through utils.translation.translate_story
#   • outputs land in `_videos_<lang>/` to avoid colliding with English
#   • shorts_done bookkeeping is per-language
# All of the rest of the rendering (b-roll, captions, thumbnail) is
# language-agnostic — only the script and metadata change.
LANGUAGE = os.environ.get("LANGUAGE", "en").strip() or "en"
if LANGUAGE != "en" and LANGUAGE not in SUPPORTED_LANGUAGES:
    raise RuntimeError(
        f"LANGUAGE={LANGUAGE!r} is not supported. "
        f"Pick one of: en, {', '.join(SUPPORTED_LANGUAGES)}"
    )

VIDEOS_DIR      = Path("_videos") if LANGUAGE == "en" else Path(f"_videos_{LANGUAGE}")
SHORTS_DONE_FILE = VIDEOS_DIR / "shorts_done.json"
LOG_FILE        = f"generate_shorts{'' if LANGUAGE == 'en' else '_' + LANGUAGE}.log"
# Cap of shorts produced per run. Overridable via env var so the
# workflow can tune it without editing this file. Defaults to 3 —
# matches youtube-bot.yml schedule.
MAX_SHORTS_PER_RUN = int(os.environ.get("MAX_SHORTS_PER_RUN", "3"))
SHORT_W, SHORT_H = 1080, 1920  # vertical 9:16


def _env_enabled(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


QUALITY_REQUIRE_MOTION_BROLL = _env_enabled("QUALITY_REQUIRE_MOTION_BROLL")
QUALITY_REQUIRE_CAPTIONS = _env_enabled("QUALITY_REQUIRE_CAPTIONS")
QUALITY_MIN_VISUAL_QA_SCORE = int(os.environ.get("QUALITY_MIN_VISUAL_QA_SCORE", "1"))

# Paleta de cores — identidade Wild Brief
BG_DARK      = (8, 8, 18)
ACCENT_BLUE  = (0, 195, 255)
ACCENT_CYAN  = (0, 240, 200)
RED_LIVE     = (220, 50, 50)
TEXT_WHITE   = (245, 245, 255)
TEXT_GRAY    = (160, 165, 190)

# Cores por categoria
CATEGORY_COLORS = {
    # Wild Brief animal categories.
    "CATS":        (255, 140, 90),   # warm orange (tabby tone)
    "DOGS":        (255, 195, 90),   # golden retriever yellow
    "OCEAN":       (0, 140, 220),    # deep marine blue
    "WILDLIFE":    (180, 130, 60),   # savanna ochre
    "BIRDS":       (90, 200, 255),   # sky blue
    "FARM":        (140, 180, 90),   # field green
    # Generic animal fallback — used when a queue entry slips through
    # without a recognised category, so the gradient renders something
    # warm and on-brand instead of a default blue.
    "ANIMAL":      (200, 150, 90),
    "ANIMALS":     (200, 150, 90),
}

ANIMAL_BROLL_QUERIES = {
    "CATS": "cat animal",
    "DOGS": "dog animal",
    "OCEAN": "marine animal underwater",
    "WILDLIFE": "wild animal nature",
    "BIRDS": "bird animal",
    "FARM": "farm animal",
}

# ── TTS voice rotation ────────────────────────────────────────────
#
# Channel grew on Jenny's voice originally, but a single voice across
# every Short flattens audience appetite. Shorts viewers notice when
# consecutive videos sound identical and skip the second
# (the "session homogeneity" signal). Rotating between a small panel
# of high-quality edge-tts voices keeps things fresh without dropping
# the channel's recognisable animal-facts tone.
#
# We pick the voice deterministically from the story's title hash so a
# given story always renders with the same voice (idempotent reruns)
# and there's roughly-even distribution across the panel.
# SIGNATURE VOICE — committed to a single host identity.
#
# The audit data is clear: automated channels that monetize have ONE
# recognizable voice. Six-voice rotation reads as randomness, not
# editorial choice. The Wild Brief narrator (configurable via
# host_persona) now speaks in en-US-AriaNeural — crisp delivery that
# doesn't fatigue across daily listening.
#
# The second voice (Guy) is the contingency: when Aria's edge-tts
# CDN blips on a particular Short, Guy takes over for that one
# render. Listeners on the channel hear Aria 99 % of the time.
HOST_VOICE_PRIMARY   = "en-US-AriaNeural"
HOST_VOICE_BACKUP    = "en-US-GuyNeural"
HOST_VOICE_VARIANTS = {
    "aria": HOST_VOICE_PRIMARY,
    "jenny": "en-US-JennyNeural",
    "guy": HOST_VOICE_BACKUP,
}

VOICE_PANEL = [HOST_VOICE_PRIMARY, "en-US-JennyNeural", HOST_VOICE_BACKUP]
# Backwards-compat alias — kept for any caller still importing it.
VOICE_SHORT = HOST_VOICE_PRIMARY

# Per-locale signature voices. Each locale picks ONE host voice +
# ONE backup, matching the English channel's "one recognizable
# host" commitment.
VOICE_PANEL_BY_LOCALE: dict[str, list[str]] = {
    "en":    VOICE_PANEL,
    "pt-BR": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"],
    "es-ES": ["es-ES-ElviraNeural",    "es-ES-AlvaroNeural"],
    "es-MX": ["es-MX-DaliaNeural",     "es-MX-JorgeNeural"],
    "fr-FR": ["fr-FR-DeniseNeural",    "fr-FR-HenriNeural"],
}


def pick_voice(seed_text: str, category: str = "",
                voice_tag: str = "") -> str:
    """Pick the host's signature voice for this Short.

    With the post-May-2026 humanization shift, the channel is committed
    to a SINGLE recognizable host voice per locale. We return the
    primary voice for the chosen locale on every call — `seed_text`
    and `category` are kept in the signature for API compatibility
    with the older rotation logic but are no longer used to scatter
    voices.

    The backup voice (index 1 of the panel) is reserved for the case
    where the primary voice's edge-tts CDN errors on a particular
    render — caller handles that fallback explicitly via VOICE_SHORT.
    """
    voice_tag = (voice_tag or "").strip()
    panel = VOICE_PANEL_BY_LOCALE.get(
        voice_tag if voice_tag and voice_tag != "en" else "en",
        VOICE_PANEL,
    )
    if not voice_tag or voice_tag == "en":
        variant = assign_variant("narrator_voice", seed_text or category or "wildbrief")
        return HOST_VOICE_VARIANTS.get(variant, HOST_VOICE_PRIMARY)
    return panel[0] if panel else HOST_VOICE_PRIMARY


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


# ── TTS ───────────────────────────────────────────────────────────
TTS_TIMEOUT_S = float(os.environ.get("TTS_TIMEOUT_S", "45"))


# Per-voice TTS rate. edge-tts voices have noticeably different
# baseline tempos: British voices read slower (Sonia/Ryan), Brazilian
# Portuguese voices faster than US English. A single global +3% nudge
# (the old default) made Sonia sound stately and Antonio panicked.
# These offsets are tuned by ear to land each voice in the 30-45s
# range for a 100-word script. Missing entries fall through to +3%.
VOICE_RATE_OFFSETS = {
    # English
    "en-US-JennyNeural":     "+3%",   # baseline
    "en-US-AriaNeural":      "+4%",
    "en-US-GuyNeural":       "+2%",
    "en-GB-SoniaNeural":     "+6%",   # British — naturally slower
    "en-GB-RyanNeural":      "+6%",
    "en-AU-NatashaNeural":   "+3%",
    # Portuguese (Brazil) — already brisk; we slow down slightly
    "pt-BR-FranciscaNeural": "+0%",
    "pt-BR-AntonioNeural":   "-2%",   # the calmest of the three
    "pt-BR-ThalitaNeural":   "+0%",
    # Spanish + French
    "es-ES-ElviraNeural":    "+2%",
    "es-ES-AlvaroNeural":    "+2%",
    "es-MX-DaliaNeural":     "+2%",
    "es-MX-JorgeNeural":     "+2%",
    "fr-FR-DeniseNeural":    "+4%",
    "fr-FR-HenriNeural":     "+4%",
}


async def text_to_speech(text: str, output_path: Path, voice: str = VOICE_SHORT,
                          rate_override: str | None = None):
    """
    Render `text` to `output_path` (MP3) via Microsoft Edge-TTS.

    Wrapped in asyncio.wait_for so a hung WebSocket can't pin the whole
    Short generation. The previous version (no timeout) would silently
    hang for up to the workflow's full 30-min budget if edge-tts's CDN
    blipped — that meant zero Shorts shipped that day. We raise on
    timeout so the caller logs the failure and moves on to the next
    story.

    Each voice gets its own rate offset (see VOICE_RATE_OFFSETS) — a
    single global nudge made British voices sound stately and Brazilian
    voices panicked. `rate_override` lets the caller (the hook-slow
    path) inject a specific rate without rebuilding the panel.
    """
    import edge_tts
    rate = rate_override or VOICE_RATE_OFFSETS.get(voice, "+3%")
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch="+0Hz")
    await asyncio.wait_for(
        communicate.save(str(output_path)),
        timeout=TTS_TIMEOUT_S,
    )


async def text_to_speech_hook_then_body(hook: str, body: str,
                                          output_path: Path,
                                          voice: str = VOICE_SHORT,
                                          tmp_dir: Path | None = None) -> bool:
    """Render the hook at the voice's "calm" baseline rate (4 % slower
    than the body), then the body at the voice's regular rate. The
    two MP3 segments are FFmpeg-concatenated into `output_path`.

    Why: the first 3 s decide whether a viewer swipes or stays. A
    rushed hook is the single biggest "swiped before they understood"
    failure mode. Reading the hook ~4 % slower than the body gives
    viewers time to comprehend the lead without making the whole
    Short feel slow.

    Returns True on success. False = caller should fall back to the
    one-shot text_to_speech with the full script.
    """
    if not hook or not body or not tmp_dir:
        return False
    body_rate = VOICE_RATE_OFFSETS.get(voice, "+3%")
    # Compute a "calm" rate ~4 percentage points below body_rate.
    try:
        body_pp = int(body_rate.rstrip("%"))
    except ValueError:
        body_pp = 3
    hook_pp = body_pp - 4
    hook_rate = f"{hook_pp:+d}%" if hook_pp != 0 else "+0%"

    hook_mp3 = tmp_dir / "_hook.mp3"
    body_mp3 = tmp_dir / "_body.mp3"
    try:
        await text_to_speech(hook, hook_mp3, voice, rate_override=hook_rate)
        await text_to_speech(body, body_mp3, voice, rate_override=body_rate)
    except Exception as exc:
        log.warning("hook/body TTS split failed: %s", exc)
        return False
    if not (hook_mp3.exists() and body_mp3.exists()):
        return False
    # Concat with FFmpeg's concat demuxer (lossless for MP3).
    list_file = tmp_dir / "_concat.txt"
    list_file.write_text(
        f"file '{hook_mp3.resolve()}'\nfile '{body_mp3.resolve()}'\n",
        encoding="utf-8",
    )
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(output_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False
    if r.returncode != 0:
        log.warning("hook/body MP3 concat failed: %s",
                     r.stderr[-200:].decode("utf-8", errors="replace"))
        return False
    log.info("  🎤 Hook @ %s, body @ %s (split-rate)", hook_rate, body_rate)
    return True


# ── Legacy AI metadata + script builders removed ─────────────────
#
# `_ai_shorts_meta`, `_ai_shorts_hook`, and `build_short_script` used
# to round-trip Mistral for title/hook/script generation, but every
# pending story in the queue is now pre-enriched by fetch_animals.py with
# `seo_title`, `hook`, `script`, `thumbnail_text`, `yt_tags`, etc.
# Keeping the legacy paths would burn extra free-tier tokens and create
# divergent metadata between the queue and the upload sidecar. Removed
# May 2026 as part of the b-roll + captions pivot.


def _render_solid_color_background(category: str, dest: Path) -> bool:
    """Synthesise a category-coloured vertical gradient as the
    background-of-last-resort. The b-roll path is the actual visual
    content; this just backs the thumbnail and the static-frame
    compose when every image source above failed.

    Returns True iff the file was written and is larger than the 5KB
    sanity floor downstream checks. Single-file PIL draw — no network,
    no external command, so this never fails except on totally broken
    Python installs (in which case the whole pipeline is dead anyway).
    """
    base = CATEGORY_COLORS.get((category or "").upper(), ACCENT_BLUE)
    bg = Image.new("RGB", (SHORT_W, SHORT_H), (12, 14, 22))
    draw = ImageDraw.Draw(bg)
    # Linear gradient: dark navy at top → category color at bottom.
    # Keeps the title-card text band readable while signalling the
    # topic visually. One horizontal line per row is ~2000× faster
    # than a per-pixel loop and finishes in ~30 ms at 1080×1920.
    for y in range(SHORT_H):
        t = y / max(1, SHORT_H - 1)
        r = int(12 * (1 - t) + base[0] * t * 0.45)
        g = int(14 * (1 - t) + base[1] * t * 0.45)
        b = int(22 * (1 - t) + base[2] * t * 0.45)
        draw.line([(0, y), (SHORT_W, y)], fill=(r, g, b))
    bg.save(str(dest), "JPEG", quality=88, optimize=True)
    return dest.exists() and dest.stat().st_size > 5 * 1024


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
      - Wild Brief branding (bottom ~85-95%)
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
    live_text = "ANIMAL FACT"
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

    # Logo text — channel name lockup on the title card.
    logo_font = get_font(54, bold=True)
    brand_y2 = brand_y + 24
    draw.text((padding, brand_y2), "WILD", font=logo_font, fill=ACCENT_BLUE)
    gbbox = draw.textbbox((0, 0), "WILD", font=logo_font)
    sep_x = padding + gbbox[2] + 12
    draw.rectangle([(sep_x, brand_y2 + 4), (sep_x + 4, brand_y2 + gbbox[3] - 4)],
                   fill=(*ACCENT_BLUE, 180))
    draw.text((sep_x + 16, brand_y2), "BRIEF", font=logo_font, fill=TEXT_WHITE)

    # Source
    src_font = get_font(36)
    src_y = brand_y2 + 68
    draw.text((padding, src_y), f"Source: {source}", font=src_font, fill=TEXT_GRAY)

    # CTA
    cta_font = get_font(38, bold=True)
    cta_text = "SUBSCRIBE FOR MORE ANIMAL FACTS"
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


# ── Thumbnail do Short (dynamic per-story) ────────────────────────
#
# Previously every Short shipped with the same brand-grid JPEG. The
# "Inauthentic Content" policy + CTR research both push the other way:
# a thumbnail that names WHAT the story is about wins clicks at the
# moment the viewer is browsing the Shorts feed search page. We now
# render the thumbnail per-Short with the AI-generated `thumbnail_text`
# Per-operator decision (2026-05-19): every Short ships with the same
# branded vertical thumbnail (`wildbrief_short_thumb.png`) as a
# placeholder. The operator overrides each Short's thumb manually via
# YouTube Studio for the ones that earn a bespoke design. This is
# cleaner than auto-generating a per-Short title-card thumb because:
#   * Every channel preview tile looks instantly recognisable as Wild
#     Brief — branding consistency at the highest-impact surface.
#   * The dynamic AI-text overlay path was visually inconsistent.
#   * Frame-from-video extracts looked random / weak.
SHIPPED_THUMB_PATH = Path(__file__).parent / "scripts" / "assets" / "wildbrief_short_thumb.png"
# Legacy alias retained because tests / older comments referenced it.
STATIC_THUMB_PATH = SHIPPED_THUMB_PATH


def _create_static_short_thumbnail(frame_img: Image.Image, output: Path,
                                   thumbnail_text: str = "",
                                   category: str = "") -> None:
    """
    Write the per-Short thumbnail.

    Current policy: every Short ships with the SAME branded vertical
    placeholder (`wildbrief_short_thumb.png`). YouTube can generate a
    cover from the video itself, but we still emit a JPEG so the
    `.done` sidecar carries one for downstream dashboards / future
    cross-posting. `thumbnail_text` and `category` are kept in the
    signature so older callers still type-check; they're ignored.

    Fallback chain:
      1. Copy the branded placeholder (the normal case).
      2. If that file is missing, save the title-card frame as JPEG.
      3. If even that fails (no PIL image passed), bail silently — the
         uploader treats a missing thumbnail as non-fatal.
    """
    if SHIPPED_THUMB_PATH.exists():
        try:
            thumb = Image.open(SHIPPED_THUMB_PATH).convert("RGB")
            thumb.save(str(output), "JPEG", quality=90, optimize=True)
            log.info("  🖼  Thumbnail (branded Wild Brief): %s", output.name)
            return
        except Exception as exc:
            log.warning(
                "  ⚠ Failed to load branded thumb at %s: %s — falling back.",
                SHIPPED_THUMB_PATH, exc,
            )

    # Fallback: title-card frame as a JPEG (never branded but never empty).
    if frame_img is not None:
        thumb = frame_img.copy().convert("RGB")
        thumb.save(str(output), "JPEG", quality=92, optimize=True)
        log.info("  Thumbnail (title-card fallback): %s", output.name)


# ── Video assembly (b-roll + captions + hook overlay) ────────────
#
# The composition itself moved to utils/video_compose.py so the two
# render paths (multi-clip motion or static-frame fallback) can be
# unit-tested in isolation. This wrapper is what `generate_short()`
# calls; it picks the right pipeline based on whether we actually
# acquired b-roll clips.

def _thumbnail_copy(thumbnail_text: str, fallback: str = "ANIMAL FACT") -> str:
    """Return compact, readable thumbnail copy for a vertical preview tile."""
    cleaned = re.sub(r"[^A-Za-z0-9 '&-]+", " ", thumbnail_text or "")
    words = [word for word in cleaned.upper().split() if word]
    return " ".join(words[:4]) or fallback


def create_short_thumbnail(frame_img: Image.Image, output: Path,
                            thumbnail_text: str = "",
                            category: str = "") -> None:
    """Render a story-specific vertical preview with one instant idea."""
    if frame_img is None:
        return
    thumb = frame_img.copy().convert("RGB").resize((SHORT_W, SHORT_H), Image.LANCZOS)
    draw = ImageDraw.Draw(thumb, "RGBA")
    cat_color = CATEGORY_COLORS.get((category or "").upper(), ACCENT_BLUE)

    # Keep the animal visible, then create a clean mobile-readable text band.
    draw.rectangle((0, 0, SHORT_W, SHORT_H), fill=(0, 0, 0, 82))
    draw.rectangle((0, 420, SHORT_W, 1450), fill=(0, 0, 0, 132))
    draw.rectangle((0, 1440, SHORT_W, SHORT_H), fill=(0, 0, 0, 178))
    draw.rectangle((0, 0, 22, SHORT_H), fill=(*cat_color, 255))

    cat_text = (category or "animals").upper()[:18]
    cat_font = get_font(42, bold=True)
    cat_box = draw.textbbox((0, 0), cat_text, font=cat_font)
    pill = (76, 110, 76 + cat_box[2] + 46, 110 + cat_box[3] + 28)
    draw_rounded_rect(draw, pill, radius=12, fill=(*cat_color, 245))
    draw.text((pill[0] + 23, pill[1] + 14), cat_text,
              font=cat_font, fill=(0, 0, 0, 255))

    copy = _thumbnail_copy(thumbnail_text)
    title_font = get_font(156, bold=True)
    lines = wrap_text(draw, copy, title_font, SHORT_W - 154)
    if len(lines) > 3:
        title_font = get_font(132, bold=True)
        lines = wrap_text(draw, copy, title_font, SHORT_W - 154)
    lines = lines[:3]
    line_h = 176 if len(lines) <= 2 else 150
    y = 730 - (len(lines) * line_h // 2)
    for line in lines:
        box = draw.textbbox((0, 0), line, font=title_font)
        x = (SHORT_W - box[2]) // 2
        draw.text((x + 7, y + 8), line, font=title_font,
                  fill=(0, 0, 0, 230))
        draw.text((x, y), line, font=title_font,
                  fill=(*TEXT_WHITE, 255))
        y += line_h

    draw.rectangle((76, 1440, 310, 1454), fill=(*cat_color, 255))
    brand_font = get_font(62, bold=True)
    draw.text((76, 1502), "WILD BRIEF", font=brand_font,
              fill=(*TEXT_WHITE, 255))
    sub_font = get_font(38, bold=True)
    draw.text((76, 1582), "ANIMAL FACTS", font=sub_font,
              fill=(*cat_color, 255))

    thumb.save(str(output), "JPEG", quality=94, optimize=True)
    log.info("  Thumbnail (dynamic story preview): %s", output.name)


def _animal_broll_query(story: dict) -> str:
    """Build a conservative visual query for an animal-only channel."""
    category = str(story.get("category", "")).strip().upper()
    category_query = ANIMAL_BROLL_QUERIES.get(category, "animal wildlife")
    tags = story.get("yt_tags") or []
    if isinstance(tags, str):
        tags = [tags]
    for tag in tags:
        clean = re.sub(r"[^A-Za-z -]", "", str(tag)).strip().lower()
        if clean and len(clean.split()) <= 3:
            return f"{clean} {category_query}"[:120]
    return category_query


def _extract_broll_thumbnail(video_path: Path, dest: Path) -> bool:
    """Extract a still from the actual animal footage for the thumbnail."""
    try:
        result = subprocess.run([
            "ffmpeg", "-y", "-ss", "0.5", "-i", str(video_path),
            "-frames:v", "1", "-q:v", "2", str(dest),
        ], capture_output=True, timeout=30)
        return (
            result.returncode == 0
            and dest.exists()
            and dest.stat().st_size >= 5 * 1024
        )
    except Exception as exc:
        log.debug("broll thumbnail extraction failed: %s", exc)
        return False


def acquire_broll_clips(story: dict, tmp_dir: Path,
                         want_n: int = 3) -> list[Path]:
    """
    Pull `want_n` b-roll MP4s into `tmp_dir`. Returns local paths.
    Empty list = the caller falls back to a static frame.

    The primary clip is the exact source clip stored with the story.
    Supplemental discovery is conservative: animal queries only.
    """
    if want_n <= 0:
        return []
    query = _animal_broll_query(story)
    if not query:
        return []
    category = story.get("category", "")
    try:
        candidates = fetch_broll_clips(
            query,
            want_n=want_n * 2,
            category=category,
            animal_only=True,
        )
    except Exception as exc:
        log.debug("broll discovery failed: %s", exc)
        return []
    log.info("  🎬 B-roll candidates: %d (query=%r)", len(candidates), query[:80])

    preferred_url = (story.get("source_download_url") or story.get("pexels_download_url") or "").strip()
    if preferred_url:
        candidates.insert(0, BrollClip(
            source=(story.get("source") or "pexels").strip().lower(),
            url=(story.get("source_url") or "").strip(),
            download_url=preferred_url,
            width=1080,
            height=1920,
            duration_s=10.0,
            title=(story.get("title") or "").strip(),
            license=(story.get("source_license") or "Reusable source clip").strip(),
        ))

    paths: list[Path] = []
    seen_urls: set[str] = set()
    for i, clip in enumerate(candidates):
        if len(paths) >= want_n:
            break
        if clip.download_url in seen_urls:
            continue
        seen_urls.add(clip.download_url)
        dest = tmp_dir / f"broll_{i}.mp4"
        if download_clip(clip, dest):
            paths.append(dest)
    log.info("  🎬 B-roll downloaded: %d/%d (sources: %s)",
             len(paths), want_n,
             {c.source for c in candidates[:len(paths)]})
    return paths


def generate_captions(audio_path: Path, tmp_dir: Path) -> Path | None:
    """Transcribe `audio_path` and emit an ASS subtitle file. None if both
    Whisper providers fail; callers should still ship the Short."""
    try:
        words = captions_transcribe(audio_path)
    except Exception as exc:
        log.warning("caption transcribe crashed: %s", exc)
        return None
    if not words:
        return None
    phrases = group_words_into_phrases(words, max_words=4, max_gap_s=0.6)
    ass_path = tmp_dir / "captions.ass"
    if not write_ass(phrases, ass_path):
        return None
    return ass_path


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


# ── Metadata for upload_youtube.py ───────────────────────────────
def build_short_metadata(story: dict, video_path: Path,
                         thumb_path: Path) -> dict:
    """
    Build the JSON metadata payload that upload_youtube.py consumes.
    Required keys downstream: title, description, video.

    SEO inputs (already authored by fetch_animals.py's prompt and carried
    on the queue entry):

      story["title"]          — seo_title, 40-55 chars, front-loaded
      story["yt_tags"]        — 5 lowercase tags (kept name for queue
                                schema back-compat; we render them inline
                                as hashtags below)
      story["yt_description"] — 2-3 sentences ending with hashtag block

    YouTube limits we respect:
      - title: 100 characters
      - description: 5,000 characters
      - tags: a focused list for YouTube search and Shorts discovery
    """
    base_title = (story.get("title") or "").strip()
    category   = story.get("category", "wildlife")
    source     = story.get("source", "Pexels")

    if not base_title:
        base_title = "Animal fact of the day"

    if len(base_title) > 100:
        base_title = base_title[:97].rstrip(" .,;:-") + "..."

    # ── YouTube Shorts hashtag block.
    # Keep the block focused: YouTube primarily needs #Shorts plus a
    # small set of topic tags.
    discovery = list(story.get("discovery_hashtags") or [])
    if not discovery:
        # Fallback for queue entries written before discovery_hashtags
        # landed: synthesise a reasonable set from category + topic.
        cat = (category or "animals").lower()
        topic_tag = (story.get("topic_hashtag") or category or "animals").lower()
        topic_tag = "".join(ch for ch in topic_tag if ch.isalnum())
        discovery = [cat, topic_tag, "animals", "wildlife", "funfacts"]
    discovery = ["Shorts", "AnimalFacts", "Wildlife"] + discovery
    # Dedupe while preserving order; cap at 5.
    seen_h: set[str] = set()
    final_tags: list[str] = []
    for tag in discovery:
        t = str(tag).strip().lstrip("#")
        t = "".join(ch for ch in t if ch.isalnum())
        if not t or t.lower() in seen_h:
            continue
        final_tags.append(t)
        seen_h.add(t.lower())
        if len(final_tags) >= 5:
            break
    hashtag_block = " ".join(f"#{t}" for t in final_tags)

    raw_desc = (story.get("yt_description") or "").strip()
    # Rebuild the hashtag line to avoid carrying stale queue tags.
    cleaned = []
    for line in raw_desc.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and all(p.startswith("#") for p in stripped.split()):
            continue  # drop pure hashtag lines authored for YouTube
        cleaned.append(line)
    body = "\n".join(cleaned).rstrip()
    if not body:
        lead = story.get("description") or story.get("script") or ""
        body = f"{base_title}. {lead}".strip()[:380] + f"\n\nSource: {source}"

    caption = f"{body}\n\n{hashtag_block}"[:5000]

    # Tag list kept for analytics back-compat (the digest + dashboard
    # both read `meta['tags']`).
    queue_tags = [t for t in (story.get("yt_tags") or []) if isinstance(t, str)]
    evergreen = [
        "youtube shorts", "shorts", "animals", "animal facts", "wildlife", "nature",
        category.lower(), f"{category.lower()} facts",
        "wild brief", "cute animals", "did you know",
    ]
    seen: set[str] = set()
    all_tags: list[str] = []
    for tag in queue_tags + evergreen:
        t = tag.strip().lower().lstrip("#")
        if not t or t in seen:
            continue
        all_tags.append(t)
        seen.add(t)
        if len(all_tags) >= 15:
            break

    return {
        "title":          base_title,
        "description":    caption,
        "tags":           all_tags,
        "youtube_privacy": "public",
        "youtube_category_id": "15",
        "thumbnail":      str(thumb_path),
        "video":          str(video_path),
        "story_slug":     story.get("slug", ""),
        "created_at":     datetime.now(timezone.utc).isoformat(),
        "thumbnail_hook": story.get("thumbnail_text", "").strip(),
        "hook":           story.get("hook", "").strip(),
        "story_format":   story.get("story_format") or classify_format(
            f"{base_title} {story.get('hook', '')} {story.get('script', '')}"
        ),
        "hook_audit":     audit_hook(story.get("hook", "")).to_dict(),
        "title_audit":    audit_title(base_title).to_dict(),
        "human_voice":    score_human_voice(story.get("script", "")).to_dict(),
        "narrator_voice": story.get("narrator_voice", ""),
        # Vertical 9:16 + short duration = a YouTube Short.
        "is_short":       True,
        # Pexels source-clip identity. Propagated so upload_youtube can
        # append it to the permanent dedup ledger
        # (`_data/published_clips.json`) on a successful upload.
        "pexels_video_id":     story.get("pexels_video_id", ""),
        "pexels_download_url": story.get("pexels_download_url", ""),
        "source_clip_id":      story.get("source_clip_id", ""),
        "source_download_url": story.get("source_download_url", ""),
        "source_license":      story.get("source_license", ""),
        "commons_page_url":    story.get("commons_page_url", ""),
        "commons_license":     story.get("commons_license", ""),
        "commons_artist":      story.get("commons_artist", ""),
        "gbif":                dict(story.get("gbif") or {}),
        # Queue entry id (sha1 of the Pexels page URL). Second dedup
        # key after pexels_video_id; whichever the recorder has is fine.
        "story_id":            story.get("id", ""),
        # Source metadata (kept for analytics / dashboard).
        "source":         source,
        "source_url":     story.get("source_url", ""),
        "geo_hashtag":    story.get("geo_hashtag", "Global"),
        "category":       category,
        # channel_handle is kept on the metadata for the .done sidecar /
        # analytics joins even when the on-frame watermark is disabled.
        "channel_handle": (os.environ.get("CHANNEL_WATERMARK", "").strip()
                           or "@wildbrief"),
        # A/B variant tags ride along all the way to the .done sidecar
        # after upload so analytics can correlate them with engagement.
        "experiments":    dict(story.get("experiments") or {}),
        "editorial":      dict(story.get("editorial") or {}),
        "series":         story.get("series", ""),
    }


# ── Parse posts ──────────────────────────────────────────────────
QUEUE_FILE = Path("_data/stories_queue.json")


@contextlib.contextmanager
def _queue_file_lock():
    """
    Cross-process advisory lock on the queue file. Held while we
    read-modify-write to mark a story consumed, so a concurrent
    fetch_animals.py append doesn't clobber the consumed flag (or vice
    versa). Mirror of fetch_animals.py::_file_lock.
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
    """Read _data/stories_queue.json — schema written by fetch_animals.py."""
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
        "source":         qs.get("source", "Pexels"),
        "source_url":     qs.get("url", ""),
        "image_url":      qs.get("image_url", ""),
        "tags":           [qs.get("category", "wildlife")],
        "category":       qs.get("category", "wildlife"),
        "date":           (qs.get("published_at") or qs.get("fetched_at", ""))[:10],
        "hook":           qs.get("hook", ""),
        # `script` is the full opinionated voice-over (~30-45 s) authored
        # by fetch_animals.py's AI prompt. generate_short() will TTS this
        # directly instead of rebuilding from key_points.
        "script":         qs.get("script", ""),
        "thumbnail_text": qs.get("thumbnail_text", ""),
        "key_points":     qs.get("key_points", []),
        # SEO fields authored by fetch_animals.py — used as-is by
        # build_short_metadata. Each is allowed to be empty; the
        # metadata builder falls back to safe defaults.
        "yt_tags":        qs.get("yt_tags", []),
        "yt_description": qs.get("yt_description", ""),
        "geo_hashtag":    qs.get("geo_hashtag", ""),
        "topic_hashtag":  qs.get("topic_hashtag", ""),
        "discovery_hashtags": list(qs.get("discovery_hashtags") or []),
        "score":          qs.get("score", 0),
        "experiments":    dict(qs.get("experiments") or assign_all_for_production(qs["id"])),
        "pexels_download_url": qs.get("pexels_download_url", ""),
        "pexels_video_id": qs.get("pexels_video_id", ""),
        "source_clip_id": qs.get("source_clip_id", ""),
        "source_download_url": qs.get("source_download_url", ""),
        "source_license": qs.get("source_license", ""),
        "commons_image_url": qs.get("commons_image_url", ""),
        "commons_page_url": qs.get("commons_page_url", ""),
        "commons_license": qs.get("commons_license", ""),
        "commons_artist": qs.get("commons_artist", ""),
        "gbif": dict(qs.get("gbif") or {}),
        "id":             qs["id"],
        "_queue_id":      qs["id"],  # used to mark consumed after success
    }


def load_pending_stories() -> tuple[list[dict], dict]:
    """
    Return (pending_stories, raw_queue). Pending = not yet consumed AND
    not already shipped to YouTube (`shorts_done` tracks the latter,
    handled by the caller). Stories sorted by AI quality score desc.
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
    return rank_for_growth(rank_candidates([_queue_to_story(s) for s in pending])), queue


def diversify_candidates(candidates: list[dict]) -> list[dict]:
    """Round-robin categories while preserving quality order within each one."""
    buckets: dict[str, list[dict]] = {}
    order: list[str] = []
    for candidate in candidates:
        category = candidate.get("category") or "wildlife"
        if category not in buckets:
            buckets[category] = []
            order.append(category)
        buckets[category].append(candidate)
    diversified: list[dict] = []
    while any(buckets.values()):
        for category in order:
            if buckets[category]:
                diversified.append(buckets[category].pop(0))
    return diversified


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
    queue from disk (a concurrent fetch_animals.py may have appended new
    stories since we loaded it), mark this story consumed, save.
    This is the only safe way to persist `consumed: true` when
    fetch_animals.py and generate_shorts.py can interleave.
    """
    with _queue_file_lock():
        disk_queue = _load_queue()
        mark_consumed(disk_queue, queue_id)
        _save_queue(disk_queue)


# ── Gera um único Short ───────────────────────────────────────────
def generate_short(story: dict, tmp_dir: Path) -> tuple[Path, Path, dict] | None:
    """
    Generate one Short for a story.

    Pipeline (preferred path):
      1. TTS audio from the queue's `script` field
      2. b-roll: up to 3 related animal clips from Pexels
      3. captions: Groq Whisper → ASS file with word-level phrases
      4. compose: FFmpeg concats b-roll, burns captions + hook overlay
      5. thumbnail: dynamic, using AI-authored `thumbnail_text`
      6. metadata: from queue's seo_title / yt_tags / yt_description

    Fallback (b-roll unavailable):
      • Render a category-coloured static background with no unrelated
        or generated imagery.
      • Compose with a static-frame FFmpeg pipeline; captions still burn.

    Returns (video_path, thumb_path, metadata) or None on failure.
    """
    # Defensive .get()s on the story dict — a queue entry with a bad
    # schema would crash the whole run otherwise.
    slug = story.get("slug") or f"unknown-{int(time.time())}"
    date_str = story.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = story.get("title") or "Animal fact of the day"
    category = story.get("category", "wildlife")

    log.info(f"  Generating Short for: [{category}] {title[:60]}")

    # English channel ignores stories from PT-BR-native feeds — they're
    # enriched in Portuguese by fetch_animals.py and would need a costly
    # back-translation. Cleaner to skip and let the PT-BR pipeline
    # render them natively.
    native = (story.get("native_lang") or "en").lower()
    if LANGUAGE == "en" and native != "en":
        log.info("  ⏭  Skipping for English channel — story is native %s", native)
        return None

    # Sibling-language channel: translate the AI-authored fields first.
    # The translation already runs through ai_cache so repeat runs of
    # the same story don't double the Mistral burn.
    if LANGUAGE != "en":
        # NATIVE-LANGUAGE FAST PATH: when the story originated from a
        # PT-BR feed (G1, UOL, Folha, etc.) tagged native_lang=pt-BR,
        # fetch_animals.py already enriched it in Portuguese. Skipping
        # translate_story here means zero extra AI calls AND higher
        # editorial quality (no round-trip translation artefacts).
        native = (story.get("native_lang") or "en").lower()
        if native == LANGUAGE.lower():
            log.info("  🇧🇷 Native %s source — no translation needed", LANGUAGE)
            # Still stamp voice_tag so pick_voice walks the locale panel.
            story = dict(story,
                          language=LANGUAGE,
                          voice_tag=SUPPORTED_LANGUAGES[LANGUAGE]["voice_tag"],
                          lang_hashtag=SUPPORTED_LANGUAGES[LANGUAGE]["hashtag"])
        else:
            translated = translate_story(story, LANGUAGE)
            if not translated:
                log.warning("  ⏭  Skipping Short — translation to %s failed for %s",
                             LANGUAGE, title[:60])
                return None
            story = translated
            log.info("  🌍 Translated to %s — voice=%s", LANGUAGE, story.get("voice_tag"))
        title = story.get("title") or story.get("seo_title") or title
        slug = f"{slug}-{LANGUAGE.lower().replace('-', '')}"

    # Queue carries pre-enriched fields when fetch_animals.py is up to date.
    # We require `script` (the full opinionated voice-over) to proceed —
    # backlog stories that predate the schema get rejected here.
    queue_script = (story.get("script") or "").strip()
    if not queue_script:
        log.warning("  ⏭  Skipping Short — no AI script on queue entry: %s", title[:80])
        return None

    # The editor-in-chief is stricter than the script linter: it also
    # considers thumbnail readability, source footage and recent channel
    # memory before spending free-tier resources on rendering.
    editorial = editorial_review(story)
    story["editorial"] = editorial.to_dict()
    story["series"] = editorial.series
    if not editorial.approved:
        log.warning(
            "  Skipping Short - editor-in-chief rejected score=%d subject=%s reasons=%s",
            editorial.score, editorial.subject, "; ".join(editorial.reasons),
        )
        return None

    # ── Pre-flight quality gate ──────────────────────────────────
    # Catch AI-tell phrases, weak hooks, and wire-copy rewrites
    # BEFORE we burn TTS / b-roll / FFmpeg time. The case-study
    # research is unanimous: shipping unchecked LLM output is what
    # got the terminated channels terminated. Skipping a bad Short
    # is always cheaper than getting flagged.
    grade, issues = evaluate_script(story)
    if issues:
        log.info("  📋 Script quality grade=%d/10 — %d issue(s):", grade, len(issues))
        for issue in issues:
            log.info("     [%s/%s] %s", issue.severity, issue.code, issue.message)
    if quality_should_block(issues):
        log.warning(
            "  ⏭  Skipping Short — quality gate blocks: %s (grade=%d, blocks=%d, warns=%d)",
            title[:60], grade,
            sum(1 for i in issues if i.severity == "block"),
            sum(1 for i in issues if i.severity == "warn"),
        )
        return None
    hook_text       = (story.get("hook") or "").strip()
    thumbnail_text  = (story.get("thumbnail_text") or "").strip()
    display_title   = (story.get("title") or "").strip()  # already seo_title from queue

    # ── 1. TTS narration ──────────────────────────────────────────
    script = humanize_for_tts(queue_script)
    audio_path = tmp_dir / f"audio_{slug}.mp3"
    # Translated stories carry a `voice_tag` (e.g. "pt-BR") set by
    # utils.translation.translate_story. English stories don't set it,
    # so pick_voice falls through to the default panel.
    voice_tag = story.get("voice_tag", "")
    voice = pick_voice(seed_text=title, category=category, voice_tag=voice_tag)
    story["narrator_voice"] = voice
    story["story_format"] = classify_format(f"{display_title} {hook_text} {queue_script}")
    log.info(f"  🎤 Voice: {voice}{' [' + voice_tag + ']' if voice_tag else ''}")

    # Split-rate TTS: render the hook at a calmer rate (≈ 4 pp slower)
    # then the rest of the script at the voice's regular rate. The
    # script always opens with the hook verbatim (fetch_animals.py's
    # prompt enforces this), so we can split on the hook itself.
    split_rendered = False
    if hook_text and queue_script.lstrip().lower().startswith(hook_text.lower()):
        body_after = queue_script[len(hook_text):].lstrip(" .!?")
        body_humanised = humanize_for_tts(body_after)
        if body_humanised:
            try:
                split_rendered = asyncio.run(
                    text_to_speech_hook_then_body(
                        hook=humanize_for_tts(hook_text),
                        body=body_humanised,
                        output_path=audio_path,
                        voice=voice,
                        tmp_dir=tmp_dir,
                    )
                )
            except Exception as exc:
                log.warning("hook/body split TTS errored: %s — falling back",
                              exc)
                split_rendered = False

    if not split_rendered:
        try:
            asyncio.run(text_to_speech(script, audio_path, voice))
            size_kb = audio_path.stat().st_size / 1024
            log.info(f"  TTS generated ({size_kb:.0f} KB)")
        except Exception as e:
            log.error(f"  TTS failed: {e}")
            if voice != VOICE_SHORT:
                try:
                    log.info("  Retrying TTS with default voice…")
                    asyncio.run(text_to_speech(script, audio_path, VOICE_SHORT))
                    log.info(f"  TTS recovered with {VOICE_SHORT}")
                except Exception as e2:
                    log.error(f"  TTS retry failed: {e2}")
                    return None
            else:
                return None

    # ── 1.4. Intro / outro wrap with the host's recurring lines. ─
    # Pre-rendered once per voice and cached under
    # `_data/intro_outro_cache/`. Wild Brief skips a spoken intro so
    # the hook starts immediately, then adds the subscribe sign-off.
    audio_path = wrap_with_intro_outro(
        body_audio=audio_path,
        voice=voice,
        tmp_dir=tmp_dir,
        text_to_speech_fn=text_to_speech,
    )

    # ── 1.5. Music bed (background, ducked to -22 dB by default). ─
    # Picks a Pixabay CC0 track keyed by story mood and mixes it under
    # the TTS. If the download or mix fails, audio_path is returned
    # unchanged — music is enhancement, not a hard requirement.
    audio_path = add_music_bed(audio_path, story, tmp_dir)

    # ── 2. Captions (word-level) — biggest single retention lever. ─
    ass_path = generate_captions(audio_path, tmp_dir)
    if not ass_path and QUALITY_REQUIRE_CAPTIONS:
        log.warning("  Skipping Short - production quality requires captions")
        return None
    if ass_path:
        log.info("  📝 Captions ready: %s", ass_path.name)
    else:
        log.info("  ⚠ Captions skipped — Whisper providers unavailable")

    # ── 3. B-roll discovery + download ────────────────────────────
    # Three carefully-related clips beat a noisy montage. The exact
    # source clip is preferred and supplemental footage stays inside
    # animal-only Pexels search.
    broll_paths = acquire_broll_clips(story, tmp_dir, want_n=3)
    if not broll_paths and QUALITY_REQUIRE_MOTION_BROLL:
        log.warning("  Skipping Short - production quality requires motion b-roll")
        return None

    # ── 4. Output paths ───────────────────────────────────────────
    VIDEOS_DIR.mkdir(exist_ok=True)
    video_path = VIDEOS_DIR / f"short-{slug}-{date_str}.mp4"
    thumb_path = VIDEOS_DIR / f"short-{slug}-{date_str}_thumb.jpg"

    # ── 5. Background image (always needed for thumbnail; sometimes
    # also for the static-frame video pipeline fallback). The b-roll
    # path doesn't use this for video but we still need a still for
    # the thumbnail composition.
    bg_path = tmp_dir / f"bg_{slug}.jpg"
    img_ok = bool(broll_paths) and _extract_broll_thumbnail(
        broll_paths[0],
        bg_path,
    )
    if not img_ok:
        img_ok = download_commons_image(story, bg_path)

    # Final-fallback: synthesise a category-coloured gradient so a story
    # without usable animal footage NEVER introduces a random person,
    # object, or generated scene. This background only backs the
    # thumbnail and static-frame fallback compose.
    if not img_ok or not bg_path.exists() or bg_path.stat().st_size < 5 * 1024:
        try:
            img_ok = _render_solid_color_background(category, bg_path)
        except Exception as exc:
            log.warning("  ⚠ solid-colour bg fallback failed: %s", exc)
            img_ok = False

    if not img_ok or not bg_path.exists() or bg_path.stat().st_size < 5 * 1024:
        log.warning(
            "  ⏭  Skipping Short — every background source failed, "
            "including the solid-colour fallback (PIL not importable?): %s",
            title[:80],
        )
        return None

    visual_qa = evaluate_frame(bg_path, story.get("title") or display_title)
    if visual_qa.get("checked") and not visual_qa.get("approved"):
        log.warning("  Skipping Short - Gemini visual QA rejected frame: %s",
                    visual_qa.get("reason", "subject mismatch"))
        return None
    if (visual_qa.get("checked")
            and int(visual_qa.get("thumbnail_quality", 0) or 0) < QUALITY_MIN_VISUAL_QA_SCORE):
        log.warning("  Skipping Short - Gemini visual QA score %s is below %s",
                    visual_qa.get("thumbnail_quality"), QUALITY_MIN_VISUAL_QA_SCORE)
        return None

    # Render the still frame used for (a) the static-video fallback,
    # and (b) the dynamic thumbnail base.
    points = extract_key_points(story.get("description", ""))
    frame = create_short_frame(
        title=display_title,
        category=category,
        points=points,
        source=story.get("source", "Pexels"),
        bg_path=bg_path,
    )
    frame_path = tmp_dir / f"frame_{slug}.png"
    frame.save(str(frame_path))

    # ── 6. Thumbnail: variant-driven (A/B framework) ──────────────
    # The thumbnail_style axis picks between dynamic_text overlay,
    # category-colour solid block, and the legacy brand-static JPEG.
    # create_short_thumbnail's fallback chain handles each path.
    experiments = story.get("experiments") or {}
    thumb_variant = experiments.get("thumbnail_style") \
                    or assign_variant("thumbnail_style", slug)
    if thumb_variant == "brand_static":
        # Forcing empty thumbnail_text triggers the static brand fallback
        # inside create_short_thumbnail.
        create_short_thumbnail(frame, thumb_path,
                                thumbnail_text="",
                                category=category)
    else:
        # dynamic_text + category_color both use the dynamic renderer;
        # category_color biases harder toward the slab fill colour.
        create_short_thumbnail(frame, thumb_path,
                                thumbnail_text=thumbnail_text,
                                category=category)
    if not thumb_path.exists() or thumb_path.stat().st_size < 5 * 1024:
        log.warning("  ⏭  Skipping Short — thumbnail too small: %s", title[:80])
        return None

    # ── 7. Compose video (b-roll preferred, static fallback) ──────
    # Every Short closes with one unambiguous channel-growth action.
    cta_text = "SUBSCRIBE FOR MORE ANIMAL FACTS"
    # Brand-bug watermark. Disabled by default because a second channel
    # mark adds visual noise to a compact Shorts frame.
    # Set CHANNEL_WATERMARK=@yourhandle to opt back in (useful if you're
    # cross-posting the raw MP4 elsewhere).
    watermark_text = os.environ.get("CHANNEL_WATERMARK", "")
    if broll_paths:
        ok = build_broll_short(
            broll_paths=broll_paths,
            audio_path=audio_path,
            output_path=video_path,
            ass_subtitle_path=ass_path,
            hook_text=hook_text or display_title,
            cover_text=thumbnail_text,
            cta_text=cta_text,
            watermark_text=watermark_text,
        )
        if not ok and QUALITY_REQUIRE_MOTION_BROLL:
            log.warning("  Skipping Short - b-roll compose failed in strict production mode")
            return None
        if not ok:
            log.info("  ⤵ B-roll compose failed — falling back to static frame.")
            ok = build_static_short(
                frame_path=frame_path,
                audio_path=audio_path,
                output_path=video_path,
                ass_subtitle_path=ass_path,
                hook_text=hook_text or display_title,
                cover_text=thumbnail_text,
                cta_text=cta_text,
                watermark_text=watermark_text,
            )
    else:
        ok = build_static_short(
            frame_path=frame_path,
            audio_path=audio_path,
            output_path=video_path,
            ass_subtitle_path=ass_path,
            hook_text=hook_text or display_title,
            cover_text=thumbnail_text,
            cta_text=cta_text,
            watermark_text=watermark_text,
        )
    if not ok:
        return None

    # NOTE: the thumbnail was written earlier by `create_short_thumbnail`
    # using the branded Wild Brief placeholder. We deliberately do NOT
    # overwrite it with a frame from the composed video — the operator
    # prefers a consistent branded preview tile across the channel.

    # ── 8. Metadata JSON ──────────────────────────────────────────
    metadata = build_short_metadata(story, video_path, thumb_path)
    # Tag metadata as synthetic content for downstream disclosure tools.
    metadata["altered_content"] = True
    metadata["has_broll"] = bool(broll_paths)
    metadata["has_captions"] = bool(ass_path)
    metadata["visual_qa"] = visual_qa
    metadata["script_quality_grade"] = grade
    metadata["production_quality"] = {
        "motion_broll_required": QUALITY_REQUIRE_MOTION_BROLL,
        "captions_required": QUALITY_REQUIRE_CAPTIONS,
        "min_visual_qa_score": QUALITY_MIN_VISUAL_QA_SCORE,
    }
    metadata["editorial"] = editorial.to_dict()
    metadata["series"] = editorial.series
    meta_path = video_path.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    log.info(f"  Metadata saved: {meta_path.name}")

    # ── 9. Channel memory: log this Short so future stories can
    # callback to it ("I covered this two weeks ago — here's the update").
    try:
        from utils.channel_memory import remember as _remember_story
        _remember_story(story)
    except Exception as exc:
        log.debug("channel_memory remember skipped: %s", exc)

    return video_path, thumb_path, metadata


# ── Principal ────────────────────────────────────────────────────
def main():
    # generate_shorts.py no longer calls the LLM at the top level —
    # `seo_title`, `script`, `hook`, `yt_tags`, `thumbnail_text` all
    # come from fetch_animals.py's queue. We DO still call Whisper for
    # captions and edge-tts for narration, but those happen inside
    # generate_short() on a per-story basis. The fail-fast checks
    # below catch the cases where the queue file itself is missing.
    from utils.panic import abort_if_halted
    abort_if_halted("generate_shorts")
    VIDEOS_DIR.mkdir(exist_ok=True)

    if not QUEUE_FILE.exists():
        log.error(f"{QUEUE_FILE} not found — run fetch_animals.py first.")
        sys.exit(2)

    shorts_done = load_shorts_done()
    log.info(f"Shorts already done: {len(shorts_done)}")

    candidates, queue = load_pending_stories()
    # Belt-and-braces: queue dedup already excludes consumed stories,
    # but shorts_done covers the case where a story was published to
    # YouTube but the workflow died before marking it consumed.
    candidates = [c for c in candidates if c["slug"] not in shorts_done]

    # Honour the operator's `/block <slug>` decisions from the daily
    # digest issue. utils/digest.py harvest_block_commands writes the
    # list to _data/blocked_slugs.json; we filter against it here so a
    # blocked story is silently dropped before any AI/render work.
    blocked = load_blocked_slugs()
    if blocked:
        before = len(candidates)
        candidates = [c for c in candidates if c["slug"] not in blocked
                       and c.get("_queue_id", "") not in blocked]
        if before != len(candidates):
            log.info("🚫 Filtered out %d blocked stories (operator /block)",
                     before - len(candidates))

    candidates = diversify_candidates(candidates)
    log.info(f"Queue has {len(candidates)} pending stor{'y' if len(candidates)==1 else 'ies'}.")
    if not candidates:
        log.info("Nothing to do.")
        return

    # Walk MORE candidates than we need so a single quality-gate
    # rejection or a transient generation failure (TTS hiccup, b-roll
    # download timeout, etc.) doesn't take the whole run to zero
    # published. We aim to PRODUCE `MAX_SHORTS_PER_RUN` successes and
    # we'll burn up to 5× that many candidates trying. With ~20+
    # pending stories in the queue at any given moment, 5 retries is
    # well under queue depth and worst-case adds maybe 30 seconds of
    # wasted AI work — far better than skipping the slot entirely.
    pool = candidates[:MAX_SHORTS_PER_RUN * 5]
    log.info(f"Aiming for {MAX_SHORTS_PER_RUN} Short(s) this run "
             f"(pool of {len(pool)} candidate(s) available):")
    for i, s in enumerate(pool[:MAX_SHORTS_PER_RUN], 1):
        log.info(f"  {i}. [{s['category']}] {s['title'][:70]}")

    tmp = Path(f"/tmp/yt_shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    tmp.mkdir(exist_ok=True)

    created = 0
    attempted = 0
    for story in pool:
        if created >= MAX_SHORTS_PER_RUN:
            break
        attempted += 1
        result = generate_short(story, tmp)
        if result:
            video_path, thumb_path, metadata = result
            shorts_done.add(story["slug"])
            save_shorts_done(shorts_done)
            # Persist consumption back to the queue under the
            # cross-process lock so a concurrent fetch_animals.py append
            # can't undo it. We pass through commit_consumed() instead
            # of the bare _save_queue(queue) — that one would write our
            # stale in-memory copy and overwrite any fetch_animals flush.
            commit_consumed(story.get("_queue_id", ""))
            created += 1
            log.info(f"  Short ready: {video_path.name}")
            log.info(f"  YT title: {metadata['title'][:80]}")
        else:
            log.warning(f"  ⏭ Candidate skipped, trying next: {story.get('slug', '?')}")

    shutil.rmtree(tmp, ignore_errors=True)
    log.info(f"\nDone: {created}/{MAX_SHORTS_PER_RUN} Short(s) created "
             f"in {VIDEOS_DIR}/ ({attempted} candidate(s) attempted).")

    # Observable failure signal: if we were asked to make Shorts and
    # produced zero, exit non-zero so the workflow turns red. Beats
    # "✅ success" on a day where no Short actually shipped.
    if pool and created == 0:
        log.error("❌ All Short generations failed. Exiting non-zero.")
        sys.exit(1)


if __name__ == "__main__":
    main()
