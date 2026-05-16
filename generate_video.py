#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_video.py — Gera vídeo roundup horário para o YouTube
==============================================================
Formato: 1 vídeo por hora cobrindo 6 histórias → ~10-12 minutos.
Vídeos longos habilitam mid-roll ads (mínimo 8 min), maximizando receita.

Estrutura do vídeo:
  Intro       ~30s   "Welcome to GlobalBR News Hourly Roundup"
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

from utils.ai_helper import ai_text as _ai_text
from utils.text import humanize_for_tts

def _ai_youtube_meta(stories: list[dict], n: int, date_str: str) -> dict:
    """
    Gera title, description, tags e thumbnail_hook do YouTube para máximo CTR + SEO.
    Retorna dict (vazio se IA falhar — caller usa fallback).
    """
    cats = [s.get("category", "news").upper() for s in stories]
    dominant = max(set(cats), key=cats.count) if cats else "NEWS"
    headlines = "\n".join(f"- {s['title']}" for s in stories[:8])
    prompt = (
        f"You are a YouTube growth strategist. Generate metadata for a news roundup video "
        f"that maximises both click-through rate AND credibility. Respond ONLY as valid JSON.\n\n"
        f"Date: {date_str}\nDominant category: {dominant}\nNumber of stories: {n}\n"
        f"Headlines:\n{headlines}\n\n"
        f"Rules for the TITLE (max 65 chars):\n"
        f"  - Lead with a SPECIFIC hook from one of the headlines (a name, number, dollar amount, or twist).\n"
        f"  - Curiosity gap is good. Pure clickbait is NOT (no 'YOU WON'T BELIEVE', no all-caps).\n"
        f"  - NEVER use the boilerplate phrase 'World News Roundup'.\n"
        f"  - Good shapes: '{n} stories you missed today (including ...)', "
        f"'Why X just happened — and {n-1} more stories', "
        f"'The {dominant.lower()} news nobody is covering today', "
        f"'$50M, 3 arrests, 1 leak — today in {dominant.lower()}'.\n"
        f"  - Numbers, names, and specifics ALWAYS beat generic phrasing.\n\n"
        f"Rules for THUMBNAIL_HOOK (3-5 words, max 28 chars):\n"
        f"  - Punchy phrase that goes BIG on the thumbnail image. Different from the title.\n"
        f"  - High-emotion, specific. Examples: 'TRUMP SHOCKS WALL ST', 'KYIV HIT AGAIN', "
        f"'$2B DEAL COLLAPSES', 'AI BEATS DOCTORS', 'OPENAI vs MUSK'.\n"
        f"  - ALL CAPS is fine here (it's display text, not the title).\n\n"
        f"Rules for DESCRIPTION (900-1000 chars):\n"
        f"  - First 2 sentences summarise the top 3 stories (shown in search snippets).\n"
        f"  - Then a bullet list of what viewers will learn.\n"
        f"  - End with: Subscribe for hourly world news updates → https://youtube.com/@globalbrnews\n\n"
        f"Rules for TAGS (10 items, lowercase, no hashtag prefix):\n"
        f"  - Mix of: 2 broad ('world news today', 'breaking news'), 3 from the actual headlines "
        f"(real names/places/topics), 2 category-specific, 3 long-tail '... today {date_str[:4]}' style.\n\n"
        f'Return this exact JSON shape:\n'
        f'{{"title":"...","thumbnail_hook":"...","description":"...","tags":["...","...","..."]}}'
    )
    raw = _ai_text(prompt, seed=abs(hash(date_str)) % 9999, timeout=22, json_mode=True)
    if not raw:
        return {}
    try:
        clean = re.sub(r'```(?:json)?\s*|\s*```', '', raw).strip()
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m:
            return json.loads(m.group(), strict=False)
    except Exception as e:
        log.warning(f"AI YouTube meta parse error: {e}")
    return {}

def _ai_video_hook(stories: list[dict], dominant_cat: str) -> str:
    """
    Gera um gancho de abertura poderoso para os primeiros 15 segundos do vídeo.
    Retorna string vazia em falha — o template padrão é usado como fallback.
    """
    headlines = "\n".join(f"- {s['title']}" for s in stories[:6])
    prompt = (
        f"Write a powerful 15-second opening hook for a YouTube news video. "
        f"Category: {dominant_cat}. "
        f"Today's top stories:\n{headlines}\n\n"
        f"The hook must: start with an attention-grabbing fact or question, "
        f"tease the biggest story, make viewers want to stay. "
        f"Maximum 60 words. No intro like 'Here is the hook:'. Just the hook text."
    )
    return _ai_text(prompt, seed=42, timeout=18)

def _build_chapters(key_points: list[str], total_duration_estimate: int = 180) -> str:
    """Generate YouTube chapter timestamps from key points."""
    if not key_points or len(key_points) < 2:
        return ""

    chapters = ["00:00 Introduction"]
    # Distribute key points evenly
    segment = total_duration_estimate // (len(key_points) + 1)
    for i, point in enumerate(key_points[:5], 1):
        mins, secs = divmod(i * segment, 60)
        label = point[:60].rstrip('.').strip()
        chapters.append(f"{mins:02d}:{secs:02d} {label}")

    # Add outro
    outro_mins, outro_secs = divmod(total_duration_estimate - 10, 60)
    chapters.append(f"{outro_mins:02d}:{outro_secs:02d} Summary")

    return "\n\n" + "\n".join(chapters)

# ── Config ─────────────────────────────────────────────────────
VIDEOS_DIR        = Path("_videos")
LOG_FILE          = "generate_video.log"
STORIES_PER_VIDEO = 6      # histórias por roundup (~10 min)
MIN_STORIES       = 3      # mínimo para gerar (evita vídeos muito curtos)
MAX_PER_RUN       = 1      # 1 roundup por execução
VIDEO_W, VIDEO_H  = 1920, 1080

# Paleta de cores — identidade GlobalBR
BG_DARK     = (8, 8, 18)
ACCENT_BLUE = (0, 195, 255)
ACCENT_CYAN = (0, 240, 200)
RED_LIVE    = (220, 50, 50)
TEXT_WHITE  = (245, 245, 255)
TEXT_GRAY   = (160, 165, 190)

# Voz por categoria. Default Jenny + Davis: more conversational than
# Aria (which sounds like a corporate anchor). Override per category.
VOICE_BY_CATEGORY = {
    "AI":       "en-US-JennyNeural",
    "SECURITY": "en-US-GuyNeural",
    "BUSINESS": "en-US-JennyNeural",
    "BIG TECH": "en-US-DavisNeural",
    "HARDWARE": "en-US-DavisNeural",
    "TECH":     "en-US-JennyNeural",
}
VOICE_DEFAULT = "en-US-JennyNeural"

# ── CTA block appended to all video descriptions ───────────────
CTA_BLOCK = """

─────────────────────────
🌐 Read more: https://non-s.github.io
📡 RSS Feed: https://non-s.github.io/feed.xml
─────────────────────────
#GlobalBRNews #WorldNews #BreakingNews"""

# ── Category-based tag bank ─────────────────────────────────────
CATEGORY_TAG_BANK = {
    "world":       ["world news", "international news", "global news", "breaking news", "current events"],
    "technology":  ["tech news", "technology", "innovation", "silicon valley", "gadgets", "AI news"],
    "politics":    ["politics", "government", "policy", "elections", "democracy", "world politics"],
    "business":    ["business news", "economy", "finance", "markets", "stocks", "entrepreneurship"],
    "science":     ["science news", "research", "discovery", "space", "biology", "physics"],
    "health":      ["health news", "medicine", "wellness", "medical research", "public health"],
    "environment": ["climate change", "environment", "sustainability", "green energy", "nature"],
    "ai":          ["artificial intelligence", "machine learning", "ChatGPT", "AI", "deep learning"],
    "sports":      ["sports news", "athletics", "championship", "football", "soccer"],
}

def _build_tags(article_tags: list, category: str) -> list:
    base = CATEGORY_TAG_BANK.get(category.lower(), ["world news", "breaking news", "global news"])
    combined = base + [t for t in article_tags if t not in base]
    # Always include brand tags
    combined += ["GlobalBR News", "globalbrnews"]
    return list(dict.fromkeys(combined))[:30]  # deduplicate, max 30

# ── Category colors for thumbnail banner ────────────────────────
CATEGORY_COLORS = {
    "world": "#dc2626", "technology": "#2563eb", "politics": "#7c3aed",
    "business": "#d97706", "science": "#059669", "health": "#db2777",
    "environment": "#16a34a", "ai": "#0891b2", "sports": "#ea580c",
    "default": "#f97316",
}

def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

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

# ── Tradução PT-BR ────────────────────────────────────────────
def _translate_script_pt(script: str) -> str:
    """Translate an English video script to Brazilian Portuguese via AI."""
    try:
        prompt = (
            f"Translate this news video script to Brazilian Portuguese (PT-BR). "
            f"Keep the same structure and tone. Return ONLY the translated script, no commentary:\n\n"
            f"{script[:3000]}"
        )
        return _ai_text(prompt)
    except Exception as e:
        log.warning(f"PT translation error: {e}")
        return ""


def create_pt_video(stories: list[dict], script_en: str, output_dir: Path):
    """
    Cria versão PT-BR do vídeo roundup usando as mesmas imagens do EN.
    Retorna Path do vídeo gerado, ou None em falha.
    """
    slug = roundup_slug()
    pt_video_path = output_dir / f"{slug}-pt.mp4"

    script_pt = _translate_script_pt(script_en)
    if len(script_pt) <= 200:
        log.warning("PT translation too short or failed — skipping PT video.")
        return None

    tmp = Path(f"/tmp/yt_{slug}_pt")
    tmp.mkdir(exist_ok=True)

    # Download images (same as EN flow)
    image_paths: list[Path | None] = []
    for i, story in enumerate(stories):
        if story["image_url"]:
            dest = tmp / f"img_{i}.jpg"
            image_paths.append(dest if download_image(story["image_url"], dest) else None)
        else:
            image_paths.append(None)

    # TTS — voz PT-BR
    mp3_pt = tmp / "narration_pt.mp3"
    try:
        asyncio.run(text_to_speech(script_pt, mp3_pt, "pt-BR-FranciscaNeural"))
        log.info(f"  🇧🇷 TTS PT-BR gerado: {mp3_pt.stat().st_size // 1024} KB")
    except Exception as e:
        log.error(f"  ❌ TTS PT-BR falhou: {e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return None

    # Vídeo PT com mesmas imagens
    ok = create_roundup_video(stories, image_paths, mp3_pt, pt_video_path)
    shutil.rmtree(tmp, ignore_errors=True)

    if not ok:
        return None

    log.info(f"  ✅ Vídeo PT-BR gerado: {pt_video_path.name}")
    return pt_video_path


# ── Script de narração roundup ──────────────────────────────────
ORDINALS = ["one", "two", "three", "four", "five", "six", "seven", "eight"]

def clean_text(text: str, max_chars: int = 500) -> str:
    return humanize_for_tts(text)[:max_chars]

def build_roundup_script(stories: list[dict]) -> str:
    """
    Script jornalístico com gancho AI + corpo template.
    Alvo: ~1.500 palavras → ~10-12 min de narração a 130 wpm.
    """
    n = len(stories)
    cats = [s["category"] for s in stories]
    dominant = max(set(cats), key=cats.count)

    cat_label_map = {
        "AI":          "artificial intelligence",
        "SECURITY":    "cybersecurity",
        "BUSINESS":    "business and economy",
        "BIG TECH":    "big tech",
        "HARDWARE":    "hardware and devices",
        "TECH":        "technology",
        "WORLD":       "world affairs",
        "POLITICS":    "politics",
        "WAR":         "conflict and defense",
        "SCIENCE":     "science and discovery",
        "HEALTH":      "health and medicine",
        "SPORTS":      "sports",
        "FOOD":        "food and culture",
        "ENVIRONMENT": "environment and climate",
        "TRAVEL":      "travel",
        "ENTERTAINMENT": "entertainment",
    }
    cat_label = cat_label_map.get(dominant.upper(), "global news")

    now      = datetime.now()
    date_str = now.strftime("%B %d, %Y")
    hour_str = now.strftime("%I %p").lstrip("0")

    # ── AI HOOK (primeiros 15 segundos — crucial para retenção) ──
    ai_hook = _ai_video_hook(stories, cat_label)

    # ── INTRO ─────────────────────────────────────────────────────
    if ai_hook:
        script = f"""{ai_hook}

Hey, welcome to GlobalBR News. It's {date_str}, and I've got {n} stories you'll want to know about — covering {cat_label} and more from around the world.

Every link is in the description, so you can read the full piece from the original source. We always credit the journalists doing the actual reporting.

Let's get into it."""
    else:
        script = f"""Hey, welcome back to GlobalBR News. It's {date_str} at {hour_str}, and I've got {n} stories for you — {cat_label} and more from around the world.

Whether you're on a commute, at the gym, or just catching up — you're in the right spot. We do one of these every hour, so you never have to hunt for what's actually going on.

Every link is down in the description so you can read the full article from the source. Credit always goes to the journalists doing the reporting.

If any of this is useful to you, hit subscribe — it's the single biggest thing you can do to support us.

Alright. {n} stories. Let's go."""

    # ── HISTÓRIAS (~200 words cada) ───────────────────────────────
    cat_context = {
        "AI": [
            "Artificial intelligence continues to reshape the technology landscape at an extraordinary pace.",
            "The race to develop more capable AI systems is intensifying, with major implications for businesses and consumers alike.",
            "This development is part of a broader trend of rapid advancement in AI capabilities that is transforming industries worldwide.",
            "As AI systems become more powerful, questions around safety, regulation, and responsible deployment are increasingly at the forefront of public debate.",
        ],
        "SECURITY": [
            "Cybersecurity threats continue to evolve in sophistication, making this development particularly noteworthy for organizations and individuals.",
            "This incident highlights the growing importance of robust cybersecurity practices in an increasingly digital world.",
            "Security researchers are closely monitoring this situation, as it could have wider implications for how we protect digital systems.",
            "Experts recommend that affected users take immediate steps to secure their accounts and monitor for suspicious activity.",
        ],
        "BUSINESS": [
            "The startup ecosystem remains highly active, with investors continuing to back innovative companies despite broader economic uncertainty.",
            "This development reflects the ongoing transformation of the technology industry and the growing appetite for disruptive new solutions.",
            "Analysts will be watching closely to see how this plays out in the coming months, as the competitive landscape continues to shift.",
            "This move signals growing confidence in the sector and could attract further investment and attention from major players.",
        ],
        "BIG TECH": [
            "Big tech companies continue to make moves that will shape the digital experiences of billions of people around the world.",
            "This announcement is likely to have significant ripple effects across the technology industry and related sectors.",
            "The major technology companies are in a constant race to innovate, and this latest development is a clear signal of where the industry is heading.",
            "Consumers and businesses alike will be paying close attention to how this unfolds over the coming weeks.",
        ],
        "HARDWARE": [
            "Hardware innovation continues to push the boundaries of what is possible for consumers and professionals alike.",
            "Advances in hardware technology have a direct impact on the software and services we rely on every day.",
            "This product development reflects the ongoing competition among manufacturers to deliver better performance and value.",
            "Technology enthusiasts and professionals have been eagerly anticipating this kind of advancement.",
        ],
        "TECH": [
            "This is the kind of development that reminds us just how quickly the technology world can change.",
            "Software and digital technology continue to transform the way we work, communicate, and access information.",
            "The broader implications of this story are still unfolding, but it is already generating significant discussion in the tech community.",
            "This development is worth watching closely, as it could influence decisions made by companies and policymakers in the months ahead.",
        ],
    }

    transitions = [
        "Next up.",
        "Onto the next one.",
        "Here's another one worth your time.",
        "Switching gears.",
        "Story number {next}.",
        "This one caught my eye too.",
        "Now this is interesting.",
        "Speaking of which, listen to this.",
        "And there's more.",
        "Let's get into the next story.",
        "On a different note.",
        "Here's something else you should know.",
    ]

    for i, story in enumerate(stories):
        ordinal  = ORDINALS[i] if i < len(ORDINALS) else f"number {i + 1}"
        title    = humanize_for_tts(story["title"])
        desc     = clean_text(story["description"], 600)
        source   = humanize_for_tts(story["source"])
        category = story["category"]

        sentences = re.split(r'(?<=[.!?])\s+', desc)
        opening   = " ".join(sentences[:2]) if len(sentences) >= 2 else desc
        body      = " ".join(sentences[2:6]) if len(sentences) > 2 else ""

        # Contexto adicional baseado na categoria
        ctx_pool = cat_context.get(category, cat_context["TECH"])
        context1 = ctx_pool[i % len(ctx_pool)]
        context2 = ctx_pool[(i + 1) % len(ctx_pool)]

        script += f"""Story {ordinal}: {title}.

{opening}

{context1}

"""
        if body:
            script += f"""{body}

"""

        script += f"""{context2}

This story was reported by {source}, which is one of the most respected publications covering this space. If you want the complete picture — the quotes, the data, the analysis — the link to the full article is waiting for you in the description below. We strongly encourage you to support the original journalists doing this important work.

"""
        # Transição entre histórias (exceto na última)
        if i < n - 1:
            next_ordinal = ORDINALS[i + 1] if (i + 1) < len(ORDINALS) else f"number {i + 2}"
            trans = transitions[i % len(transitions)].format(next=next_ordinal)
            script += f"""{trans}

"""

    # ── OUTRO (~220 words) ────────────────────────────────────────
    script += f"""And that's the hour. {n} stories from around the world.

A quick recap before you go:

We started with {stories[0]['title'] if stories else 'our top story'}.

{"Then there was " + stories[1]['title'] + "." if len(stories) > 1 else ""}

{"Plus " + str(len(stories) - 2) + " more — all of them in the description with timestamps if you want to jump around." if len(stories) > 2 else ""}

Which one caught your attention? Tell me in the comments — I actually read them, and it shapes what we cover next.

If you're not subscribed yet, take a second to fix that. We're back every hour with a new roundup, so subscribing means you'll always be ahead of the news cycle.

Everything is also on our website at non-s dot github dot io — searchable, with way more stories than fit in a video like this.

If you know someone who'd actually use this — send it their way. Word of mouth is how we grow.

Thanks for watching. I'll see you in an hour."""

    return script

# ── TTS ────────────────────────────────────────────────────────
async def text_to_speech(text: str, output_path: Path, voice: str):
    import edge_tts
    # Slightly slower rate than the previous +5% — gives the speech room
    # to breathe, which makes the synthetic voice feel less rushed and
    # more like a person and less like an alert.
    communicate = edge_tts.Communicate(text, voice, rate="+0%", pitch="+0Hz")
    await communicate.save(str(output_path))

# ── Download de imagem ─────────────────────────────────────────
def download_image(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=10,
                         headers={"User-Agent": "GlobalBR-Bot/2.0"})
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
    draw.text((50, 20), "GLOBAL", font=get_font(44, bold=True), fill=ACCENT_BLUE)
    draw.text((244, 20), "BR NEWS", font=get_font(44, bold=True), fill=TEXT_WHITE)
    draw.rectangle([(234, 22), (237, 66)], fill=(*ACCENT_BLUE, 180))

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
def _build_thumbnail_prompt(stories: list[dict]) -> str:
    """Build a cinematic Pollinations prompt based on story categories."""
    cats = [s.get("category", "").upper() for s in stories]
    dominant = max(set(cats), key=cats.count) if cats else "TECH"

    base_style = (
        "ultra-high quality YouTube thumbnail, cinematic dramatic lighting, "
        "vivid saturated colors, photorealistic, 4K, sharp focus, "
        "professional news broadcast aesthetic, bold visual impact"
    )

    scene_map = {
        "WORLD":         "dramatic globe earth from space, city skyline at night with lights, epic scale",
        "WAR":           "dramatic military scene, intense smoke and fire, helicopter silhouette, golden hour",
        "POLITICS":      "government building columns with dramatic sky, powerful political atmosphere",
        "BUSINESS":      "futuristic city financial district, glowing skyscrapers, stock market data streams",
        "SCIENCE":       "stunning NASA space view, galaxy nebula, astronaut floating, cosmic colors",
        "HEALTH":        "futuristic medical lab glowing blue, DNA helix, microscope, clean white light",
        "FOOD":          "stunning gourmet dish close-up, rich colors, steam rising, Michelin star plating",
        "SPORTS":        "stadium packed with fans, dramatic action shot, explosive energy, motion blur",
        "ENTERTAINMENT": "Hollywood movie set glowing lights, red carpet, cinematic marquee, star-studded",
        "ENVIRONMENT":   "dramatic nature landscape, stormy sky over ocean, forest fire glow, earth crisis",
        "TRAVEL":        "breathtaking aerial view of exotic destination, crystal ocean, golden sunset",
        "AI":            "futuristic neural network visualization, glowing circuit brain, blue neon tech",
        "SECURITY":      "dark cyber hacker atmosphere, glowing code streams, ominous red and blue",
        "GADGETS":       "sleek tech devices glowing, product reveal lighting, modern minimalist",
        "STARTUPS":      "startup office at night, glowing monitors, modern coworking space, success energy",
        "TECHNOLOGY":    "futuristic smart city, holographic displays, neon blue tech atmosphere, innovation",
    }

    scene = scene_map.get(dominant, scene_map["TECHNOLOGY"])
    top_title = stories[0]["title"][:60] if stories else "World News"

    return f"{scene}, {base_style}, inspired by headline: {top_title}"


def generate_ai_thumbnail_bg(prompt: str, dest: Path, width: int = 1280, height: int = 720) -> bool:
    """Download AI-generated background from Pollinations.ai (free, no API key)."""
    import urllib.parse
    encoded = urllib.parse.quote(prompt)
    seed = abs(hash(prompt)) % 999999
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&nologo=true&seed={seed}&model=flux"
    )
    try:
        log.info(f"  🎨 Generating AI thumbnail background via Pollinations.ai…")
        r = requests.get(url, timeout=60, headers={"User-Agent": "GlobalBR-Bot/3.0"})
        r.raise_for_status()
        dest.write_bytes(r.content)
        log.info(f"  ✅ AI background saved ({len(r.content) // 1024} KB)")
        return True
    except Exception as e:
        log.warning(f"  ⚠️  Pollinations failed ({e}), using fallback background")
        return False


def create_roundup_thumbnail(stories: list[dict], image_paths: list,
                             output: Path, hook_text: str = ""):
    """
    Thumbnail 1280×720 com fundo gerado por IA (Pollinations/Flux) e
    texto BIG sobreposto via PIL — estilo YouTube de alto CTR.

    `hook_text`: 3-5 word punchy phrase from the AI metadata (e.g.
    "TRUMP SHOCKS WALL ST"). When provided, dominates the thumbnail.
    Falls back to top story title if missing.
    """
    W, H = 1280, 720

    # ── 1. Tenta gerar fundo com IA ──────────────────────────────
    ai_bg_path = output.with_name(output.stem + "_aibg.jpg")
    prompt = _build_thumbnail_prompt(stories)
    ai_ok = generate_ai_thumbnail_bg(prompt, ai_bg_path, W, H)

    img = Image.new("RGB", (W, H), BG_DARK)

    if ai_ok and ai_bg_path.exists():
        try:
            bg = Image.open(ai_bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
            img.paste(bg)
        except Exception:
            ai_ok = False

    if not ai_ok:
        # Fallback: gradiente escuro + foto da notícia
        draw = ImageDraw.Draw(img)
        for i in range(H):
            t = i / H
            r = int(8 * (1 - t) + 20 * t)
            g = int(8 * (1 - t) + 8 * t)
            b = int(18 * (1 - t) + 55 * t)
            draw.line([(0, i), (W, i)], fill=(r, g, b))
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

    # ── 2. Overlay escuro semitransparente para legibilidade ─────
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Gradiente horizontal: escuro à esquerda, transparente à direita
    for x in range(W):
        t = max(0, 1 - x / (W * 0.75))
        alpha = int(210 * (t ** 0.6))
        od.line([(x, 0), (x, H)], fill=(0, 0, 8, alpha))
    # Subtle gradient overlay at bottom for text readability
    for y in range(H - 160, H):
        t = (y - (H - 160)) / 160
        alpha = int(180 * t)
        od.line([(0, y), (W, y)], fill=(0, 0, 8, alpha))
    # Faixa inferior sólida para branding
    od.rectangle([(0, H - 120), (W, H)], fill=(0, 0, 8, 200))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # ── 3. Category banner bar at top (20px height) ───────────────
    cats = [s.get("category", "").upper() for s in stories]
    dominant_cat = max(set(cats), key=cats.count) if cats else "TECH"
    cat_key_lower = dominant_cat.lower().replace(" ", "")
    # Try CATEGORY_COLORS first, then fallback stripe_color map
    cat_hex = CATEGORY_COLORS.get(cat_key_lower, CATEGORY_COLORS.get("default", "#f97316"))
    banner_rgb = _hex_to_rgb(cat_hex)
    draw.rectangle([(0, 0), (W, 20)], fill=banner_rgb)

    stripe_color = {
        "WAR": (220, 50, 50), "SPORTS": (255, 140, 0), "FOOD": (255, 180, 0),
        "ENTERTAINMENT": (180, 0, 220), "HEALTH": (0, 200, 120),
        "SCIENCE": (0, 180, 255), "ENVIRONMENT": (0, 200, 80),
    }.get(dominant_cat, banner_rgb)

    for i in range(8):
        alpha_val = 255 - i * 28
        draw.rectangle([(i * 2, 20), (i * 2 + 1, H)],
                       fill=(*stripe_color, alpha_val))

    n = len(stories)

    # ── 4. Badge categoria + número de histórias ─────────────────
    badge_text = f"TOP {n} STORIES"
    bfont = get_font(34, bold=True)
    bbbox = draw.textbbox((0, 0), badge_text, font=bfont)
    draw_rounded_rect(draw, (28, 32, 28 + bbbox[2] + 28, 82),
                      radius=8, fill=RED_LIVE)
    draw.text((42, 40), badge_text, font=bfont, fill=TEXT_WHITE)

    # Category label
    cat_text = dominant_cat
    cfont = get_font(28, bold=True)
    cx = 28 + bbbox[2] + 28 + 16
    cbbox = draw.textbbox((0, 0), cat_text, font=cfont)
    draw_rounded_rect(draw, (cx, 36, cx + cbbox[2] + 20, 78),
                      radius=6, fill=(*stripe_color, 230))
    draw.text((cx + 10, 42), cat_text, font=cfont, fill=(0, 0, 0))

    # ── 5. HOOK GIGANTE — o que decide o clique ──────────────────
    # Prefer the AI's punchy hook ("$2B DEAL COLLAPSES", "KYIV HIT AGAIN").
    # Fall back to the top story title if missing, but truncate hard so
    # we never paint a 3-line cramped paragraph again.
    if hook_text and 4 <= len(hook_text) <= 32:
        main_title = hook_text.upper()
    else:
        main_title = stories[0]["title"] if stories else "WORLD NEWS"
        # Cap to ~24 chars so the text stays huge on the thumb.
        if len(main_title) > 24:
            main_title = main_title[:21].rstrip() + "…"
        main_title = main_title.upper()

    # Pick a font size that fills the canvas without wrapping more than 2 lines.
    tfont = get_font(160, bold=True)
    max_w = int(W * 0.92)
    tlines = wrap_text(draw, main_title, tfont, max_w)
    if len(tlines) > 2:
        tfont = get_font(120, bold=True)
        tlines = wrap_text(draw, main_title, tfont, max_w)
        lh = 130
    elif len(tlines) == 2:
        lh = 168
    else:
        lh = 0  # single line

    # Vertically centre the block.
    total_h = max(lh * (len(tlines) - 1), 0) + (tfont.size if hasattr(tfont, "size") else 160)
    ty = max(120, (H - total_h) // 2 - 20)
    for line in tlines[:2]:
        # Thick outline so it pops against any background.
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                if dx != 0 or dy != 0:
                    draw.text((40 + dx, ty + dy), line, font=tfont, fill=(0, 0, 0))
        # Bright text — colour-pop via category stripe colour for variety.
        draw.text((40, ty), line, font=tfont, fill=TEXT_WHITE)
        ty += lh

    # ── 7. Branding na base — "GLOBALBR NEWS" ────────────────────
    draw.rectangle([(22, H - 108), (int(W * 0.55), H - 105)], fill=stripe_color)
    brand_font = get_font(44, bold=True)
    draw.text((22, H - 100), "GLOBALBR", font=brand_font, fill=stripe_color)
    gbbox = draw.textbbox((0, 0), "GLOBALBR", font=brand_font)
    draw.text((22 + gbbox[2] + 8, H - 100), "NEWS", font=brand_font, fill=TEXT_WHITE)
    now_str = datetime.now().strftime("%b %d, %Y  •  Daily World Roundup")
    draw.text((22, H - 50), now_str, font=get_font(26), fill=TEXT_GRAY)

    img.save(str(output), "JPEG", quality=95, optimize=True)

    # Limpa bg temporário
    if ai_bg_path.exists():
        ai_bg_path.unlink()

    log.info(f"  🖼  Thumbnail salva: {output.name}")


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

# ── Metadados SEO com capítulos + AI ───────────────────────────
def build_metadata(roundup_slug: str, stories: list[dict],
                   thumbnail: Path, video: Path,
                   duration_estimate: float,
                   ai_meta: dict | None = None) -> dict:
    """If `ai_meta` is passed in we skip the second AI call — the caller
    has already generated it (typically because it needed thumbnail_hook
    before this function ran)."""
    n = len(stories)
    year = datetime.now().year
    date_str = datetime.now().strftime("%B %d, %Y")

    # Capítulos com timestamps estimados (15s intro + 75s por história)
    chapters_list = ["0:00 Introduction"]
    for i, story in enumerate(stories):
        seconds = 15 + i * 75
        mins = seconds // 60
        secs = seconds % 60
        title_short = story["title"][:50]
        chapters_list.append(f"{mins}:{secs:02d} {title_short}")
    # Outro timestamp
    outro_secs = 15 + len(stories) * 75
    chapters_list.append(f"{outro_secs // 60}:{outro_secs % 60:02d} Stay informed")

    chapters = "⏱ CHAPTERS\n" + "\n".join(chapters_list)

    stories_summary = "\n".join(
        f"  {i}. {s['title'][:80]}" for i, s in enumerate(stories, 1)
    )
    sources_block = "\n".join(
        f"  • Story {i}: {s['source_url']}" for i, s in enumerate(stories, 1)
    )

    # ── AI-generated title + description (reuse if pre-computed) ─────
    if ai_meta is None:
        ai_meta = _ai_youtube_meta(stories, n, date_str)
    ai_meta = ai_meta or {}

    if ai_meta.get("title") and 10 < len(ai_meta["title"]) <= 100:
        yt_title = ai_meta["title"]
        log.info(f"  🤖 AI YouTube title: {yt_title[:60]}")
    else:
        yt_title = f"World News Roundup — Top {n} Stories | {date_str} | GlobalBR News"

    if ai_meta.get("description") and len(ai_meta["description"]) > 100:
        ai_intro = ai_meta["description"][:900]
        log.info(f"  🤖 AI YouTube description ({len(ai_intro)} chars)")
    else:
        ai_intro = f"In this GlobalBR News World Roundup we cover {n} top stories from around the globe."

    yt_desc = (
        f"{ai_intro}\n\n"
        f"📰 In this video:\n{stories_summary}\n\n"
        "━" * 28 + "\n"
        f"🌐 Sources:\n{sources_block}\n\n"
        "━" * 28 + "\n"
        f"{chapters}\n\n"
        "━" * 28 + "\n"
        "🔔 SUBSCRIBE for world news every hour → https://youtube.com/@globalbrnews\n"
        "📰 Read more at → https://non-s.github.io\n\n"
        "━" * 28 + "\n"
        f"© {year} GlobalBR News. Original articles belong to their respective sources.\n"
        "#WorldNews #NewsRoundup #GlobalNews #GlobalBRNews #BreakingNews"
        + CTA_BLOCK
    )

    # Append auto-generated chapters from story key points
    cats = [s.get("category", "news") for s in stories]
    dominant_cat_lower = max(set(cats), key=cats.count).lower() if cats else "news"
    story_titles = [s["title"] for s in stories]
    chapters_block = _build_chapters(story_titles, int(duration_estimate))
    if chapters_block:
        yt_desc += chapters_block

    # Truncate to YouTube 5000-char limit
    yt_desc = yt_desc[:5000]

    # Tags: use category tag bank + AI tags + story tags
    story_tags = [t for s in stories for t in s.get("tags", [])]
    if ai_meta.get("tags") and isinstance(ai_meta["tags"], list):
        ai_tags = ai_meta["tags"]
        log.info(f"  🤖 AI YouTube tags: {len(ai_tags)} tags")
    else:
        ai_tags = []
    all_tags = _build_tags(ai_tags + story_tags, dominant_cat_lower)

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
    text = (title + " " + " ".join(tags)).lower()
    # Use word boundary check for short keywords to avoid substring false positives
    # e.g. "raises" contains "ai", "hackernews" contains "hack"
    if (re.search(r'\bai\b', text) or
            any(w in text for w in ["artificial intelligence", "machine learning",
                                     "gpt", "llm", "openai", "anthropic",
                                     "gemini", "claude", "deepmind", "mistral"])):
        return "AI"
    if any(w in text for w in ["cybersecurity", "cyber attack", "cyberattack",
                                "data breach", "malware", "ransomware",
                                "vulnerability", "zero-day", "phishing",
                                "exploit", "hacking", "hacked", "spyware",
                                "krebs", "the hacker news"]):
        return "SECURITY"
    if any(w in text for w in ["startup", "funding", "series a", "series b",
                                "series c", "ipo", "acquisition", "billion",
                                "venture capital", "unicorn"]):
        return "BUSINESS"
    if any(w in text for w in ["apple", "google", "microsoft", "meta",
                                "amazon", "nvidia", "tesla", "samsung"]):
        return "BIG TECH"
    if any(w in text for w in ["phone", "iphone", "android", "hardware",
                                "chip", "gpu", "laptop", "processor", "display"]):
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
        source   = fm.get("source_name", "GlobalBR News")
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

    # Gera o AI meta ANTES da thumbnail pra ter o thumbnail_hook na mão.
    # build_metadata depois reusa esse mesmo dict (sem chamar a IA 2x).
    date_str = datetime.now().strftime("%B %d, %Y")
    ai_meta = _ai_youtube_meta(stories, len(stories), date_str)
    hook_text = (ai_meta.get("thumbnail_hook") or "").strip()
    if hook_text:
        log.info(f"  ✨ Thumbnail hook: {hook_text}")

    # Thumbnail
    thumb_path = VIDEOS_DIR / f"{slug}_thumb.jpg"
    create_roundup_thumbnail(stories, image_paths, thumb_path, hook_text=hook_text)

    # Vídeo
    video_path = VIDEOS_DIR / f"{slug}.mp4"
    ok = create_roundup_video(stories, image_paths, mp3_path, video_path)
    if not ok:
        shutil.rmtree(tmp, ignore_errors=True)
        return

    # Metadados SEO com capítulos (reusa o ai_meta já gerado acima)
    build_metadata(slug, stories, thumb_path, video_path, duration, ai_meta=ai_meta)

    # ── Versão PT-BR ─────────────────────────────────────────────
    pt_video = create_pt_video(stories, script, VIDEOS_DIR)
    if pt_video:
        # Traduz título e descrição para PT
        pt_title_raw = _ai_text(
            f"Translate this YouTube video title to Brazilian Portuguese (PT-BR). "
            f"Return ONLY the translated title, no commentary:\n\n{slug.replace('-', ' ').title()}"
        )
        pt_desc_raw = _ai_text(
            f"Translate this to Brazilian Portuguese (PT-BR). "
            f"Return ONLY the translated text:\n\nWorld news roundup with {len(stories)} top stories."
        )
        base_tags = [s for s in stories for s in s.get("tags", [])]
        pt_meta = {
            "title":       pt_title_raw or f"Resumo de Notícias Mundiais | {slug}",
            "description": pt_desc_raw or "Principais notícias do mundo em português.",
            "tags":        list(dict.fromkeys(base_tags + ["pt-br", "noticias", "mundo"])),
            "category_id": "28",
            "privacy":     "public",
            "video":       str(pt_video),
            # Reuse the EN thumbnail — the visual is identical and saves
            # an extra Pollinations call. upload_youtube.py treats this
            # as optional anyway.
            "thumbnail":   str(thumb_path),
            "category":    "roundup",
            "is_short":    False,
        }
        pt_meta_path = VIDEOS_DIR / f"{slug}-pt.json"
        pt_meta_path.write_text(json.dumps(pt_meta, indent=2, ensure_ascii=False))
        log.info(f"  📄 Metadados PT-BR salvos: {pt_meta_path.name}")

    # Marca posts como usados (não serão incluídos em próximo roundup)
    mark_posts_as_used([s["slug"] for s in stories])

    shutil.rmtree(tmp, ignore_errors=True)
    log.info(f"\n\U0001f3c1 Roundup concluído: {slug} ({len(stories)} histórias, ~{duration/60:.1f} min)")


if __name__ == "__main__":
    main()
