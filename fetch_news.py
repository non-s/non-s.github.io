#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_news.py — Coleta notícias de feeds RSS e cria posts Jekyll
================================================================
Uso:
    python fetch_news.py

Dependências:
    pip install feedparser requests

O script:
  1. Lê feeds RSS configurados em FEEDS
  2. Para cada notícia (até MAX_PER_FEED por feed):
     - Filtra conteúdo irrelevante por blacklist
     - Filtra por qualidade mínima (tamanho, relevância)
     - Gera slug único e verifica duplicatas
     - Cria arquivo .md em _posts/ com frontmatter e corpo rico
  3. Registra log em fetch_news.log
"""

import feedparser
import requests
import os
import re
import json
import logging
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

from utils.text import slugify, sanitize_text, extract_description, extract_image, parse_date
from utils.dedup import levenshtein as _levenshtein, titles_too_similar as _titles_too_similar, title_similarity as _title_similarity
from utils.ai_helper import (
    ai_text as _ai_text,
    sentiment_score as _sentiment_score,
    fact_check_score as _fact_check_score,
    is_breaking_news as _is_breaking_news,
    quality_check as _quality_check,
    quality_score as _quality_score,
    BREAKING_KEYWORDS,
)
from utils.retry import retry_call

# HTTP session reutilizável (melhor performance)
_session = requests.Session()
_session.headers.update({"User-Agent": "GlobalBR-News-Bot/3.0 (+https://non-s.github.io)"})



# ============================================================
# WIKIPEDIA API — Enriquecimento de artigos
# ============================================================

_WIKI_CACHE: dict[str, str] = {}


def _fetch_wikipedia_summary(query: str) -> str:
    """Busca resumo do Wikipedia em inglês para o título dado. Retorna até 500 chars.

    Cached per-process: titles that recur within a single run (common when
    multiple articles reference the same entity) only hit Wikipedia once.
    """
    if query in _WIKI_CACHE:
        return _WIKI_CACHE[query]

    def _do_fetch():
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(query)}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "GlobalBRNews/1.0"})
        if r.status_code == 404:
            return ""
        r.raise_for_status()
        return r.json().get("extract", "")[:500]
    result = retry_call(_do_fetch, max_attempts=2, base_delay=2.0, default="")
    out = result or ""
    _WIKI_CACHE[query] = out
    return out


# ============================================================
# COINGECKO — Preços de criptomoedas
# ============================================================

_CRYPTO_PRICES_FILE = Path("_data/crypto_prices.json")
_crypto_prices_cache: dict | None = None

_CRYPTO_KEYWORDS = {
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
    "ripple", "xrp", "cardano", "ada", "solana", "sol", "blockchain",
    "defi", "nft", "web3", "altcoin", "stablecoin",
}


def _fetch_crypto_prices() -> dict:
    """Busca preços de cripto via CoinGecko (sem key). Retorna dict vazio em falha."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin,ethereum,ripple,cardano,solana"
            "&vs_currencies=usd&include_24hr_change=true",
            timeout=10,
            headers={"User-Agent": "GlobalBRNews/1.0"},
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _get_crypto_prices_cached() -> dict:
    """Retorna preços de cripto cacheados para o run atual."""
    global _crypto_prices_cache
    if _crypto_prices_cache is None:
        _crypto_prices_cache = _fetch_crypto_prices()
        try:
            if _crypto_prices_cache:
                _CRYPTO_PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
                _CRYPTO_PRICES_FILE.write_text(
                    json.dumps(_crypto_prices_cache, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception:
            pass
    return _crypto_prices_cache


def _post_is_crypto_related(title: str, description: str) -> bool:
    """Retorna True se o post menciona palavras-chave de cripto."""
    combined = (title + " " + description).lower()
    return any(kw in combined for kw in _CRYPTO_KEYWORDS)


def _check_source_url(url: str, timeout: int = 5) -> bool:
    """
    Makes a HEAD request to the source URL.
    Returns True if HTTP status < 400.
    Returns False on 4xx/5xx errors.
    Returns True on timeout/connection error (don't block on slow servers).
    """
    try:
        r = _session.head(url, timeout=timeout, allow_redirects=True)
        return r.status_code < 400
    except requests.exceptions.Timeout:
        return True   # slow server — don't block the run
    except Exception:
        return True   # network error — don't block the run


_PROTECTED_SLUG_PATTERNS = re.compile(
    r'roundup|digest|weekly|milestone|stats|best-of|infographic',
    re.IGNORECASE,
)


def _get_referenced_slugs() -> set:
    """Return stems of posts referenced in roundup/digest content (protected from cleanup)."""
    referenced: set = set()
    for post_path in POSTS_DIR.glob("*.md"):
        if not _PROTECTED_SLUG_PATTERNS.search(post_path.name):
            continue
        try:
            content = post_path.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'/(\d{4}/\d{2}/\d{2}/[^/\s"\']+)/', content):
                slug_part = m.group(1).split("/")[-1]
                referenced.add(slug_part)
        except Exception:
            pass
    return referenced


def cleanup_old_posts(max_age_days: int = 90) -> int:
    """
    Scans _posts/ for .md files older than max_age_days.
    Skips roundup/digest/milestone/stats posts and posts referenced in roundups.
    Returns count deleted.
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    referenced_slugs = _get_referenced_slugs()
    deleted = 0
    for post_path in POSTS_DIR.glob("*.md"):
        filename = post_path.name
        if _PROTECTED_SLUG_PATTERNS.search(filename):
            continue
        stem = post_path.stem
        slug_part = stem[11:] if len(stem) > 11 else stem  # strip YYYY-MM-DD-
        if slug_part in referenced_slugs:
            continue
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-', filename)
        if not m:
            continue
        try:
            post_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                 tzinfo=timezone.utc)
        except ValueError:
            continue
        if post_date < cutoff:
            try:
                post_path.unlink()
                deleted += 1
                log.debug(f"  🗑  Deleted old post: {filename}")
            except Exception as exc:
                log.warning(f"  ⚠️  Failed to delete {filename}: {exc}")
    log.info(f"🗑  Cleanup: {deleted} post(s) older than {max_age_days} days deleted.")
    return deleted


_ARTICLE_SCENES = {
    "world":         "globe earth world connections editorial journalism photo",
    "politics":      "government parliament building political official press conference",
    "war":           "military helicopter dramatic conflict zone editorial war journalism",
    "business":      "city financial district stock market trading floor professional",
    "science":       "laboratory research scientist microscope discovery breakthrough",
    "health":        "modern hospital medical professional doctor healthcare clean",
    "food":          "gourmet dish professional food photography restaurant kitchen",
    "sports":        "packed stadium dramatic lighting athletic competition action",
    "entertainment": "hollywood film set awards show glamour photography entertainment",
    "environment":   "lush forest climate change renewable energy solar panels nature",
    "travel":        "exotic destination architecture landmark golden hour travel",
    "technology":    "futuristic circuit boards digital interface blue neon tech lab",
    "ai":            "artificial intelligence neural network data center futuristic",
    "security":      "cybersecurity shield digital lock binary code dark blue room",
    "gadgets":       "modern smartphone flat lay tech product photography minimal",
    "startups":      "modern startup office collaborative workspace innovation hub",
    "mobile":        "smartphone close-up mobile app interface modern device",
}

def _news_image_url(title: str, category: str) -> str:
    """URL de imagem Pollinations Flux única por artigo — sem download, hospedada no CDN deles."""
    scene = _ARTICLE_SCENES.get(category, "professional editorial news photography journalism")
    keywords = " ".join(w for w in title.split()[:5] if len(w) > 3)
    prompt = f"photorealistic editorial photo {keywords} {scene} 16:9 widescreen no text no words high quality"
    encoded = requests.utils.quote(prompt)
    seed = abs(hash(title + category)) % 99999
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&nologo=true&seed={seed}&model=flux"


# ── Category accent colours for OG image gradient ────────────
_CAT_COLORS = {
    "world":         ((8, 12, 23),   (13, 26, 58)),
    "politics":      ((20, 10, 40),  (45, 15, 80)),
    "war":           ((30, 10, 10),  (70, 20, 20)),
    "business":      ((5, 20, 40),   (10, 40, 80)),
    "science":       ((5, 30, 45),   (10, 60, 90)),
    "health":        ((5, 35, 25),   (10, 70, 50)),
    "food":          ((40, 20, 5),   (80, 45, 10)),
    "sports":        ((10, 25, 5),   (20, 55, 10)),
    "entertainment": ((40, 10, 35),  (80, 20, 70)),
    "environment":   ((5, 35, 10),   (10, 70, 20)),
    "travel":        ((5, 25, 40),   (10, 55, 80)),
    "technology":    ((5, 15, 40),   (10, 30, 80)),
    "ai":            ((10, 5, 50),   (20, 10, 100)),
    "security":      ((5, 20, 30),   (10, 40, 60)),
    "gadgets":       ((10, 20, 30),  (20, 45, 65)),
    "startups":      ((30, 15, 5),   (65, 35, 10)),
    "mobile":        ((5, 20, 35),   (10, 45, 70)),
}


def _to_webp(img_path: "Path") -> "Path | None":
    """Convert an image file to WebP quality=82, method=6. Returns new .webp path or None on failure."""
    try:
        from PIL import Image as _PILImage
        webp_path = img_path.with_suffix(".webp")
        with _PILImage.open(img_path) as im:
            im = im.convert("RGB")
            # Only resize if image is at least 400px wide; cap at 1200x630
            if im.width >= 400:
                im.thumbnail((1200, 630), _PILImage.LANCZOS)
            im.save(str(webp_path), "WEBP", quality=82, method=6)
        # Remove original jpg if conversion succeeded and they differ
        if webp_path != img_path and img_path.exists():
            img_path.unlink()
        return webp_path
    except Exception as exc:
        log.debug(f"WebP conversion failed: {exc}")
        return None


def _generate_og_image(title: str, category: str, slug: str) -> str:
    """
    Generates a local OG image for the post using Pillow.
    Downloads background from Pollinations, overlays title + branding.
    Saves as WebP to assets/images/posts/SLUG.webp.
    Returns relative path /assets/images/posts/SLUG.webp, or falls back to Pollinations URL.
    Returns immediately if the image already exists on disk (cache hit).
    """
    fallback = _news_image_url(title, category)
    out_dir = Path("assets/images/posts")
    cached_path = out_dir / f"{slug}.webp"
    if cached_path.exists() and cached_path.stat().st_size > 1000:
        return f"/assets/images/posts/{slug}.webp"

    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        out_dir.mkdir(parents=True, exist_ok=True)

        # ── Download background image from Pollinations ──────────
        bg_img = None
        try:
            r = _session.get(fallback, timeout=20, stream=True)
            r.raise_for_status()
            raw = b"".join(r.iter_content(chunk_size=16384))
            bg_img = Image.open(io.BytesIO(raw)).convert("RGB")
            bg_img = bg_img.resize((1200, 630), Image.LANCZOS)
        except Exception:
            pass

        if bg_img is None:
            # Gradient fallback
            bg_img = Image.new("RGB", (1200, 630))
            draw_bg = ImageDraw.Draw(bg_img)
            c1, c2 = _CAT_COLORS.get(category, ((8, 12, 23), (13, 26, 58)))
            for y in range(630):
                t = y / 630
                r_c = int(c1[0] + (c2[0] - c1[0]) * t)
                g_c = int(c1[1] + (c2[1] - c1[1]) * t)
                b_c = int(c1[2] + (c2[2] - c1[2]) * t)
                draw_bg.line([(0, y), (1200, y)], fill=(r_c, g_c, b_c))

        draw = ImageDraw.Draw(bg_img)

        # ── Fonts: try DejaVu (common on Linux/CI), fall back to Pillow default ─
        try:
            font_title = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_cat   = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
            font_brand = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except Exception:
            try:
                font_title = ImageFont.load_default(size=36)
                font_cat   = ImageFont.load_default(size=22)
                font_brand = ImageFont.load_default(size=18)
            except TypeError:
                font_title = ImageFont.load_default()
                font_cat   = font_title
                font_brand = font_title

        # ── Logo "GlobalBR News" — top-left corner ───────────────
        draw.text((20, 18), "GlobalBR News", font=font_brand,
                  fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0))

        # ── Semi-transparent overlay on bottom 40% only ──────────
        overlay_top = int(bg_img.height * 6 // 10)
        overlay = Image.new("RGBA", bg_img.size, (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        ov_draw.rectangle(
            [(0, overlay_top), (bg_img.width, bg_img.height)],
            fill=(0, 0, 0, 160),
        )
        bg_img = Image.alpha_composite(bg_img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(bg_img)

        # ── Category label above the title ───────────────────────
        cat_text = category.upper()
        cat_y = overlay_top + 14
        draw.text((20, cat_y), cat_text, font=font_cat, fill=(249, 115, 22),
                  stroke_width=1, stroke_fill=(0, 0, 0))

        # ── Title text wrapped, max 2 lines ──────────────────────
        max_w = bg_img.width - 40
        words = title.split()
        lines: list = []
        current_line: list = []
        for word in words:
            test = " ".join(current_line + [word])
            try:
                w = draw.textlength(test, font=font_title)
            except AttributeError:
                w = len(test) * 20  # rough fallback for older Pillow
            if w > max_w and current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        if current_line:
            lines.append(" ".join(current_line))
        lines = lines[-2:]  # max 2 lines

        y = bg_img.height - 85
        for ln in lines:
            draw.text((20, y), ln, font=font_title, fill=(255, 255, 255),
                      stroke_width=2, stroke_fill=(0, 0, 0))
            y += 42

        # ── Resize to max 1200x630 before saving (only if >= 400px wide) ─
        if bg_img.width >= 400:
            bg_img.thumbnail((1200, 630), Image.LANCZOS)

        # ── Save as JPG first, then convert to WebP ──────────────
        jpg_path = out_dir / f"{slug}.jpg"
        bg_img.save(str(jpg_path), "JPEG", quality=82, optimize=True)

        webp_path = _to_webp(jpg_path)
        final_local = str(webp_path) if (webp_path and webp_path.exists()) else (str(jpg_path) if jpg_path.exists() else None)
        local_url = f"/assets/images/posts/{slug}.webp" if (webp_path and webp_path.exists()) else (f"/assets/images/posts/{slug}.jpg" if jpg_path.exists() else fallback)

        return local_url

    except ImportError:
        log.debug("Pillow not available — using Pollinations URL for OG image")
        return fallback
    except Exception as exc:
        log.warning(f"OG image generation failed ({exc}) — falling back to Pollinations URL")
        return fallback


def _validate_image_url(url: str) -> bool:
    """
    Return True iff `url` actually serves a usable image (≥5KB, image/* MIME,
    HTTP 200). For local /assets/... paths we trust the disk write that
    produced them. Used by the post pipeline to refuse publishing without a
    real cover — better to drop the post than ship a thumbnail-less card.
    """
    if not url:
        return False
    if url.startswith("/assets/"):
        # Local-on-disk path was just written by _generate_og_image — trust it.
        p = Path("." + url) if url.startswith("/") else Path(url)
        try:
            return p.exists() and p.stat().st_size >= 5 * 1024
        except OSError:
            return False
    if not url.startswith(("http://", "https://")):
        return False
    try:
        # HEAD first — most CDNs honour it and we don't want to pull MB.
        r = _session.head(url, timeout=10, allow_redirects=True)
        if r.status_code == 405 or r.status_code in (403, 401):
            # Some hosts reject HEAD; try GET with stream.
            r = _session.get(url, timeout=10, stream=True)
        if r.status_code != 200:
            return False
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "image/" not in ctype and "octet-stream" not in ctype:
            return False
        clen = r.headers.get("Content-Length")
        if clen and clen.isdigit() and int(clen) < 5 * 1024:
            return False
        return True
    except Exception:
        return False


def _ai_enhance_post(title: str, description: str, body: str, category: str, source_name: str) -> dict:
    """
    Gera conteúdo SEO-otimizado por artigo via AI.
    Retorna dict com: seo_title, meta_description, article_body, faq, keywords, key_points.
    Also fetches Wikipedia summary and stores it under 'wikipedia_summary'.
    """
    combined = f"{description}\n\n{body}".strip()[:2000]
    cat = category.capitalize()
    prompt = (
        f'You are a world-class AP-style SEO journalist. Enhance this news article for maximum search visibility and reader engagement. '
        f'Respond ONLY with valid JSON. No markdown, no code blocks, no extra text.\n\n'
        f'Title: {title}\nCategory: {cat}\nSource: {source_name}\nContent:\n{combined}\n\n'
        f'Return this exact JSON structure:\n'
        f'{{'
        f'"seo_title": "Informative headline max 65 chars. Use numbers when helpful. Create mild intrigue but stay factual. NEVER use clickbait. Must be searchable and match search intent.",'
        f'"meta_description": "150-160 chars. Start with the main fact or benefit. Include the primary keyword naturally. End with a period. Sound human, not robotic. AVOID: In this article, Learn how, Explore. EXAMPLE: Scientists confirm new drug cuts dementia risk by 40% in landmark UK 10-year trial of 40000 patients.",'
        f'"lead": "One tight paragraph 40-50 words answering Who What When Where Why — classic journalistic inverted pyramid lead. Include the single most important fact.",'
        f'"tl_dr": "One sentence max 25 words starting with an active verb — perfect for featured snippets. EXAMPLE: UK scientists confirm new drug halves dementia risk in 10-year trial of 40000 patients.",'
        f'"content_type": "one of: news|breaking|analysis|explainer|opinion|feature",'
        f'"key_points": ["Action-verb sentence max 12 words key fact 1", "Action-verb sentence max 12 words key fact 2", "Action-verb sentence max 12 words key fact 3"],'
        f'"article_body": "Write 5-7 journalistic paragraphs, 550-700 words total. Follow inverted pyramid: most critical facts first. Add an ## H2 heading every 2 paragraphs. For key people/organizations/places add Wikipedia links: [Name](https://en.wikipedia.org/wiki/Name). Final paragraph: what happens next or broader implications. AP style. No bullet points.",'
        f'"image_caption": "One descriptive sentence about what the article image likely shows. Relevant, specific, mentions key person or location if applicable.",'
        f'"faq": ['
        f'{{"q": "Question starting with What/Why/How/When/Who — mirrors Google People Also Ask format", "a": "Direct answer 40-60 words plain prose."}},'
        f'{{"q": "Second PAA-style question", "a": "Direct answer 40-60 words."}},'
        f'{{"q": "Third PAA-style question", "a": "Direct answer 40-60 words."}},'
        f'{{"q": "Fourth PAA-style question", "a": "Direct answer 40-60 words."}},'
        f'{{"q": "Fifth PAA-style question", "a": "Direct answer 40-60 words."}}'
        f'],'
        f'"keywords": ["primary keyword matching title", "second primary keyword", "LSI term 1", "LSI term 2", "LSI term 3", "long tail phrase 4-6 words", "second long tail phrase", "third long tail phrase"],'
        f'"entities": ["Person Name or Organization or Place 1", "Entity 2", "Entity 3"],'
        f'"hook": "One punchy sentence max 20 words — journalistic hook, creates curiosity without clickbait"'
        f'}}'
    )
    raw = _ai_text(prompt, seed=abs(hash(title)) % 9999, timeout=25)
    result = {}
    if raw:
        try:
            clean = re.sub(r'```(?:json)?\s*|\s*```', '', raw).strip()
            # Find outermost JSON object — scan for matching braces
            start = clean.find('{')
            if start >= 0:
                depth = 0
                end = start
                for i, ch in enumerate(clean[start:], start):
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                candidate = clean[start:end + 1]
                # strict=False allows raw control chars (newlines, tabs)
                # inside string values. Mistral often writes multi-paragraph
                # article_body with literal \n instead of escaped \\n.
                try:
                    result = json.loads(candidate, strict=False)
                except json.JSONDecodeError:
                    # LLMs occasionally return a Python repr (single quotes)
                    # instead of JSON. Try literal_eval as a fallback.
                    try:
                        import ast as _ast
                        parsed = _ast.literal_eval(candidate)
                        if isinstance(parsed, dict):
                            result = parsed
                        else:
                            result = json.loads(clean, strict=False)
                    except (ValueError, SyntaxError):
                        result = json.loads(clean, strict=False)
        except Exception as e:
            log.warning(f"AI enhance parse error: {e} | raw[:120]={raw[:120]}")

    # ── Wikipedia enrichment ──────────────────────────────────
    # Skip the Wikipedia round-trip when the AI already produced a
    # rich body — Wikipedia exists to backfill thin posts, not to
    # duplicate a 600-word article. Costs ~2-3s per skip.
    ai_body = result.get("article_body") or ""
    if not isinstance(ai_body, str) or len(ai_body) < 500:
        wiki_summary = _fetch_wikipedia_summary(title)
        if wiki_summary:
            result["wikipedia_summary"] = wiki_summary

    return result

# ============================================================
# CONFIGURAÇÕES
# ============================================================

POSTS_DIR        = Path("_posts")
LOG_FILE         = "fetch_news.log"
MAX_PER_FEED     = int(os.environ.get("FETCH_MAX_PER_FEED", "4"))     # Max posts por feed por execução
MAX_POSTS_PER_RUN = int(os.environ.get("FETCH_MAX_PER_RUN", "50"))   # Limite global por execução (muitos feeds agora)
REQUEST_TIMEOUT  = 15
# Sleep was 2s × 135 feeds = 270s of pure waiting per run. Dropped
# to 0 — feeds are now processed in parallel (see fetch_feeds_concurrent),
# and the per-host rate-limiting is handled implicitly by requests.Session
# connection pool. Override with FETCH_SLEEP_BETWEEN_FEEDS=2 if needed.
SLEEP_BETWEEN_FEEDS = float(os.environ.get("FETCH_SLEEP_BETWEEN_FEEDS", "0"))
# Cap on concurrent feeds. 10 is a polite default: most CDNs allow it
# without throttling and we still cut total fetch time by ~7×.
FEED_WORKERS = int(os.environ.get("FETCH_FEED_WORKERS", "10"))
MIN_DESCRIPTION_LEN = 80              # Descrição mínima para publicar

# Feeds RSS configurados
FEEDS = [
    # ── World News ────────────────────────────────────────────
    {
        "name":     "BBC News World",
        "url":      "https://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "world",
        "tags":     ["bbc", "world-news", "international"],
        "source":   "BBC News",
    },
    {
        "name":     "Al Jazeera",
        "url":      "https://www.aljazeera.com/xml/rss/all.xml",
        "category": "world",
        "tags":     ["aljazeera", "world-news", "middle-east"],
        "source":   "Al Jazeera",
    },
    {
        "name":     "The Guardian World",
        "url":      "https://www.theguardian.com/world/rss",
        "category": "world",
        "tags":     ["guardian", "world-news", "international"],
        "source":   "The Guardian",
    },
    {
        "name":     "Deutsche Welle",
        "url":      "https://rss.dw.com/rdf/rss-en-all",
        "category": "world",
        "tags":     ["dw", "europe", "world-news"],
        "source":   "Deutsche Welle",
    },
    {
        "name":     "France 24",
        "url":      "https://www.france24.com/en/rss",
        "category": "world",
        "tags":     ["france24", "world-news", "europe"],
        "source":   "France 24",
    },
    {
        "name":     "Reuters",
        "url":      "https://feeds.reuters.com/reuters/topNews",
        "category": "world",
        "tags":     ["reuters", "world-news", "breaking"],
        "source":   "Reuters",
    },
    {
        "name":     "NPR News",
        "url":      "https://feeds.npr.org/1001/rss.xml",
        "category": "world",
        "tags":     ["npr", "usa", "world-news"],
        "source":   "NPR",
    },
    {
        "name":     "Euronews",
        "url":      "https://feeds.feedburner.com/euronews/en/news",
        "category": "world",
        "tags":     ["euronews", "europe", "world-news"],
        "source":   "Euronews",
    },
    # ── Politics ──────────────────────────────────────────────
    {
        "name":     "The Guardian Politics",
        "url":      "https://www.theguardian.com/politics/rss",
        "category": "politics",
        "tags":     ["guardian", "politics", "uk"],
        "source":   "The Guardian",
    },
    {
        "name":     "Foreign Policy",
        "url":      "https://foreignpolicy.com/feed/",
        "category": "politics",
        "tags":     ["foreign-policy", "geopolitics", "diplomacy"],
        "source":   "Foreign Policy",
    },
    {
        "name":     "Politico",
        "url":      "https://rss.politico.com/politics-news.xml",
        "category": "politics",
        "tags":     ["politico", "politics", "usa"],
        "source":   "Politico",
    },
    {
        "name":     "BBC Politics",
        "url":      "https://feeds.bbci.co.uk/news/politics/rss.xml",
        "category": "politics",
        "tags":     ["bbc", "politics", "uk"],
        "source":   "BBC News",
    },
    # ── War / Defense / Conflict ──────────────────────────────
    {
        "name":     "War on the Rocks",
        "url":      "https://warontherocks.com/feed/",
        "category": "war",
        "tags":     ["defense", "military", "geopolitics"],
        "source":   "War on the Rocks",
    },
    {
        "name":     "Defense News",
        "url":      "https://www.defensenews.com/arc/outboundfeeds/rss/",
        "category": "war",
        "tags":     ["defense", "military", "pentagon"],
        "source":   "Defense News",
    },
    {
        "name":     "The Drive — War Zone",
        "url":      "https://www.thedrive.com/the-war-zone/rss",
        "category": "war",
        "tags":     ["military", "weapons", "conflict"],
        "source":   "The Drive",
    },
    {
        "name":     "Al Jazeera Conflicts",
        "url":      "https://www.aljazeera.com/xml/rss/all.xml",
        "category": "war",
        "tags":     ["conflict", "war", "aljazeera"],
        "source":   "Al Jazeera",
    },
    # ── Business / Finance ────────────────────────────────────
    {
        "name":     "CNBC",
        "url":      "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "category": "business",
        "tags":     ["cnbc", "finance", "economy"],
        "source":   "CNBC",
    },
    {
        "name":     "MarketWatch",
        "url":      "https://feeds.marketwatch.com/marketwatch/topstories/",
        "category": "business",
        "tags":     ["marketwatch", "stocks", "finance"],
        "source":   "MarketWatch",
    },
    {
        "name":     "Fortune",
        "url":      "https://fortune.com/feed/",
        "category": "business",
        "tags":     ["fortune", "business", "economy"],
        "source":   "Fortune",
    },
    {
        "name":     "The Guardian Business",
        "url":      "https://www.theguardian.com/business/rss",
        "category": "business",
        "tags":     ["guardian", "business", "economy"],
        "source":   "The Guardian",
    },
    {
        "name":     "BBC Business",
        "url":      "https://feeds.bbci.co.uk/news/business/rss.xml",
        "category": "business",
        "tags":     ["bbc", "business", "economy"],
        "source":   "BBC News",
    },
    # ── Science ───────────────────────────────────────────────
    {
        "name":     "NASA News",
        "url":      "https://www.nasa.gov/feed/",
        "category": "science",
        "tags":     ["nasa", "space", "science"],
        "source":   "NASA",
    },
    {
        "name":     "Scientific American",
        "url":      "https://www.scientificamerican.com/feed/rss/",
        "category": "science",
        "tags":     ["science", "research", "discovery"],
        "source":   "Scientific American",
    },
    {
        "name":     "New Scientist",
        "url":      "https://www.newscientist.com/feed/",
        "category": "science",
        "tags":     ["science", "research", "physics"],
        "source":   "New Scientist",
    },
    {
        "name":     "Space.com",
        "url":      "https://www.space.com/feeds/all",
        "category": "science",
        "tags":     ["space", "astronomy", "nasa"],
        "source":   "Space.com",
    },
    {
        "name":     "ScienceAlert",
        "url":      "https://www.sciencealert.com/feed",
        "category": "science",
        "tags":     ["science", "biology", "chemistry"],
        "source":   "ScienceAlert",
    },
    # ── Health ────────────────────────────────────────────────
    {
        "name":     "Medical News Today",
        "url":      "https://www.medicalnewstoday.com/rss",
        "category": "health",
        "tags":     ["health", "medicine", "medical"],
        "source":   "Medical News Today",
    },
    {
        "name":     "Healthline",
        "url":      "https://www.healthline.com/rss/health-news",
        "category": "health",
        "tags":     ["health", "wellness", "medicine"],
        "source":   "Healthline",
    },
    {
        "name":     "BBC Health",
        "url":      "https://feeds.bbci.co.uk/news/health/rss.xml",
        "category": "health",
        "tags":     ["bbc", "health", "medicine"],
        "source":   "BBC News",
    },
    {
        "name":     "WHO News",
        "url":      "https://www.who.int/feeds/entity/news/en/rss.xml",
        "category": "health",
        "tags":     ["who", "global-health", "pandemic"],
        "source":   "WHO",
    },
    # ── Food / Cooking ────────────────────────────────────────
    {
        "name":     "Serious Eats",
        "url":      "https://www.seriouseats.com/feeds/all",
        "category": "food",
        "tags":     ["food", "cooking", "recipes"],
        "source":   "Serious Eats",
    },
    {
        "name":     "Eater",
        "url":      "https://www.eater.com/rss/index.xml",
        "category": "food",
        "tags":     ["food", "restaurants", "cuisine"],
        "source":   "Eater",
    },
    {
        "name":     "Food52",
        "url":      "https://food52.com/blog.rss",
        "category": "food",
        "tags":     ["food", "cooking", "recipes"],
        "source":   "Food52",
    },
    {
        "name":     "Bon Appétit",
        "url":      "https://www.bonappetit.com/feed/rss",
        "category": "food",
        "tags":     ["food", "cooking", "recipes"],
        "source":   "Bon Appétit",
    },
    # ── Sports ────────────────────────────────────────────────
    {
        "name":     "ESPN",
        "url":      "https://www.espn.com/espn/rss/news",
        "category": "sports",
        "tags":     ["espn", "sports", "nfl"],
        "source":   "ESPN",
    },
    {
        "name":     "BBC Sport",
        "url":      "https://feeds.bbci.co.uk/sport/rss.xml",
        "category": "sports",
        "tags":     ["bbc", "sports", "football"],
        "source":   "BBC Sport",
    },
    {
        "name":     "Sky Sports",
        "url":      "https://www.skysports.com/rss/12040",
        "category": "sports",
        "tags":     ["sky-sports", "football", "premier-league"],
        "source":   "Sky Sports",
    },
    {
        "name":     "Goal.com",
        "url":      "https://www.goal.com/feeds/en/news",
        "category": "sports",
        "tags":     ["football", "soccer", "transfers"],
        "source":   "Goal.com",
    },
    # ── Entertainment ─────────────────────────────────────────
    {
        "name":     "Variety",
        "url":      "https://variety.com/feed/",
        "category": "entertainment",
        "tags":     ["variety", "movies", "hollywood"],
        "source":   "Variety",
    },
    {
        "name":     "Hollywood Reporter",
        "url":      "https://www.hollywoodreporter.com/feed/",
        "category": "entertainment",
        "tags":     ["hollywood", "movies", "tv"],
        "source":   "Hollywood Reporter",
    },
    {
        "name":     "Rolling Stone",
        "url":      "https://www.rollingstone.com/feed/",
        "category": "entertainment",
        "tags":     ["music", "rolling-stone", "culture"],
        "source":   "Rolling Stone",
    },
    {
        "name":     "IGN",
        "url":      "https://www.ign.com/rss/articles",
        "category": "entertainment",
        "tags":     ["gaming", "ign", "movies"],
        "source":   "IGN",
    },
    # ── Environment / Climate ─────────────────────────────────
    {
        "name":     "The Guardian Environment",
        "url":      "https://www.theguardian.com/environment/rss",
        "category": "environment",
        "tags":     ["guardian", "climate", "environment"],
        "source":   "The Guardian",
    },
    {
        "name":     "Yale Environment 360",
        "url":      "https://e360.yale.edu/feeds/all",
        "category": "environment",
        "tags":     ["climate", "environment", "sustainability"],
        "source":   "Yale Environment 360",
    },
    {
        "name":     "BBC Science & Environment",
        "url":      "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "category": "environment",
        "tags":     ["bbc", "environment", "climate"],
        "source":   "BBC News",
    },
    # ── Travel ────────────────────────────────────────────────
    {
        "name":     "Lonely Planet",
        "url":      "https://www.lonelyplanet.com/feeds/latest",
        "category": "travel",
        "tags":     ["travel", "destinations", "tourism"],
        "source":   "Lonely Planet",
    },
    {
        "name":     "Travel + Leisure",
        "url":      "https://www.travelandleisure.com/feeds/all",
        "category": "travel",
        "tags":     ["travel", "luxury", "destinations"],
        "source":   "Travel + Leisure",
    },
    # ── Technology ────────────────────────────────────────────
    {
        "name":     "TechCrunch",
        "url":      "https://techcrunch.com/feed/",
        "category": "technology",
        "tags":     ["techcrunch", "startups", "tech"],
        "source":   "TechCrunch",
    },
    {
        "name":     "The Verge",
        "url":      "https://www.theverge.com/rss/index.xml",
        "category": "technology",
        "tags":     ["theverge", "gadgets", "reviews"],
        "source":   "The Verge",
    },
    {
        "name":     "Wired",
        "url":      "https://www.wired.com/feed/rss",
        "category": "technology",
        "tags":     ["wired", "tech", "science"],
        "source":   "Wired",
    },
    {
        "name":     "Ars Technica",
        "url":      "https://feeds.arstechnica.com/arstechnica/index",
        "category": "technology",
        "tags":     ["arstechnica", "tech", "science"],
        "source":   "Ars Technica",
    },
    {
        "name":     "Engadget",
        "url":      "https://www.engadget.com/rss.xml",
        "category": "gadgets",
        "tags":     ["engadget", "gadgets", "reviews"],
        "source":   "Engadget",
    },
    {
        "name":     "CNET",
        "url":      "https://www.cnet.com/rss/news/",
        "category": "technology",
        "tags":     ["cnet", "tech", "reviews"],
        "source":   "CNET",
    },
    # ── AI ────────────────────────────────────────────────────
    {
        "name":     "TechCrunch AI",
        "url":      "https://techcrunch.com/category/artificial-intelligence/feed/",
        "category": "ai",
        "tags":     ["techcrunch", "ai", "machine-learning"],
        "source":   "TechCrunch",
    },
    {
        "name":     "MIT Technology Review",
        "url":      "https://www.technologyreview.com/feed/",
        "category": "ai",
        "tags":     ["mit", "ai", "research"],
        "source":   "MIT Technology Review",
    },
    {
        "name":     "VentureBeat AI",
        "url":      "https://venturebeat.com/category/ai/feed/",
        "category": "ai",
        "tags":     ["venturebeat", "ai", "enterprise"],
        "source":   "VentureBeat",
    },
    # ── Startups ──────────────────────────────────────────────
    {
        "name":     "TechCrunch Startups",
        "url":      "https://techcrunch.com/category/startups/feed/",
        "category": "startups",
        "tags":     ["techcrunch", "startups", "venture-capital"],
        "source":   "TechCrunch",
    },
    {
        "name":     "VentureBeat",
        "url":      "https://venturebeat.com/feed/",
        "category": "startups",
        "tags":     ["venturebeat", "startups", "enterprise"],
        "source":   "VentureBeat",
    },
    # ── Security ──────────────────────────────────────────────
    {
        "name":     "Krebs on Security",
        "url":      "https://krebsonsecurity.com/feed/",
        "category": "security",
        "tags":     ["krebs", "security", "cybersecurity"],
        "source":   "Krebs on Security",
    },
    {
        "name":     "The Hacker News",
        "url":      "https://feeds.feedburner.com/TheHackersNews",
        "category": "security",
        "tags":     ["hackernews", "security", "vulnerabilities"],
        "source":   "The Hacker News",
    },
    # ── Developer / General Tech ──────────────────────────────
    {
        "name":     "Hacker News (Top)",
        "url":      "https://hnrss.org/frontpage",
        "category": "technology",
        "tags":     ["hackernews", "programming", "tech"],
        "source":   "Hacker News",
    },
    {
        "name":     "The Register",
        "url":      "https://www.theregister.com/headlines.atom",
        "category": "technology",
        "tags":     ["theregister", "tech", "enterprise"],
        "source":   "The Register",
    },
    # ── DEV.to (API nativa, sem chave obrigatória) ────────────
    {
        "name":     "DEV.to Programming",
        "url":      "__devto__programming",
        "category": "technology",
        "tags":     ["devto", "programming", "development"],
        "source":   "DEV.to",
    },
    {
        "name":     "DEV.to WebDev",
        "url":      "__devto__webdev",
        "category": "technology",
        "tags":     ["devto", "webdev", "javascript"],
        "source":   "DEV.to",
    },
    {
        "name":     "DEV.to Python",
        "url":      "__devto__python",
        "category": "technology",
        "tags":     ["devto", "python", "programming"],
        "source":   "DEV.to",
    },
    {
        "name":     "DEV.to AI",
        "url":      "__devto__ai",
        "category": "ai",
        "tags":     ["devto", "ai", "machine-learning"],
        "source":   "DEV.to",
    },
    # ── HackerNews (API nativa, sem chave) ───────────────────
    {
        "name":     "Hacker News API",
        "url":      "__hackernews__",
        "category": "technology",
        "tags":     ["hackernews", "tech", "programming"],
        "source":   "Hacker News",
    },
    # ── Additional World / International ─────────────────────
    {
        "name":     "AP News Top Stories",
        "url":      "https://rsshub.app/apnews/topics/apf-topnews",
        "category": "world",
        "tags":     ["ap-news", "world-news", "breaking"],
        "source":   "AP News",
    },
    {
        "name":     "RFI English",
        "url":      "https://www.rfi.fr/en/rss",
        "category": "world",
        "tags":     ["rfi", "france", "world-news"],
        "source":   "RFI",
    },
    {
        "name":     "South China Morning Post",
        "url":      "https://www.scmp.com/rss/91/feed",
        "category": "world",
        "tags":     ["scmp", "asia", "china", "world-news"],
        "source":   "SCMP",
    },
    {
        "name":     "Times of India — World",
        "url":      "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
        "category": "world",
        "tags":     ["india", "asia", "world-news"],
        "source":   "Times of India",
    },
    # ── Additional Business ───────────────────────────────────
    {
        "name":     "MarketWatch",
        "url":      "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
        "category": "business",
        "tags":     ["marketwatch", "finance", "markets"],
        "source":   "MarketWatch",
    },
    {
        "name":     "Financial Times (Free)",
        "url":      "https://www.ft.com/rss/home",
        "category": "business",
        "tags":     ["ft", "finance", "economy"],
        "source":   "Financial Times",
    },
    # ── Additional Science ────────────────────────────────────
    {
        "name":     "Phys.org",
        "url":      "https://phys.org/rss-feed/",
        "category": "science",
        "tags":     ["physics", "science", "research"],
        "source":   "Phys.org",
    },
    {
        "name":     "EurekAlert",
        "url":      "https://www.eurekalert.org/rss.xml",
        "category": "science",
        "tags":     ["science", "research", "discovery"],
        "source":   "EurekAlert",
    },
    # ── Additional Health ─────────────────────────────────────
    {
        "name":     "MedPage Today",
        "url":      "https://www.medpagetoday.com/rss/headlines.xml",
        "category": "health",
        "tags":     ["medicine", "health", "clinical"],
        "source":   "MedPage Today",
    },
    # ── Additional Environment ────────────────────────────────
    {
        "name":     "Carbon Brief",
        "url":      "https://www.carbonbrief.org/feed",
        "category": "environment",
        "tags":     ["climate", "environment", "carbon"],
        "source":   "Carbon Brief",
    },
    {
        "name":     "Inside Climate News",
        "url":      "https://insideclimatenews.org/feed/",
        "category": "environment",
        "tags":     ["climate", "environment", "energy"],
        "source":   "Inside Climate News",
    },
    # ── Additional AI ─────────────────────────────────────────
    {
        "name":     "OpenAI Blog",
        "url":      "https://openai.com/blog/rss.xml",
        "category": "ai",
        "tags":     ["openai", "ai", "gpt"],
        "source":   "OpenAI",
    },
    {
        "name":     "Google DeepMind Blog",
        "url":      "https://deepmind.google/blog/rss.xml",
        "category": "ai",
        "tags":     ["deepmind", "ai", "research"],
        "source":   "Google DeepMind",
    },
    {
        "name":     "Import AI (Jack Clark)",
        "url":      "https://importai.substack.com/feed",
        "category": "ai",
        "tags":     ["ai", "newsletter", "research"],
        "source":   "Import AI",
    },
    # ── Additional Sports ─────────────────────────────────────
    {
        "name":     "BBC Sport",
        "url":      "https://feeds.bbci.co.uk/sport/rss.xml",
        "category": "sports",
        "tags":     ["bbc", "sports", "football"],
        "source":   "BBC Sport",
    },
    {
        "name":     "Sky Sports",
        "url":      "https://www.skysports.com/rss/12040",
        "category": "sports",
        "tags":     ["sky-sports", "football", "sports"],
        "source":   "Sky Sports",
    },
    # ── Security ──────────────────────────────────────────────
    {
        "name":     "Dark Reading",
        "url":      "https://www.darkreading.com/rss.xml",
        "category": "security",
        "tags":     ["cybersecurity", "hacking", "infosec"],
        "source":   "Dark Reading",
    },
    {
        "name":     "Krebs on Security",
        "url":      "https://krebsonsecurity.com/feed/",
        "category": "security",
        "tags":     ["cybersecurity", "krebs", "infosec"],
        "source":   "Krebs on Security",
    },
    {
        "name":     "The Hacker News",
        "url":      "https://feeds.feedburner.com/TheHackersNews",
        "category": "security",
        "tags":     ["cybersecurity", "hacking", "vulnerability"],
        "source":   "The Hacker News",
    },

    # ── Expanded global / regional desk ──────────────────────────
    {"name": "Reuters World", "url": "https://www.reutersagency.com/feed/?best-topics=world&post_type=best", "category": "world", "tags": ["reuters", "world"], "source": "Reuters"},
    {"name": "AP Top Stories", "url": "https://feeds.apnews.com/rss/apf-topnews", "category": "world", "tags": ["ap", "world"], "source": "Associated Press"},
    {"name": "DW World", "url": "https://rss.dw.com/atom/rss-en-world", "category": "world", "tags": ["dw", "europe"], "source": "Deutsche Welle"},
    {"name": "France 24 World", "url": "https://www.france24.com/en/rss", "category": "world", "tags": ["france24", "europe"], "source": "France 24"},
    {"name": "Al Jazeera World", "url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "world", "tags": ["aljazeera", "middle-east"], "source": "Al Jazeera"},
    {"name": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml", "category": "world", "tags": ["npr", "us"], "source": "NPR"},
    {"name": "Reuters Africa", "url": "https://www.reutersagency.com/feed/?best-regions=africa&post_type=best", "category": "world", "tags": ["africa", "reuters"], "source": "Reuters"},
    {"name": "Reuters Asia", "url": "https://www.reutersagency.com/feed/?best-regions=asia&post_type=best", "category": "world", "tags": ["asia", "reuters"], "source": "Reuters"},
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss/feed/nar", "category": "world", "tags": ["asia", "nikkei"], "source": "Nikkei Asia"},
    {"name": "SCMP World", "url": "https://www.scmp.com/rss/91/feed", "category": "world", "tags": ["china", "asia"], "source": "South China Morning Post"},

    # ── Politics extra ───────────────────────────────────────────
    {"name": "Politico", "url": "https://www.politico.com/rss/politicopicks.xml", "category": "politics", "tags": ["politico", "us-politics"], "source": "Politico"},
    {"name": "The Hill", "url": "https://thehill.com/feed", "category": "politics", "tags": ["thehill", "us"], "source": "The Hill"},
    {"name": "Foreign Policy", "url": "https://foreignpolicy.com/feed/", "category": "politics", "tags": ["foreign-policy", "diplomacy"], "source": "Foreign Policy"},

    # ── War / conflict ───────────────────────────────────────────
    {"name": "Defense News", "url": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", "category": "war", "tags": ["defense", "military"], "source": "Defense News"},
    {"name": "War on the Rocks", "url": "https://warontherocks.com/feed/", "category": "war", "tags": ["war-on-the-rocks", "conflict"], "source": "War on the Rocks"},
    {"name": "Kyiv Independent", "url": "https://kyivindependent.com/rss/", "category": "war", "tags": ["ukraine", "war"], "source": "Kyiv Independent"},

    # ── Business / Economy ───────────────────────────────────────
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "category": "business", "tags": ["reuters", "business"], "source": "Reuters"},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "category": "business", "tags": ["bloomberg", "markets"], "source": "Bloomberg"},
    {"name": "Financial Times World", "url": "https://www.ft.com/rss/home/international", "category": "business", "tags": ["ft", "world"], "source": "Financial Times"},
    {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "category": "business", "tags": ["cnbc", "markets"], "source": "CNBC"},

    # ── Science / Health ─────────────────────────────────────────
    {"name": "NASA Breaking", "url": "https://www.nasa.gov/news-release/feed/", "category": "science", "tags": ["nasa", "space"], "source": "NASA"},
    {"name": "Nature News", "url": "https://www.nature.com/nature.rss", "category": "science", "tags": ["nature", "research"], "source": "Nature"},
    {"name": "Scientific American", "url": "https://www.scientificamerican.com/feed/", "category": "science", "tags": ["scientific-american"], "source": "Scientific American"},
    {"name": "STAT Health", "url": "https://www.statnews.com/feed/", "category": "health", "tags": ["statnews", "medicine"], "source": "STAT News"},
    {"name": "NEJM This Week", "url": "https://www.nejm.org/action/showFeed?type=etoc&feed=rss&jc=nejm", "category": "health", "tags": ["nejm", "medicine"], "source": "New England Journal of Medicine"},
    {"name": "WHO News", "url": "https://www.who.int/feeds/entity/news/en/rss.xml", "category": "health", "tags": ["who", "public-health"], "source": "World Health Organization"},

    # ── Environment / Climate ────────────────────────────────────
    {"name": "Inside Climate News", "url": "https://insideclimatenews.org/feed/", "category": "environment", "tags": ["climate"], "source": "Inside Climate News"},
    {"name": "Grist", "url": "https://grist.org/feed/", "category": "environment", "tags": ["climate", "grist"], "source": "Grist"},
    {"name": "Climate Central", "url": "https://www.climatecentral.org/rss/feed", "category": "environment", "tags": ["climate"], "source": "Climate Central"},

    # ── Tech / AI / Startups ─────────────────────────────────────
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "category": "technology", "tags": ["mit", "tech-review"], "source": "MIT Technology Review"},
    {"name": "IEEE Spectrum", "url": "https://spectrum.ieee.org/feeds/feed.rss", "category": "technology", "tags": ["ieee", "engineering"], "source": "IEEE Spectrum"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "category": "ai", "tags": ["ai", "venturebeat"], "source": "VentureBeat"},
    {"name": "DeepMind Blog", "url": "https://deepmind.com/blog/feed/basic/", "category": "ai", "tags": ["deepmind", "ai-research"], "source": "DeepMind"},
    {"name": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml", "category": "ai", "tags": ["openai", "ai-research"], "source": "OpenAI"},
    {"name": "Anthropic Blog", "url": "https://www.anthropic.com/news/rss.xml", "category": "ai", "tags": ["anthropic", "ai-safety"], "source": "Anthropic"},

    # ── Mobile / Gadgets ─────────────────────────────────────────
    {"name": "9to5Mac", "url": "https://9to5mac.com/feed/", "category": "mobile", "tags": ["apple", "iphone"], "source": "9to5Mac"},
    {"name": "9to5Google", "url": "https://9to5google.com/feed/", "category": "mobile", "tags": ["google", "android"], "source": "9to5Google"},
    {"name": "Android Authority", "url": "https://www.androidauthority.com/feed/", "category": "mobile", "tags": ["android"], "source": "Android Authority"},

    # ── Sports ───────────────────────────────────────────────────
    {"name": "ESPN Top Headlines", "url": "https://www.espn.com/espn/rss/news", "category": "sports", "tags": ["espn"], "source": "ESPN"},
    {"name": "BBC Sport", "url": "http://feeds.bbci.co.uk/sport/rss.xml", "category": "sports", "tags": ["bbc-sport"], "source": "BBC Sport"},

    # ── Entertainment / Culture ──────────────────────────────────
    {"name": "Variety", "url": "https://variety.com/feed/", "category": "entertainment", "tags": ["variety", "hollywood"], "source": "Variety"},
    {"name": "Hollywood Reporter", "url": "https://www.hollywoodreporter.com/feed/", "category": "entertainment", "tags": ["hollywood"], "source": "The Hollywood Reporter"},
    {"name": "Pitchfork", "url": "https://pitchfork.com/rss/news/", "category": "entertainment", "tags": ["pitchfork", "music"], "source": "Pitchfork"},

    # ── Food / Travel ────────────────────────────────────────────
    {"name": "Eater Latest", "url": "https://www.eater.com/rss/index.xml", "category": "food", "tags": ["eater"], "source": "Eater"},
    {"name": "Bon Appétit", "url": "https://www.bonappetit.com/feed/rss", "category": "food", "tags": ["bonappetit"], "source": "Bon Appétit"},
    {"name": "Lonely Planet News", "url": "https://www.lonelyplanet.com/news/feed", "category": "travel", "tags": ["lonelyplanet"], "source": "Lonely Planet"},

    # ── Security extras ──────────────────────────────────────────
    {"name": "Bleeping Computer", "url": "https://www.bleepingcomputer.com/feed/", "category": "security", "tags": ["bleepingcomputer", "malware"], "source": "Bleeping Computer"},
    {"name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml", "category": "security", "tags": ["dark-reading", "infosec"], "source": "Dark Reading"},
    {"name": "Schneier on Security", "url": "https://www.schneier.com/feed/atom/", "category": "security", "tags": ["schneier", "cryptography"], "source": "Schneier on Security"},
]


# ============================================================
# EXTRA SOURCES — HackerNews, DEV.to
# ============================================================

def fetch_hackernews(max_items: int = 20, min_score: int = 100) -> list[dict]:
    """
    Fetches HackerNews top stories via the official Firebase API.
    Returns a list of article dicts compatible with the post pipeline.
    No API key required.
    """
    items = []
    try:
        r = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=15,
            headers={"User-Agent": "GlobalBRNews/1.0"},
        )
        if r.status_code != 200:
            return items
        story_ids = r.json()[:50]  # fetch first 50, filter by score below
    except Exception as exc:
        log.warning(f"HackerNews topstories fetch failed: {exc}")
        return items

    fetched = 0
    for story_id in story_ids:
        if fetched >= max_items:
            break
        try:
            ri = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=10,
                headers={"User-Agent": "GlobalBRNews/1.0"},
            )
            if ri.status_code != 200:
                continue
            data = ri.json()
            if not data or data.get("type") != "story":
                continue
            score = data.get("score", 0)
            if score < min_score:
                continue
            title = sanitize_text(data.get("title", ""))
            url = data.get("url", "")
            if not title or not url:
                continue
            pub_date = datetime.fromtimestamp(data.get("time", 0), tz=timezone.utc)
            items.append({
                "title": title,
                "link": url,
                "description": f"HackerNews score: {score}. {title}",
                "pub_date": pub_date,
                "image_url": "",
                "category": "technology",
                "tags": ["hackernews", "programming", "tech"],
                "source": "Hacker News",
                "hn_score": score,
            })
            fetched += 1
        except Exception as exc:
            log.debug(f"HackerNews item {story_id} fetch failed: {exc}")
            continue
    log.info(f"HackerNews: {len(items)} stories fetched (min_score={min_score})")
    return items


def fetch_devto(tags: list | None = None, per_page: int = 20) -> list[dict]:
    """
    Fetches articles from DEV.to API.
    Uses DEV_TO_API_KEY if available; works without it too.
    Returns list of article dicts compatible with the post pipeline.
    """
    if tags is None:
        tags = ["programming", "webdev", "javascript", "python", "ai"]
    api_key = os.getenv("DEV_TO_API_KEY", "")
    headers = {"User-Agent": "GlobalBRNews/1.0"}
    if api_key:
        headers["api-key"] = api_key

    items = []
    seen_links: set = set()

    for tag in tags:
        try:
            r = requests.get(
                f"https://dev.to/api/articles?per_page={per_page}&tag={requests.utils.quote(tag)}",
                headers=headers,
                timeout=15,
            )
            if r.status_code != 200:
                log.debug(f"DEV.to tag '{tag}' returned HTTP {r.status_code}")
                continue
            articles = r.json()
            for art in articles:
                link = art.get("url", "")
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                title = sanitize_text(art.get("title", ""))
                description = sanitize_text((art.get("description") or art.get("title", ""))[:400])
                if not title or not link:
                    continue
                pub_str = art.get("published_at", "")
                try:
                    pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    pub_date = datetime.now(timezone.utc)
                image_url = art.get("cover_image") or art.get("social_image") or ""
                art_tags = ["devto", "programming", tag]
                devto_tags = art.get("tag_list", [])
                if devto_tags:
                    art_tags += [t.lower() for t in devto_tags[:3]]
                items.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "pub_date": pub_date,
                    "image_url": image_url,
                    "category": "technology",
                    "tags": list(dict.fromkeys(art_tags)),
                    "source": "DEV.to",
                })
        except Exception as exc:
            log.warning(f"DEV.to tag '{tag}' fetch error: {exc}")
            continue

    log.info(f"DEV.to: {len(items)} articles fetched across {len(tags)} tags")
    return items


# ============================================================
# KEYWORD → CATEGORY / TAG MAPPING
# ============================================================

KEYWORD_CATEGORIES: dict[str, tuple[str, list]] = {
    # AI / Machine Learning
    "artificial intelligence": ("ai",          ["ai", "machine-learning"]),
    "machine learning":        ("ai",          ["ai", "machine-learning"]),
    "deep learning":           ("ai",          ["ai", "deep-learning"]),
    "neural network":          ("ai",          ["ai", "neural-networks"]),
    "large language model":    ("ai",          ["ai", "llm"]),
    " llm ":                   ("ai",          ["ai", "llm"]),
    "chatgpt":                 ("ai",          ["ai", "chatgpt", "openai"]),
    "openai":                  ("ai",          ["ai", "openai"]),
    "anthropic":               ("ai",          ["ai", "anthropic"]),
    "gemini":                  ("ai",          ["ai", "google", "gemini"]),
    "copilot":                 ("ai",          ["ai", "microsoft", "copilot"]),
    "generative ai":           ("ai",          ["ai", "generative-ai"]),
    "claude":                  ("ai",          ["ai", "anthropic", "claude"]),
    "grok":                    ("ai",          ["ai", "xai", "grok"]),
    "mistral":                 ("ai",          ["ai", "mistral"]),

    # Security
    "cybersecurity":           ("security",    ["security", "cybersecurity"]),
    "ransomware":              ("security",    ["security", "ransomware"]),
    "malware":                 ("security",    ["security", "malware"]),
    "data breach":             ("security",    ["security", "data-breach"]),
    "vulnerability":           ("security",    ["security", "vulnerability"]),
    "hacker":                  ("security",    ["security", "hacking"]),
    "zero-day":                ("security",    ["security", "zero-day"]),
    "phishing":                ("security",    ["security", "phishing"]),
    "exploit":                 ("security",    ["security", "exploit"]),
    "spyware":                 ("security",    ["security", "spyware"]),

    # Mobile
    "iphone":                  ("mobile",      ["mobile", "apple", "iphone"]),
    "android":                 ("mobile",      ["mobile", "android"]),
    "smartphone":              ("mobile",      ["mobile", "smartphone"]),
    "samsung galaxy":          ("mobile",      ["mobile", "samsung"]),
    "pixel phone":             ("mobile",      ["mobile", "google", "pixel"]),

    # Gadgets
    "smartwatch":              ("gadgets",     ["gadgets", "wearables"]),
    "headphones":              ("gadgets",     ["gadgets", "audio"]),
    "laptop":                  ("gadgets",     ["gadgets", "laptop"]),
    "graphics card":           ("gadgets",     ["gadgets", "gpu"]),
    "electric vehicle":        ("gadgets",     ["gadgets", "ev", "electric-vehicle"]),
    "gpu":                     ("gadgets",     ["gadgets", "gpu", "nvidia"]),
    "processor":               ("gadgets",     ["gadgets", "processor", "chip"]),

    # Startups
    "startup":                 ("startups",    ["startups"]),
    "venture capital":         ("startups",    ["startups", "venture-capital"]),
    "series a":                ("startups",    ["startups", "funding"]),
    "series b":                ("startups",    ["startups", "funding"]),
    "series c":                ("startups",    ["startups", "funding"]),
    "ipo":                     ("startups",    ["startups", "ipo"]),
    "unicorn":                 ("startups",    ["startups", "unicorn"]),
    "funding round":           ("startups",    ["startups", "funding"]),
    "acquisition":             ("startups",    ["startups", "acquisition"]),

    # War / Conflict / Defense
    "war":                     ("war",         ["war", "conflict"]),
    "military":                ("war",         ["war", "military", "defense"]),
    "troops":                  ("war",         ["war", "military"]),
    "missile":                 ("war",         ["war", "weapons", "military"]),
    "airstrike":               ("war",         ["war", "conflict", "military"]),
    "ceasefire":               ("war",         ["war", "conflict", "diplomacy"]),
    "nato":                    ("war",         ["war", "nato", "military"]),
    "ukraine":                 ("war",         ["war", "ukraine", "russia"]),
    "gaza":                    ("war",         ["war", "gaza", "middle-east"]),
    "pentagon":                ("war",         ["war", "usa", "military"]),
    "drone strike":            ("war",         ["war", "drones", "military"]),
    "nuclear":                 ("war",         ["war", "nuclear", "weapons"]),

    # Politics
    "election":                ("politics",    ["politics", "election"]),
    "president":               ("politics",    ["politics", "government"]),
    "congress":                ("politics",    ["politics", "usa", "congress"]),
    "senate":                  ("politics",    ["politics", "usa", "senate"]),
    "parliament":              ("politics",    ["politics", "government"]),
    "white house":             ("politics",    ["politics", "usa", "white-house"]),
    "prime minister":          ("politics",    ["politics", "government"]),
    "democrat":                ("politics",    ["politics", "usa", "democrats"]),
    "republican":              ("politics",    ["politics", "usa", "republicans"]),
    "legislation":             ("politics",    ["politics", "law"]),
    "geopolitics":             ("politics",    ["politics", "geopolitics"]),
    "sanctions":               ("politics",    ["politics", "diplomacy"]),

    # Business / Economy
    "stock market":            ("business",    ["business", "stocks", "finance"]),
    "economy":                 ("business",    ["business", "economy"]),
    "inflation":               ("business",    ["business", "economy", "inflation"]),
    "interest rate":           ("business",    ["business", "economy", "fed"]),
    "federal reserve":         ("business",    ["business", "fed", "economy"]),
    "earnings":                ("business",    ["business", "earnings", "stocks"]),
    "recession":               ("business",    ["business", "economy", "recession"]),
    "wall street":             ("business",    ["business", "wall-street", "finance"]),
    "gdp":                     ("business",    ["business", "economy", "gdp"]),
    "trade war":               ("business",    ["business", "trade", "economy"]),
    "tariff":                  ("business",    ["business", "trade", "economy"]),
    "cryptocurrency":          ("business",    ["business", "crypto", "bitcoin"]),
    "bitcoin":                 ("business",    ["business", "bitcoin", "crypto"]),

    # Science
    "nasa":                    ("science",     ["science", "space", "nasa"]),
    "space":                   ("science",     ["science", "space"]),
    "climate change":          ("environment", ["environment", "climate", "global-warming"]),
    "global warming":          ("environment", ["environment", "climate"]),
    "renewable energy":        ("environment", ["environment", "energy", "sustainability"]),
    "research study":          ("science",     ["science", "research"]),
    "black hole":              ("science",     ["science", "space", "astronomy"]),
    "planet":                  ("science",     ["science", "space", "astronomy"]),
    "gene":                    ("science",     ["science", "biology", "genetics"]),
    "physics":                 ("science",     ["science", "physics"]),

    # Health / Medicine
    "vaccine":                 ("health",      ["health", "vaccine", "medicine"]),
    "cancer":                  ("health",      ["health", "cancer", "medicine"]),
    "pandemic":                ("health",      ["health", "pandemic", "disease"]),
    "mental health":           ("health",      ["health", "mental-health"]),
    "fda":                     ("health",      ["health", "fda", "medicine"]),
    "clinical trial":          ("health",      ["health", "research", "medicine"]),
    "antibiotic":              ("health",      ["health", "medicine"]),
    "obesity":                 ("health",      ["health", "obesity", "nutrition"]),
    "diabetes":                ("health",      ["health", "diabetes", "medicine"]),
    "virus":                   ("health",      ["health", "virus", "disease"]),

    # Food / Cooking
    "recipe":                  ("food",        ["food", "cooking", "recipe"]),
    "restaurant":              ("food",        ["food", "restaurant", "dining"]),
    "chef":                    ("food",        ["food", "chef", "cuisine"]),
    "cuisine":                 ("food",        ["food", "cuisine"]),
    "ingredient":              ("food",        ["food", "cooking"]),
    "michelin":                ("food",        ["food", "restaurant", "michelin"]),
    "food festival":           ("food",        ["food", "festival"]),
    "street food":             ("food",        ["food", "street-food"]),

    # Sports
    "nfl":                     ("sports",      ["sports", "nfl", "american-football"]),
    "nba":                     ("sports",      ["sports", "nba", "basketball"]),
    "nhl":                     ("sports",      ["sports", "nhl", "hockey"]),
    "mlb":                     ("sports",      ["sports", "mlb", "baseball"]),
    "premier league":          ("sports",      ["sports", "football", "premier-league"]),
    "champions league":        ("sports",      ["sports", "football", "champions-league"]),
    "world cup":               ("sports",      ["sports", "football", "world-cup"]),
    "olympic":                 ("sports",      ["sports", "olympics"]),
    "formula 1":               ("sports",      ["sports", "f1", "motorsport"]),
    " f1 ":                    ("sports",      ["sports", "f1", "motorsport"]),
    "tennis":                  ("sports",      ["sports", "tennis"]),
    "golf":                    ("sports",      ["sports", "golf"]),
    "ufc":                     ("sports",      ["sports", "ufc", "mma"]),
    "transfer":                ("sports",      ["sports", "football", "transfers"]),

    # Entertainment
    "movie":                   ("entertainment", ["entertainment", "movies"]),
    "film":                    ("entertainment", ["entertainment", "movies"]),
    "netflix":                 ("entertainment", ["entertainment", "streaming", "netflix"]),
    "oscar":                   ("entertainment", ["entertainment", "oscars", "movies"]),
    "grammy":                  ("entertainment", ["entertainment", "music", "grammy"]),
    "album":                   ("entertainment", ["entertainment", "music"]),
    "box office":              ("entertainment", ["entertainment", "movies", "box-office"]),
    "streaming":               ("entertainment", ["entertainment", "streaming"]),
    "video game":              ("entertainment", ["entertainment", "gaming"]),
    "tv show":                 ("entertainment", ["entertainment", "tv"]),

    # Environment
    "carbon emissions":        ("environment",  ["environment", "climate", "emissions"]),
    "deforestation":           ("environment",  ["environment", "deforestation"]),
    "biodiversity":            ("environment",  ["environment", "biodiversity"]),
    "wildfire":                ("environment",  ["environment", "wildfire", "climate"]),
    "flood":                   ("environment",  ["environment", "flood", "climate"]),
    "drought":                 ("environment",  ["environment", "drought", "climate"]),
    "solar energy":            ("environment",  ["environment", "solar", "energy"]),

    # Travel
    "travel":                  ("travel",       ["travel", "destinations"]),
    "tourism":                 ("travel",       ["travel", "tourism"]),
    "airline":                 ("travel",       ["travel", "airline", "flight"]),
    "hotel":                   ("travel",       ["travel", "hotel"]),
    "visa":                    ("travel",       ["travel", "visa"]),
}

# ============================================================
# FILTRO DE QUALIDADE — BLACKLIST
# Termos que indicam conteúdo irrelevante para um blog de tecnologia
# ============================================================

BLACKLIST_PHRASES = [
    # Puzzles / games (não é notícia)
    "crossword", "crossword answers", "wordle", "mini crossword",
    "horoscope", "zodiac", "astrology",
    # Spam / ads
    "discount code", "coupon", "promo code", "deals up to",
    "best deals", "sale ends", "limited time offer",
    "click here to win", "giveaway",
    "sponsored content", "advertisement",
    # Adult / harmful content
    "sex toy", "vibrator", "we-vibe", "adult toy",
    "deepfake porn", "deepfake nude", "nonconsensual",
]

BLACKLIST_TITLE_PATTERNS = [
    r"^today['']s .{0,30} answers",
    r"^best .{0,30} deals",
    r"\bdiscount codes?\b",
    r"\bcoupon\b",
    r"\bpromo code\b",
    r"\bhoroscope\b",
    r"\bcrossword\b",
    r"\bwordle\b",
]


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def fetch_og_metadata(url: str, timeout: int = 10) -> dict:
    """
    Fetches OG metadata AND article body text in a single request.
    Reads up to 64 KB to capture both <head> tags and initial body paragraphs.
    Returns dict with 'description', 'image', and 'body' keys.
    """
    result = {"description": "", "image": "", "body": ""}
    try:
        resp = _session.get(url, timeout=timeout, stream=True,
                            headers={"Accept": "text/html"})
        resp.raise_for_status()
        chunk = b""
        for data in resp.iter_content(chunk_size=8192):
            chunk += data
            if len(chunk) >= 65536:  # 64 KB
                break
        resp.close()
        html = chunk.decode("utf-8", errors="ignore")
    except Exception:
        return result

    # og:description
    og_desc = re.search(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{20,})["\']',
        html, re.IGNORECASE
    )
    if not og_desc:
        og_desc = re.search(
            r'<meta[^>]+content=["\']([^"\']{20,})["\'][^>]+property=["\']og:description["\']',
            html, re.IGNORECASE
        )
    if og_desc:
        result["description"] = sanitize_text(re.sub(r"\s+", " ", og_desc.group(1)).strip()[:800])

    # og:image
    og_img = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if not og_img:
        og_img = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            html, re.IGNORECASE
        )
    if og_img:
        url_candidate = og_img.group(1).strip()
        if url_candidate.startswith("http"):
            result["image"] = url_candidate

    # Extract body paragraphs for richer post content
    raw_paragraphs = re.findall(r'<p[^>]{0,100}>(.*?)</p>', html, re.IGNORECASE | re.DOTALL)
    body_parts = []
    total_chars = 0
    for p in raw_paragraphs:
        clean = re.sub(r'<[^>]+>', ' ', p)
        clean = re.sub(r'&[a-zA-Z]+;', ' ', clean)
        clean = re.sub(r'&#\d+;', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Skip nav/footer noise: very short or all-caps
        if len(clean) < 60 or clean.isupper():
            continue
        body_parts.append(clean)
        total_chars += len(clean)
        if total_chars >= 2500:
            break
    result["body"] = sanitize_text(" ".join(body_parts)[:2500])

    return result


def is_blacklisted(title: str, description: str) -> bool:
    """Verifica se o conteúdo deve ser filtrado por baixa qualidade/irrelevância."""
    combined = (title + " " + description).lower()

    for phrase in BLACKLIST_PHRASES:
        if phrase.lower() in combined:
            return True

    for pattern in BLACKLIST_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True

    return False


# Inverted index built once at import time: word → (cat, tags)
# Avoids O(n*keywords) scan per article.
_KEYWORD_INDEX: dict[str, tuple[str, list]] = {
    kw: val for kw, val in KEYWORD_CATEGORIES.items()
}

def get_extra_tags(title: str, description: str) -> tuple[str, list]:
    """Detecta categoria e tags extras a partir do conteúdo (inverted index)."""
    combined = (title + " " + description).lower()
    for keyword, (cat, tags) in _KEYWORD_INDEX.items():
        if keyword in combined:
            return cat, tags
    return "", []


# Dead-feed failure counter: feed name → consecutive failure count
_feed_failures: dict[str, int] = {}
_DEAD_FEED_THRESHOLD = 3


def post_filename(date: datetime, slug: str) -> str:
    """Gera nome do arquivo de post Jekyll."""
    return f"{date.strftime('%Y-%m-%d')}-{slug}.md"


# Cache de URLs conhecidas (construído uma vez por execução)
_known_urls: set | None = None

def _load_known_urls() -> set:
    """Lê posts existentes e coleta todas as source_url."""
    global _known_urls
    if _known_urls is not None:
        return _known_urls
    _known_urls = set()
    for f in POSTS_DIR.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("source_url:"):
                    url = line.split("source_url:", 1)[1].strip().strip('"')
                    if url:
                        _known_urls.add(url)
                    break
        except Exception:
            pass
    return _known_urls


def post_exists(filename: str, source_url: str = "") -> bool:
    """Retorna True se o post já existe (por filename OU por source URL)."""
    if (POSTS_DIR / filename).exists():
        return True
    if source_url:
        return source_url in _load_known_urls()
    return False


# ENTITY EXTRACTION — improved auto-tagging
# ============================================================

def _extract_entities(title: str, description: str = "") -> list:
    """Extract proper nouns as additional tags using simple heuristics."""
    text = title + " " + description
    # Capitalized words (likely proper nouns) not at sentence start
    words = re.findall(
        r'(?<!\. )(?<!\n)(?<!["\'])([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})',
        text,
    )
    STOPWORDS = {
        "The", "This", "That", "These", "Those", "When", "Where", "What",
        "After", "Before", "During", "While", "How", "Why", "New", "United",
        "American", "European", "Global", "World", "International",
    }
    entities = []
    for w in words:
        parts = w.split()
        if not any(p in STOPWORDS for p in parts) and len(w) > 3:
            tag = w.lower().replace(" ", "-")
            if len(tag) < 30:
                entities.append(tag)
    return list(dict.fromkeys(entities))[:5]  # dedup, max 5


# ============================================================
# STORY CONTINUATION — find related post filename for linking
# ============================================================

def _find_continuation(title: str, known_posts: list) -> str | None:
    """Find a related post filename for internal linking (Jaccard on 4+ letter words)."""
    title_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', title.lower()))
    best_match, best_score = None, 0
    for post_file, post_title in known_posts[-50:]:  # check last 50
        post_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', post_title.lower()))
        if not title_words or not post_words:
            continue
        score = len(title_words & post_words) / len(title_words | post_words)
        if score > 0.35 and score > best_score:
            best_score = score
            best_match = post_file
    return best_match


# Cache of known titles (built once per run)
_known_titles: list | None = None

def _load_known_titles() -> list:
    """Reads existing posts and returns list of (title, filename) tuples (last 100 posts)."""
    global _known_titles
    if _known_titles is not None:
        return _known_titles
    _known_titles = []
    all_posts = sorted(POSTS_DIR.glob("*.md"), reverse=True)[:100]
    for f in all_posts:
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("title:"):
                    m = re.match(r'title:\s*"?([^"]+)"?\s*$', line)
                    if m:
                        _known_titles.append((m.group(1).strip(), f.name))
                    break
        except Exception:
            pass
    return _known_titles


def build_frontmatter(
    title:             str,
    date:              datetime,
    categories:        list,
    tags:              list,
    author:            str,
    description:       str,
    source_url:        str,
    source_name:       str,
    image:             str,
    keywords:          list | None = None,
    faq:               list | None = None,
    sentiment:         str  = "neutral",
    key_points:        list | None = None,
    fact_check:        str | None = None,
    image_caption:     str | None = None,
    last_updated:      str  = "",
    wikipedia_summary: str  = "",
    description_ptbr:  str  = "",
    crypto_prices:     dict | None = None,
    hook:              str  = "",
    related_post:      str  = "",
    tl_dr:             str  = "",
    lead:              str  = "",
    content_type:      str  = "",
    entities:          list | None = None,
) -> str:
    """Monta o frontmatter YAML do post Jekyll."""
    date_str  = date.strftime("%Y-%m-%d %H:%M:%S %z").strip()
    # Slugify tags before serialising to YAML — keeps the inline array
    # safe against AI-generated values that contain commas, brackets, or
    # quotes (e.g. "gaza-death-toll-73,000" would otherwise split the
    # array and the trailing "000" would parse as integer 0, which then
    # crashes the sort filter in series/index.html).
    cats_yaml = "[" + ", ".join(c for c in categories if c) + "]"
    safe_tags = [s for s in (slugify(t) for t in tags if t) if s]
    tags_yaml = "[" + ", ".join(safe_tags) + "]"

    front = f"""---
layout: post
title: "{sanitize_text(title)}"
date: {date_str if date_str else date.strftime("%Y-%m-%d %H:%M:%S +0000")}
categories: {cats_yaml}
tags: {tags_yaml}
author: "{author}"
description: "{sanitize_text(description[:160])}"
source_url: "{source_url}"
source_name: "{source_name}"
sentiment: "{sentiment}"
lang: "en"
"""
    # Auto-generate OG image if none provided
    if not image:
        import urllib.parse
        prompt = urllib.parse.quote(f"{title[:60]} news editorial dark background", safe='')
        seed = abs(hash(title)) % 100000
        image = f"https://image.pollinations.ai/prompt/{prompt}?width=1200&height=630&nologo=true&seed={seed}&model=flux"
    if last_updated:
        front += f'last_updated: "{last_updated}"\n'
    if image:
        front += f'image: "{image}"\n'
        alt = sanitize_text(title[:100])
        if not alt:
            alt = sanitize_text(title[:100])
        front += f'image_alt: "{alt}"\n'
    if image_caption:
        front += f'image_caption: "{sanitize_text(image_caption[:120])}"\n'
    if fact_check:
        front += f'fact_check: "{fact_check}"\n'
    if keywords:
        kw_yaml = "[" + ", ".join(f'"{k}"' for k in keywords[:8] if k and len(k) > 1) + "]"
        front += f"keywords: {kw_yaml}\n"
    if key_points:
        front += "key_points:\n"
        for pt in key_points[:3]:
            pt_clean = sanitize_text(str(pt)).replace('"', "'")
            if pt_clean:
                front += f'  - "{pt_clean}"\n'
    if faq:
        front += "faq:\n"
        for item in faq[:5]:
            q = sanitize_text(str(item.get("q", ""))).replace('"', "'")
            a = sanitize_text(str(item.get("a", ""))).replace('"', "'")
            if q and a:
                front += f'  - q: "{q}"\n    a: "{a}"\n'
    if wikipedia_summary:
        front += f'wikipedia_summary: "{sanitize_text(wikipedia_summary[:500])}"\n'
    if description_ptbr:
        front += f'description_ptbr: "{sanitize_text(description_ptbr[:300])}"\n'
    if crypto_prices:
        # Embed a concise snapshot: e.g. bitcoin_usd: 68000
        for coin, data in crypto_prices.items():
            usd = data.get("usd")
            change = data.get("usd_24h_change")
            if usd is not None:
                front += f'crypto_{coin}_usd: {usd}\n'
            if change is not None:
                front += f'crypto_{coin}_24h_change: {round(change, 2)}\n'
    # ── Breaking news flags ───────────────────────────────────────
    breaking = _is_breaking_news(title, description)
    if breaking:
        front += 'featured: true\n'
    front += f'breaking: {str(breaking).lower()}\n'
    # ── Journalistic hook ─────────────────────────────────────────
    if hook:
        front += f'hook: "{sanitize_text(hook[:120])}"\n'
    # ── Related post for cross-linking ───────────────────────────
    if related_post:
        front += f'related_post: "{related_post}"\n'
    # ── TL;DR (renders in tl-dr-box on post page) ────────────────
    if tl_dr:
        front += f'tl_dr: "{sanitize_text(tl_dr[:280])}"\n'
    # ── Lead paragraph (post.html post-lead) ─────────────────────
    if lead:
        front += f'lead: "{sanitize_text(lead[:400])}"\n'
    # ── Article content type (drives news:genres in sitemap) ─────
    valid_types = {"news", "breaking", "analysis", "explainer", "opinion", "feature"}
    if content_type and content_type.strip().lower() in valid_types:
        front += f'content_type: "{content_type.strip().lower()}"\n'
    # ── Named entities (renders as entity chips on post page) ────
    if entities:
        clean = [sanitize_text(str(e))[:60] for e in entities[:8] if e]
        clean = [e for e in clean if e]
        if clean:
            front += "entities:\n"
            for e in clean:
                front += f'  - "{e.replace(chr(34), chr(39))}"\n'
    front += "---\n"
    return front


def build_content(
    title:       str,
    description: str,
    source_url:  str,
    source_name: str,
    date:        datetime,
    categories:  list,
    tags:        list,
    body:        str = "",
    ai_body:     str = "",
) -> str:
    """Builds rich Markdown post content for SEO. Uses AI body when available."""
    date_str       = date.strftime("%B %d, %Y")
    time_str       = date.strftime("%H:%M UTC")
    category_label = categories[0].capitalize() if categories else "News"
    tag_links      = [f"#{t}" for t in tags[:6] if len(t) > 2]
    tags_line      = " · ".join(tag_links) if tag_links else ""

    if ai_body and len(ai_body) > 200:
        # ── AI-generated content (high quality SEO) ──────────
        content = f"{ai_body}\n\n<!--more-->\n\n"
    else:
        # ── Template-based fallback ───────────────────────────
        sentences = re.split(r'(?<=[.!?])\s+', description.strip())
        para1 = " ".join(sentences[:3]) if len(sentences) >= 3 else description.strip()
        para2 = " ".join(sentences[3:6]) if len(sentences) > 3 else ""

        body_sections = []
        if body:
            body_sentences = re.split(r'(?<=[.!?])\s+', body.strip())
            desc_lower = description.lower()
            unique = [s for s in body_sentences if s.lower()[:40] not in desc_lower]
            if unique:
                chunk1 = " ".join(unique[:4])
                chunk2 = " ".join(unique[4:8]) if len(unique) > 4 else ""
                if len(chunk1) > 80:
                    body_sections.append(chunk1)
                if len(chunk2) > 80:
                    body_sections.append(chunk2)

        content = f"{para1}\n\n<!--more-->\n"
        if para2:
            content += f"\n{para2}\n"
        if body_sections:
            content += f"\n{body_sections[0]}\n"
            if len(body_sections) > 1:
                content += f"\n{body_sections[1]}\n"

    content += f"""
## What You Need to Know

- **Source:** [{source_name}]({source_url})
- **Published:** {date_str} at {time_str}
- **Category:** {category_label}
"""
    if tag_links:
        content += f"- **Topics:** {tags_line}\n"

    content += f"""
## Read the Full Story

This is a curated summary. For the complete article, original data, quotes and full analysis:

> **[Read the full story on {source_name} →]({source_url})**

*All reporting rights belong to the respective author(s) at **{source_name}**. GlobalBR News summarizes publicly available content to help readers discover the most relevant global news.*

---

*Curated by [GlobalBR News](https://non-s.github.io) · {date_str}*
"""
    return content


# ============================================================
# INTERNAL LINKING
# ============================================================

def _add_internal_links(content: str, category: str, current_stem: str) -> str:
    """Scans the last 40 posts and injects a 'Related Articles' section."""
    try:
        all_posts = sorted(POSTS_DIR.glob("*.md"), key=lambda p: p.name, reverse=True)[:40]
        related = []
        for post_path in all_posts:
            stem = post_path.stem
            if stem == current_stem:
                continue
            try:
                text = post_path.read_text(encoding="utf-8")
                post_category = ""
                post_title = ""
                for line in text.splitlines():
                    if line.startswith("categories:") and not post_category:
                        m = re.search(r'\[([^\]]+)\]', line)
                        if m:
                            parts = [p.strip() for p in m.group(1).split(",")]
                            post_category = parts[0] if parts else ""
                    if line.startswith("title:") and not post_title:
                        m = re.match(r'title:\s*"?([^"]+)"?\s*$', line)
                        if m:
                            post_title = m.group(1).strip()
                    if post_category and post_title:
                        break
                if post_category != category or not post_title:
                    continue
                # Build URL from stem: YYYY-MM-DD-slug
                m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)$', stem)
                if not m:
                    continue
                year, month, day, slug = m.group(1), m.group(2), m.group(3), m.group(4)
                url = f"/{category}/{year}/{month}/{day}/{slug}/"
                related.append((post_title, url))
                if len(related) >= 3:
                    break
            except Exception:
                continue
        if not related:
            return content
        links_md = "\n".join(f"- [{title}]({url})" for title, url in related)
        section = f"\n\n---\n\n## Related Articles\n\n{links_md}\n"
        return content + section
    except Exception:
        return content


# ============================================================
# PORTUGUESE SUMMARY
# ============================================================

def _add_pt_summary(title: str, description: str, category: str) -> str:
    """Generates a rich Portuguese (PT-BR) summary section using AI."""
    try:
        cat_pt = {
            "world": "mundo", "politics": "política", "war": "conflito/defesa",
            "business": "economia", "science": "ciência", "health": "saúde",
            "food": "gastronomia", "sports": "esportes", "entertainment": "entretenimento",
            "environment": "meio ambiente", "travel": "viagens", "technology": "tecnologia",
            "ai": "inteligência artificial", "security": "segurança digital",
            "gadgets": "gadgets", "startups": "startups", "mobile": "celulares",
        }.get(category, "notícias")

        prompt = (
            f"Você é um jornalista brasileiro experiente da área de {cat_pt}. "
            f"Escreva um resumo em português do Brasil (PT-BR) sobre a notícia abaixo. "
            f"O resumo deve ter EXATAMENTE 2 a 3 parágrafos em texto corrido:\n"
            f"1. Uma frase de abertura envolvente que contextualize o fato principal de forma atraente para o leitor brasileiro.\n"
            f"2. Um parágrafo explicando o contexto e a relevância desta notícia para o Brasil e os leitores de língua portuguesa.\n"
            f"3. Uma frase ou parágrafo de fechamento com implicações ou próximos passos.\n\n"
            f"Use linguagem jornalística natural, clara e acessível. "
            f"Não use bullet points, JSON, títulos ou formatação especial — apenas parágrafos corridos.\n\n"
            f"Título: {title}\nDescrição: {description}"
        )
        pt_text = _ai_text(
            prompt,
            system=(
                "Você é um jornalista profissional brasileiro. "
                "Escreva sempre em português do Brasil (PT-BR), com linguagem natural e fluente. "
                "Nunca use inglês. Responda apenas com o texto do resumo, sem introduções como 'Aqui está...'."
            ),
        )
        if not pt_text:
            return ""
        pt_text = pt_text.strip()
        # Strip any accidental leading label like "Resumo:" the AI might add
        pt_text = re.sub(r'^(resumo\s*:|aqui está[^:]*:|resultado:)\s*', '', pt_text, flags=re.IGNORECASE)
        if len(pt_text) < 60:
            return ""
        return f"\n\n---\n\n## 🇧🇷 Resumo em Português\n\n{pt_text}\n"
    except Exception:
        return ""


# ============================================================
# SPANISH SUMMARY
# ============================================================

def _add_es_summary(title: str, description: str, category: str) -> str:
    """Generates a rich Spanish (ES) summary section using AI."""
    try:
        cat_es = {
            "world": "mundo", "politics": "política", "war": "conflicto/defensa",
            "business": "economía", "science": "ciencia", "health": "salud",
            "food": "gastronomía", "sports": "deportes", "entertainment": "entretenimiento",
            "environment": "medio ambiente", "travel": "viajes", "technology": "tecnología",
            "ai": "inteligencia artificial", "security": "ciberseguridad",
            "gadgets": "gadgets", "startups": "startups", "mobile": "móviles",
        }.get(category, "noticias")

        prompt = (
            f"Eres un periodista español experimentado en {cat_es}. "
            f"Escribe un resumen en español (ES) sobre la noticia siguiente. "
            f"El resumen debe tener EXACTAMENTE 2 párrafos en prosa:\n"
            f"1. Una frase de apertura que contextualice el hecho principal de forma atractiva.\n"
            f"2. Un párrafo que explique el contexto, la relevancia y las implicaciones para los lectores hispanohablantes.\n\n"
            f"Usa lenguaje periodístico natural, claro y accesible. "
            f"Sin bullet points, sin JSON, sin títulos — solo párrafos en prosa.\n\n"
            f"Título: {title}\nDescripción: {description}"
        )
        es_text = _ai_text(
            prompt,
            system=(
                "Eres un periodista profesional hispanohablante. "
                "Escribe siempre en español estándar, con lenguaje natural y fluido. "
                "Nunca uses inglés. Responde solo con el texto del resumen."
            ),
        )
        if not es_text:
            return ""
        es_text = es_text.strip()
        es_text = re.sub(r'^(resumen\s*:|aquí está[^:]*:|resultado:)\s*', '', es_text, flags=re.IGNORECASE)
        if len(es_text) < 60:
            return ""
        return f"\n\n---\n\n## 🇪🇸 Resumen en Español\n\n{es_text}\n"
    except Exception:
        return ""


# ============================================================
# STORY CONTINUATION DETECTION
# ============================================================

_PT_STOPWORDS = {
    "about", "after", "again", "along", "among", "around", "before",
    "being", "between", "could", "during", "every", "first", "found",
    "great", "group", "house", "large", "later", "light", "might",
    "never", "night", "often", "other", "place", "right", "small",
    "still", "their", "there", "these", "thing", "think", "those",
    "three", "through", "today", "under", "until", "using", "where",
    "which", "while", "world", "would", "years", "their", "since",
    "after", "major", "report", "shows", "ahead", "calls", "backs",
    "says", "says",
}


def _find_related_story(title: str, tags: list, category: str) -> str:
    """
    Scans the last 20 posts in the same category using keyword overlap (2+ shared nouns).
    Returns a Markdown 'Continuing coverage' link or empty string.
    """
    # ── Keyword-based search ──────────────────────────────────────
    try:
        key_nouns = {
            w.lower() for w in title.split()
            if len(w) > 5 and w.lower() not in _PT_STOPWORDS and w.isalpha()
        }
        if len(key_nouns) < 2:
            return ""

        all_posts = sorted(POSTS_DIR.glob("*.md"), key=lambda p: p.name, reverse=True)
        checked = 0
        for post_path in all_posts:
            if checked >= 20:
                break
            try:
                text = post_path.read_text(encoding="utf-8")
                post_category = ""
                post_title = ""
                for line in text.splitlines():
                    if line.startswith("categories:") and not post_category:
                        m = re.search(r'\[([^\]]+)\]', line)
                        if m:
                            parts = [p.strip() for p in m.group(1).split(",")]
                            post_category = parts[0] if parts else ""
                    if line.startswith("title:") and not post_title:
                        m = re.match(r'title:\s*"?([^"]+)"?\s*$', line)
                        if m:
                            post_title = m.group(1).strip()
                    if post_category and post_title:
                        break
                if post_category != category:
                    continue
                checked += 1
                existing_nouns = {
                    w.lower() for w in post_title.split()
                    if len(w) > 5 and w.lower() not in _PT_STOPWORDS and w.isalpha()
                }
                shared = key_nouns & existing_nouns
                if len(shared) >= 2:
                    stem = post_path.stem
                    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)$', stem)
                    if m:
                        yr, mo, dy, sl = m.group(1), m.group(2), m.group(3), m.group(4)
                        url = f"/{category}/{yr}/{mo}/{dy}/{sl}/"
                        return (
                            f"> 📰 **Continuing coverage:** [{post_title}]({url})\n\n"
                        )
            except Exception:
                continue
    except Exception:
        pass
    return ""


# ============================================================
# SOURCE DIVERSITY CHECK
# ============================================================

def _check_source_diversity(created_today: dict) -> None:
    """Logs a warning if any single source accounts for > 30% of today's posts."""
    total = sum(created_today.values())
    if total == 0:
        return
    for source, count in created_today.items():
        pct = count / total * 100
        if pct > 30:
            log.warning(
                f"Source diversity alert: {source} = {pct:.0f}% of today's posts ({count}/{total})"
            )


# ============================================================
# DAILY ROUNDUP
# ============================================================

def create_daily_roundup() -> None:
    """
    Creates a daily roundup post if >= 5 posts were published today.
    Skips if the roundup already exists.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    roundup_filename = f"{today}-daily-roundup.md"
    roundup_path = POSTS_DIR / roundup_filename

    if roundup_path.exists():
        log.info("Daily roundup already exists — skipping.")
        return

    today_posts = []
    for f in sorted(POSTS_DIR.glob(f"{today}-*.md")):
        if "roundup" in f.stem or "digest" in f.stem:
            continue
        try:
            text = f.read_text(encoding="utf-8")
            post_title = ""
            post_cat = ""
            for line in text.splitlines():
                if line.startswith("title:") and not post_title:
                    m = re.match(r'title:\s*"?([^"]+)"?\s*$', line)
                    if m:
                        post_title = m.group(1).strip()
                if line.startswith("categories:") and not post_cat:
                    m = re.search(r'\[([^\]]+)\]', line)
                    if m:
                        parts = [p.strip() for p in m.group(1).split(",")]
                        post_cat = parts[0] if parts else ""
                if post_title and post_cat:
                    break
            if post_title:
                stem = f.stem
                m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)$', stem)
                if m and post_cat:
                    yr, mo, dy, sl = m.group(1), m.group(2), m.group(3), m.group(4)
                    url = f"/{post_cat}/{yr}/{mo}/{dy}/{sl}/"
                    today_posts.append((post_title, url))
        except Exception:
            continue

    if len(today_posts) < 5:
        log.info(f"Not enough posts today ({len(today_posts)}) for daily roundup — skipping.")
        return

    log.info(f"Creating daily roundup for {today} ({len(today_posts)} posts)...")

    headlines = "\n".join(f"- {t}" for t, _ in today_posts)
    ai_prompt = (
        f"Write a 2-3 paragraph editorial summary of today's top news stories for GlobalBR News. "
        f"Be engaging and journalistic. Summarize the main themes and significance of today's coverage. "
        f"Do not use bullet points — write flowing paragraphs only.\n\n"
        f"Today's headlines:\n{headlines}"
    )
    ai_intro = _ai_text(ai_prompt, system="You are a professional news editor writing a daily digest.")
    if not ai_intro:
        ai_intro = f"Here is a roundup of today's top {len(today_posts)} stories from GlobalBR News."

    date_display = datetime.now(timezone.utc).strftime("%B %d, %Y")
    bullet_list = "\n".join(f"- [{t}]({u})" for t, u in today_posts)

    roundup_image = _generate_og_image(f"Daily News Roundup — {date_display}", "roundup", f"{today}-daily-roundup")

    frontmatter = f"""---
layout: post
title: "Daily News Roundup — {date_display}"
date: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000")}
categories: [roundup]
tags: [daily, news, roundup]
author: "GlobalBR News"
description: "Your daily roundup of the top {len(today_posts)} news stories for {date_display}."
image: "{roundup_image}"
sentiment: "neutral"
---
"""
    content = (
        f"{ai_intro}\n\n<!--more-->\n\n"
        f"## Today's Top Stories\n\n"
        f"{bullet_list}\n\n"
        f"---\n\n"
        f"*Curated by [GlobalBR News](https://non-s.github.io) · {date_display}*\n"
    )
    roundup_path.write_text(frontmatter + "\n" + content, encoding="utf-8")
    log.info(f"Daily roundup created: {roundup_filename}")


# ============================================================
# WEEKLY DIGEST
# ============================================================

def create_weekly_digest() -> None:
    """
    Creates a 'Best of the Week' digest post every Sunday.
    Skips if not Sunday or if the digest already exists.
    """
    if datetime.now().weekday() != 6:  # 6 = Sunday
        return

    today = datetime.now(timezone.utc)
    digest_filename = f"{today.strftime('%Y-%m-%d')}-weekly-digest.md"
    digest_path = POSTS_DIR / digest_filename

    if digest_path.exists():
        log.info("Weekly digest already exists for this week — skipping.")
        return

    from datetime import timedelta
    cutoff = today - timedelta(days=7)
    week_posts = []

    for f in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        if "roundup" in f.stem or "digest" in f.stem:
            continue
        try:
            m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)$', f.stem)
            if not m:
                continue
            yr, mo, dy, sl = m.group(1), m.group(2), m.group(3), m.group(4)
            post_date = datetime(int(yr), int(mo), int(dy), tzinfo=timezone.utc)
            if post_date < cutoff:
                break  # files are sorted newest-first, so we can stop early
            text = f.read_text(encoding="utf-8")
            post_title = ""
            post_cat = ""
            post_source = ""
            for line in text.splitlines():
                if line.startswith("title:") and not post_title:
                    mm = re.match(r'title:\s*"?([^"]+)"?\s*$', line)
                    if mm:
                        post_title = mm.group(1).strip()
                if line.startswith("categories:") and not post_cat:
                    mm = re.search(r'\[([^\]]+)\]', line)
                    if mm:
                        parts = [p.strip() for p in mm.group(1).split(",")]
                        post_cat = parts[0] if parts else ""
                if line.startswith("source_name:") and not post_source:
                    post_source = line.split("source_name:", 1)[1].strip().strip('"')
                if post_title and post_cat and post_source:
                    break
            if post_title and post_cat:
                url = f"/{post_cat}/{yr}/{mo}/{dy}/{sl}/"
                week_posts.append((post_title, url, post_source))
        except Exception:
            continue

    if len(week_posts) < 3:
        log.info(f"Not enough posts this week ({len(week_posts)}) for weekly digest — skipping.")
        return

    log.info(f"Creating weekly digest ({len(week_posts)} posts this week)...")

    top5 = week_posts[:5]
    headlines = "\n".join(f"- {t} ({s})" for t, _, s in top5)
    ai_prompt = (
        f"Write a 'Best of the Week' editorial for GlobalBR News covering the top stories of the past 7 days. "
        f"Structure: 1) engaging opening paragraph about this week's major themes, "
        f"2) highlight the top 5 stories and why they matter, "
        f"3) brief closing paragraph. "
        f"Use journalistic prose, no bullet points in the intro/closing.\n\n"
        f"This week's top stories:\n{headlines}"
    )
    ai_body = _ai_text(ai_prompt, system="You are a senior editor writing a weekly news digest.")
    if not ai_body:
        ai_body = f"Here is a look at the most important stories from the past week on GlobalBR News."

    date_display = today.strftime("%B %d, %Y")
    top5_list = "\n".join(f"- [{t}]({u})" for t, u, _ in top5)

    frontmatter = f"""---
layout: post
title: "Best of the Week — {date_display}"
date: {today.strftime("%Y-%m-%d %H:%M:%S +0000")}
categories: [digest]
tags: [weekly, roundup, digest]
author: "GlobalBR News"
description: "The most important stories of the week, curated by GlobalBR News — {date_display}."
sentiment: "neutral"
---
"""
    content = (
        f"{ai_body}\n\n<!--more-->\n\n"
        f"## Top Stories This Week\n\n"
        f"{top5_list}\n\n"
        f"---\n\n"
        f"*Weekly digest by [GlobalBR News](https://non-s.github.io) · {date_display}*\n"
    )
    digest_path.write_text(frontmatter + "\n" + content, encoding="utf-8")
    log.info(f"Weekly digest created: {digest_filename}")


# ============================================================
# WEEKLY STATS POST
# ============================================================

def _generate_weekly_stats_post() -> None:
    """
    Creates a 'Week in Review' stats post every Sunday alongside the digest.
    Counts posts by category, calculates average sentiment, and finds the most-used tag.
    Skips if not Sunday or if the stats post already exists today.
    """
    if datetime.now().weekday() != 6:  # 6 = Sunday
        return

    today = datetime.now(timezone.utc)
    stats_filename = f"{today.strftime('%Y-%m-%d')}-week-in-review-stats.md"
    stats_path = POSTS_DIR / stats_filename

    if stats_path.exists():
        log.info("Weekly stats post already exists for this week — skipping.")
        return

    from datetime import timedelta
    cutoff = today - timedelta(days=7)

    # ── Collect posts from the past 7 days ───────────────────────
    category_counts: dict[str, int] = {}
    sentiment_values: list[str] = []
    tag_counts: dict[str, int] = {}
    total_posts = 0

    for f in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        if "roundup" in f.stem or "digest" in f.stem or "stats" in f.stem:
            continue
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)$', f.stem)
        if not m:
            continue
        try:
            post_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                 tzinfo=timezone.utc)
        except ValueError:
            continue
        if post_date < cutoff:
            break  # sorted newest-first, can stop early
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            post_cat = ""
            post_sentiment = ""
            post_tags: list[str] = []
            for line in text.splitlines():
                if line.startswith("categories:") and not post_cat:
                    mm = re.search(r'\[([^\]]+)\]', line)
                    if mm:
                        parts = [p.strip() for p in mm.group(1).split(",")]
                        post_cat = parts[0] if parts else ""
                if line.startswith("sentiment:") and not post_sentiment:
                    post_sentiment = line.split("sentiment:", 1)[1].strip().strip('"')
                if line.startswith("tags:") and not post_tags:
                    mm = re.search(r'\[([^\]]+)\]', line)
                    if mm:
                        post_tags = [t.strip().strip('"').strip("'")
                                     for t in mm.group(1).split(",")]
                if line == "---" and post_cat:
                    break  # end of frontmatter
            if post_cat and post_cat not in ("roundup", "digest"):
                category_counts[post_cat] = category_counts.get(post_cat, 0) + 1
                total_posts += 1
            if post_sentiment:
                sentiment_values.append(post_sentiment)
            for tag in post_tags:
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        except Exception:
            continue

    if total_posts < 3:
        log.info(f"Not enough posts this week ({total_posts}) for stats post — skipping.")
        return

    # ── Compute stats ────────────────────────────────────────────
    top_category = max(category_counts, key=lambda k: category_counts[k]) \
        if category_counts else "world"
    top_category_count = category_counts.get(top_category, 0)

    sentiment_map = {"positive": 1, "neutral": 0, "negative": -1}
    if sentiment_values:
        avg_val = sum(sentiment_map.get(s, 0) for s in sentiment_values) / len(sentiment_values)
        avg_sentiment = "positive" if avg_val > 0.2 else ("negative" if avg_val < -0.2 else "neutral")
    else:
        avg_sentiment = "neutral"

    # Exclude generic tags from "top tag" ranking
    _exclude_tags = {
        "globalbrnews", "news", "roundup", "digest", "daily", "weekly",
        "world-news", "breaking", "international",
    }
    filtered_tags = {t: c for t, c in tag_counts.items()
                     if t.lower() not in _exclude_tags}
    top_tag = max(filtered_tags, key=lambda k: filtered_tags[k]) \
        if filtered_tags else ""
    top_tag_count = filtered_tags.get(top_tag, 0)

    # ── Build category breakdown table ───────────────────────────
    sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    cat_rows = "\n".join(
        f"| {cat.capitalize()} | {cnt} |"
        for cat, cnt in sorted_cats
    )
    cat_table = (
        "| Category | Posts |\n"
        "|----------|-------|\n"
        + cat_rows
    )

    date_display = today.strftime("%B %d, %Y")
    week_start = (today - timedelta(days=6)).strftime("%B %d")
    week_range = f"{week_start}–{today.strftime('%B %d, %Y')}"

    top_tag_line = f"- **Most-used tag:** `{top_tag}` ({top_tag_count} posts)\n" \
        if top_tag else ""

    content = (
        f"A quick look at what GlobalBR News covered this week "
        f"({week_range}): **{total_posts} articles** across "
        f"**{len(category_counts)} categories**, with the spotlight on "
        f"**{top_category.capitalize()}** ({top_category_count} posts).\n\n"
        f"<!--more-->\n\n"
        f"## By the Numbers\n\n"
        f"- **Total articles:** {total_posts}\n"
        f"- **Top category:** {top_category.capitalize()} ({top_category_count} posts)\n"
        f"- **Overall sentiment:** {avg_sentiment.capitalize()}\n"
        + top_tag_line +
        f"\n## Category Breakdown\n\n"
        f"{cat_table}\n\n"
        f"---\n\n"
        f"*Weekly stats by [GlobalBR News](https://non-s.github.io) · {date_display}*\n"
    )

    frontmatter = (
        f"---\n"
        f'layout: post\n'
        f'title: "Week in Review: {total_posts} articles, top category {top_category.capitalize()}"\n'
        f'date: {today.strftime("%Y-%m-%d %H:%M:%S +0000")}\n'
        f'categories: [roundup]\n'
        f'tags: [weekly, stats, roundup]\n'
        f'author: "GlobalBR News"\n'
        f'description: "GlobalBR News weekly stats: {total_posts} articles published '
        f'({week_range}), top category {top_category.capitalize()}, '
        f'sentiment {avg_sentiment}."\n'
        f'sentiment: "{avg_sentiment}"\n'
        f'featured: true\n'
        f"---\n"
    )

    stats_path.write_text(frontmatter + "\n" + content, encoding="utf-8")
    log.info(f"Weekly stats post created: {stats_filename}")


# ============================================================
# TRENDING KEYWORDS — Google Trends RSS
# ============================================================

_TRENDING_STOP_WORDS = frozenset({
    "about", "after", "again", "also", "back", "been", "before", "being",
    "between", "both", "could", "does", "doing", "during", "each", "from",
    "have", "here", "into", "just", "know", "like", "make", "more", "most",
    "much", "need", "news", "next", "only", "other", "over", "same", "says",
    "should", "some", "still", "such", "than", "that", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "time",
    "very", "want", "were", "what", "when", "where", "which", "while",
    "will", "with", "would", "your",
})

_TRENDS_FEEDS = [
    "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
    "https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB",
    "https://trends.google.com/trends/trendingsearches/daily/rss?geo=BR",
]


def _get_trending_keywords() -> set:
    """
    Fetches Google Trends daily RSS for US/GB/BR and returns a set of lowercase
    keywords extracted from trending titles. Returns empty set on any failure.
    """
    keywords: set = set()
    for feed_url in _TRENDS_FEEDS:
        try:
            parsed = feedparser.parse(
                feed_url,
                request_headers={"User-Agent": "GlobalBR-News-Bot/3.0 (+https://non-s.github.io)"},
            )
            for entry in parsed.get("entries", []):
                title = getattr(entry, "title", "")
                for word in title.split():
                    word = word.lower().strip(".,!?\"'()-")
                    if len(word) > 4 and word not in _TRENDING_STOP_WORDS and word.isalpha():
                        keywords.add(word)
        except Exception:
            continue
    return keywords


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

from utils.ranking import entry_relevance_score as _entry_relevance_score


def fetch_feed(feed_config: dict, max_override: int | None = None) -> int:
    """
    Processa um feed RSS e cria posts novos.
    Retorna o número de posts criados.
    max_override limita a criação abaixo de MAX_PER_FEED (usado pelo limite global).
    """
    name      = feed_config["name"]
    url       = feed_config["url"]
    category  = feed_config["category"]
    base_tags = feed_config["tags"]
    source    = feed_config["source"]
    limit     = min(MAX_PER_FEED, max_override) if max_override is not None else MAX_PER_FEED

    log.info(f"📡 Processando feed: {name} ({url})")

    try:
        parsed = feedparser.parse(url, request_headers={
            "User-Agent": "GlobalBR-News-Bot/3.0 (+https://non-s.github.io)"
        })
    except Exception as e:
        log.error(f"  ❌ Erro ao ler feed {name}: {e}")
        _feed_failures[name] = _feed_failures.get(name, 0) + 1
        if _feed_failures[name] >= _DEAD_FEED_THRESHOLD:
            log.warning(f"  💀 Feed possivelmente morto ({_feed_failures[name]} falhas consecutivas): {name}")
        return 0

    if parsed.bozo and not parsed.entries:
        exc = getattr(parsed, 'bozo_exception', None)
        log.warning(f"  ⚠️  Feed inválido (bozo, sem entradas): {name} — {exc}")
        _feed_failures[name] = _feed_failures.get(name, 0) + 1
        if _feed_failures[name] >= _DEAD_FEED_THRESHOLD:
            log.warning(f"  💀 Feed possivelmente morto ({_feed_failures[name]} falhas consecutivas): {name}")
        return 0
    elif parsed.bozo:
        log.debug(f"  ⚠️  Feed com bozo mas tem entradas: {parsed.bozo_exception}")

    entries = parsed.entries
    if not entries:
        log.info(f"  ℹ️  Nenhuma entrada encontrada em {name}")
        _feed_failures[name] = _feed_failures.get(name, 0) + 1
        return 0

    # Reset failure counter on success
    _feed_failures[name] = 0
    log.info(f"  📋 {len(entries)} entradas encontradas")

    # ── Pre-filter / pre-rank entries before we burn AI on them ─────
    # Quality > volume. We sort entries by a lightweight score (no AI,
    # no network) so the AI enrichment slots go to the strongest stories
    # in the feed, not just whoever happens to be at the top.
    entries = sorted(entries, key=_entry_relevance_score, reverse=True)

    created_count = 0

    for entry in entries:
        if created_count >= limit:
            break

        try:
            title       = sanitize_text(getattr(entry, "title", ""))
            link        = getattr(entry, "link", "")
            description = extract_description(entry)
            pub_date    = parse_date(entry)
            image_url   = extract_image(entry)

            if not title or not link:
                log.debug("  ⏭  Item sem título ou link, pulando.")
                continue

            # ── Link checker — skip dead source URLs ──────────────
            if not _check_source_url(link):
                log.warning(f"  ⚠️  Source URL returned error (skipping): {link[:80]}")
                continue

            # Filtro de descrição mínima
            if len(description) < MIN_DESCRIPTION_LEN:
                log.info(f"  ⏭  Descrição muito curta ({len(description)} chars): {title[:60]}")
                continue

            # Filtro de qualidade avançado
            ok, reason = _quality_check(title, description)
            if not ok:
                log.info(f"  ⏭  Quality check failed ({reason}): {title[:60]}")
                continue

            # Filtro de qualidade / relevância
            if is_blacklisted(title, description):
                log.info(f"  🚫 Conteúdo filtrado (blacklist): {title[:60]}")
                continue

            # Enriquece com metadados OG do artigo original
            og = fetch_og_metadata(link)
            if og["description"] and len(og["description"]) > len(description):
                log.debug(f"  📈 OG desc ({len(og['description'])} chars) > RSS desc ({len(description)} chars)")
                description = og["description"]
            if og["image"] and not image_url:
                image_url = og["image"]

            # Detecta categoria e tags extras por palavra-chave
            extra_cat, extra_tags = get_extra_tags(title, description)
            categories = [category]
            if extra_cat and extra_cat not in categories:
                categories.append(extra_cat)

            # ── Entity extraction → extra tags ────────────────────
            entity_tags = _extract_entities(title, description)
            all_tags = list(dict.fromkeys(base_tags + extra_tags + entity_tags))

            slug     = slugify(title)
            filename = post_filename(pub_date, slug)

            if post_exists(filename, link):
                log.debug(f"  ⏭  Post já existe: {filename}")
                continue

            # ── Title similarity deduplication ────────────────────
            similar_found = False
            for existing_title, existing_file in _load_known_titles():
                if _titles_too_similar(title, existing_title):
                    log.info(
                        f"  ⏭  Título similar (Levenshtein/Jaccard) a '{existing_file}': {title[:60]}"
                    )
                    similar_found = True
                    break
            if similar_found:
                continue

            # ── AI Enhancement (Mistral) ──────────────────────────
            ai = _ai_enhance_post(title, description, og.get("body", ""), category, source)
            if ai.get("seo_title") and 10 < len(ai["seo_title"]) <= 70:
                log.info(f"  🤖 AI title: {ai['seo_title'][:60]}")
                title = ai["seo_title"]
            if ai.get("meta_description") and len(ai["meta_description"]) > 50:
                description = ai["meta_description"][:160]
            if ai.get("keywords"):
                all_tags = list(dict.fromkeys(all_tags + [k.lower().replace(" ", "-") for k in ai["keywords"]]))

            # ── Quality gate (post-AI) ──────────────────────────────
            # We don't want to publish thin posts even if they pass
            # the pre-AI quality check. After enrichment the AI either
            # produced a substantial article_body + key_points + tl_dr
            # (high score) or it didn't (low score). Drop the lows.
            _score, _notes = _quality_score(
                title=title,
                description=description,
                ai_payload=ai,
                body_chars=len(og.get("body", "") or ""),
            )
            _gate = int(os.environ.get("FETCH_QUALITY_THRESHOLD", "6"))
            if _score < _gate:
                log.info(
                    f"  ⏭  Quality gate {_score}/10 < {_gate} ({', '.join(_notes)[:120]}): {title[:60]}"
                )
                continue

            # ── Imagem: source image (lazy — skip OG gen if usable) ───
            # Check the source image first. If it's usable, skip the
            # Pollinations + Pillow + WebP pipeline entirely — that
            # saves ~3-5s per post in the common case.
            if image_url and _validate_image_url(image_url):
                log.debug(f"  🖼  Using source image: {image_url[:60]}")
            else:
                # Source missing/broken: synthesise an OG image locally.
                image_url = _generate_og_image(title, category, slug)
                log.info(f"  🎨 Generated OG image: {image_url}")
            # Hard requirement: every published post must have a usable cover image.
            if not _validate_image_url(image_url):
                # Last-ditch: try the Pollinations fallback.
                fallback = _news_image_url(title, category)
                if _validate_image_url(fallback):
                    image_url = fallback
                    log.info(f"  🎨 Fallback Pollinations OK: {fallback[:60]}")
                else:
                    log.warning(
                        f"  ⏭  Skipping post — no usable image (source, OG, "
                        f"fallback all failed): {title[:80]}"
                    )
                    continue

            sentiment   = _sentiment_score(f"{title} {description}")
            fact_check  = _fact_check_score(title, description)

            description_ptbr = ""

            # ── Crypto prices for business posts ─────────────────
            crypto_prices_for_post: dict | None = None
            if category == "business":
                combined_text = (title + " " + description).lower()
                if any(kw in combined_text for kw in _CRYPTO_KEYWORDS):
                    crypto_prices_for_post = _get_crypto_prices() or None
                    if crypto_prices_for_post:
                        log.debug(f"  💰 Crypto prices attached to business post")

            # ── Story continuation detection ──────────────────────
            continuation = _find_related_story(title, all_tags, category)
            last_updated_val = pub_date.strftime("%Y-%m-%d") if continuation else ""

            # ── Find related/continuation post for cross-linking ──
            known_posts_list = [(fn, t) for t, fn in _load_known_titles()]
            related_post_path = _find_continuation(title, known_posts_list)
            related_post_url = ""
            if related_post_path:
                m_rp = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$', related_post_path)
                if m_rp:
                    rp_cat = category
                    related_post_url = f"/{rp_cat}/{m_rp.group(1)}/{m_rp.group(2)}/{m_rp.group(3)}/{m_rp.group(4)}/"

            frontmatter = build_frontmatter(
                title             = title,
                date              = pub_date,
                categories        = categories,
                tags              = all_tags,
                author            = "GlobalBR News",
                description       = description,
                source_url        = link,
                source_name       = source,
                image             = image_url,
                keywords          = ai.get("keywords", []),
                faq               = ai.get("faq", []),
                sentiment         = sentiment,
                key_points        = ai.get("key_points", []),
                fact_check        = fact_check,
                image_caption     = ai.get("image_caption", ""),
                last_updated      = last_updated_val,
                wikipedia_summary = ai.get("wikipedia_summary", ""),
                description_ptbr  = description_ptbr,
                crypto_prices     = crypto_prices_for_post,
                hook              = ai.get("hook", ""),
                related_post      = related_post_url,
                tl_dr             = ai.get("tl_dr", ""),
                lead              = ai.get("lead", ""),
                content_type      = ai.get("content_type", ""),
                entities          = ai.get("entities", []),
            )

            post_content = build_content(
                title       = title,
                description = description,
                source_url  = link,
                source_name = source,
                date        = pub_date,
                categories  = categories,
                tags        = all_tags,
                body        = og.get("body", ""),
                ai_body     = ai.get("article_body", ""),
            )

            # Prepend continuation link if found
            if continuation:
                post_content = continuation + post_content

            post_content = _add_internal_links(post_content, category, Path(filename).stem)
            pt_section = _add_pt_summary(title, description, category)
            post_content += pt_section
            # Spanish summary — top 3 categories by global readership
            if category in {"world", "politics", "business", "technology", "science", "health", "war"}:
                es_section = _add_es_summary(title, description, category)
                post_content += es_section

            post_path = POSTS_DIR / filename
            post_path.write_text(frontmatter + "\n" + post_content, encoding="utf-8")

            log.info(f"  ✅ Post criado: {filename}" + (f" [fact:{fact_check}]" if fact_check else ""))
            _load_known_urls().add(link)
            _load_known_titles().insert(0, (title, filename))
            created_count += 1

            # Track source for diversity check (passed via return value extension below)
            if not hasattr(fetch_feed, "_source_counts"):
                fetch_feed._source_counts = {}
            fetch_feed._source_counts[source] = fetch_feed._source_counts.get(source, 0) + 1

        except Exception as e:
            log.error(f"  ❌ Erro ao processar item '{getattr(entry, 'title', '?')}': {e}")
            continue

    log.info(f"  📝 {created_count} posts criados para {name}")
    return created_count


def _process_article_dict(item: dict, max_override: int | None = None) -> int:
    """
    Processes a single article dict (from HackerNews / DEV.to) through
    the same quality, dedup, AI-enhance, and post-creation pipeline used by fetch_feed.
    Returns 1 if a post was created, 0 otherwise.
    """
    title       = item.get("title", "")
    link        = item.get("link", "")
    description = item.get("description", "")
    pub_date    = item.get("pub_date", datetime.now(timezone.utc))
    image_url   = item.get("image_url", "")
    category    = item.get("category", "technology")
    base_tags   = item.get("tags", [])
    source      = item.get("source", "Unknown")

    if not title or not link:
        return 0

    # Check global limit BEFORE doing any expensive processing
    if max_override is not None and max_override <= 0:
        return 0

    if not _check_source_url(link):
        log.warning(f"  ⚠️  Source URL returned error (skipping): {link[:80]}")
        return 0

    if len(description) < MIN_DESCRIPTION_LEN:
        log.info(f"  ⏭  Descrição muito curta ({len(description)} chars): {title[:60]}")
        return 0

    ok, reason = _quality_check(title, description)
    if not ok:
        log.info(f"  ⏭  Quality check failed ({reason}): {title[:60]}")
        return 0

    if is_blacklisted(title, description):
        log.info(f"  🚫 Conteúdo filtrado (blacklist): {title[:60]}")
        return 0

    og = fetch_og_metadata(link)
    if og["description"] and len(og["description"]) > len(description):
        description = og["description"]
    if og["image"] and not image_url:
        image_url = og["image"]

    extra_cat, extra_tags = get_extra_tags(title, description)
    categories = [category]
    if extra_cat and extra_cat not in categories:
        categories.append(extra_cat)
    all_tags = list(dict.fromkeys(base_tags + extra_tags))

    slug     = slugify(title)
    filename = post_filename(pub_date, slug)

    if post_exists(filename, link):
        log.debug(f"  ⏭  Post já existe: {filename}")
        return 0

    for existing_title, existing_file in _load_known_titles():
        if _titles_too_similar(title, existing_title):
            log.info(f"  ⏭  Título similar (Levenshtein/Jaccard) a '{existing_file}': {title[:60]}")
            return 0

    ai = _ai_enhance_post(title, description, og.get("body", ""), category, source)
    if ai.get("seo_title") and 10 < len(ai["seo_title"]) <= 70:
        title = ai["seo_title"]
    if ai.get("meta_description") and len(ai["meta_description"]) > 50:
        description = ai["meta_description"][:160]
    if ai.get("keywords"):
        all_tags = list(dict.fromkeys(all_tags + [k.lower().replace(" ", "-") for k in ai["keywords"]]))

    # ── Quality gate (post-AI) ──────────────────────────────────
    _score, _notes = _quality_score(
        title=title,
        description=description,
        ai_payload=ai,
        body_chars=len(og.get("body", "") or ""),
    )
    _gate = int(os.environ.get("FETCH_QUALITY_THRESHOLD", "6"))
    if _score < _gate:
        log.info(
            f"  ⏭  Quality gate {_score}/10 < {_gate} ({', '.join(_notes)[:120]}): {title[:60]}"
        )
        return 0

    # Lazy OG generation: skip the local Pillow render if the source
    # already has a usable image.
    if image_url and _validate_image_url(image_url):
        pass
    else:
        image_url = _generate_og_image(title, category, slug)
    if not _validate_image_url(image_url):
        fallback = _news_image_url(title, category)
        if _validate_image_url(fallback):
            image_url = fallback
        else:
            log.warning(
                f"  ⏭  Skipping post — no usable image: {title[:80]}"
            )
            return 0

    sentiment  = _sentiment_score(f"{title} {description}")
    fact_check = _fact_check_score(title, description)

    description_ptbr = ""

    crypto_prices_for_post: dict | None = None
    if category == "business":
        combined_text = (title + " " + description).lower()
        if any(kw in combined_text for kw in _CRYPTO_KEYWORDS):
            crypto_prices_for_post = _get_crypto_prices() or None

    continuation = _find_related_story(title, all_tags, category)
    last_updated_val = pub_date.strftime("%Y-%m-%d") if continuation else ""

    # ── Find related/continuation post for cross-linking ──────────
    known_posts_list = [(fn, t) for t, fn in _load_known_titles()]
    related_post_path = _find_continuation(title, known_posts_list)
    related_post_url = ""
    if related_post_path:
        m_rp = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$', related_post_path)
        if m_rp:
            related_post_url = f"/{category}/{m_rp.group(1)}/{m_rp.group(2)}/{m_rp.group(3)}/{m_rp.group(4)}/"

    frontmatter = build_frontmatter(
        title             = title,
        date              = pub_date,
        categories        = categories,
        tags              = all_tags,
        author            = "GlobalBR News",
        description       = description,
        source_url        = link,
        source_name       = source,
        image             = image_url,
        keywords          = ai.get("keywords", []),
        faq               = ai.get("faq", []),
        sentiment         = sentiment,
        key_points        = ai.get("key_points", []),
        fact_check        = fact_check,
        image_caption     = ai.get("image_caption", ""),
        last_updated      = last_updated_val,
        wikipedia_summary = ai.get("wikipedia_summary", ""),
        description_ptbr  = description_ptbr,
        crypto_prices     = crypto_prices_for_post,
        hook              = ai.get("hook", ""),
        related_post      = related_post_url,
        tl_dr             = ai.get("tl_dr", ""),
        lead              = ai.get("lead", ""),
        content_type      = ai.get("content_type", ""),
        entities          = ai.get("entities", []),
    )

    post_content = build_content(
        title       = title,
        description = description,
        source_url  = link,
        source_name = source,
        date        = pub_date,
        categories  = categories,
        tags        = all_tags,
        body        = og.get("body", ""),
        ai_body     = ai.get("article_body", ""),
    )
    if continuation:
        post_content = continuation + post_content
    post_content = _add_internal_links(post_content, category, Path(filename).stem)
    pt_section = _add_pt_summary(title, description, category)
    post_content += pt_section
    # Spanish summary — top 3 categories by global readership
    if category in {"world", "politics", "business", "technology", "science", "health", "war"}:
        es_section = _add_es_summary(title, description, category)
        post_content += es_section

    post_path = POSTS_DIR / filename
    post_path.write_text(frontmatter + "\n" + post_content, encoding="utf-8")

    log.info(f"  ✅ Post criado [{source}]: {filename}")
    _load_known_urls().add(link)
    _load_known_titles().insert(0, (title, filename))
    if not hasattr(fetch_feed, "_source_counts"):
        fetch_feed._source_counts = {}
    fetch_feed._source_counts[source] = fetch_feed._source_counts.get(source, 0) + 1
    return 1


# ============================================================
# MILESTONE POSTS
# ============================================================

_MILESTONE_MARKERS = Path("_data/milestones.json")


def _load_milestone_markers() -> set[str]:
    if not _MILESTONE_MARKERS.exists():
        return set()
    try:
        return set(json.loads(_MILESTONE_MARKERS.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_milestone_markers(markers: set[str]) -> None:
    _MILESTONE_MARKERS.parent.mkdir(parents=True, exist_ok=True)
    _MILESTONE_MARKERS.write_text(
        json.dumps(sorted(markers), indent=2),
        encoding="utf-8",
    )


def _check_milestones(new_posts_count: int) -> None:
    """Create a milestone post when a category hits 100/250/500/1000 posts."""
    if new_posts_count == 0:
        return
    import glob as _glob

    cat_counts: dict[str, int] = {}
    for f in _glob.glob("_posts/*.md"):
        try:
            with open(f, encoding="utf-8") as fp:
                content = fp.read()
            m = re.search(r'^categories:\s*\[([^\]]+)\]', content, re.MULTILINE)
            if m:
                cats = [c.strip() for c in m.group(1).split(",")]
                for cat in cats:
                    if cat and cat not in ("roundup", "digest"):
                        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        except Exception:
            pass

    markers = _load_milestone_markers()
    legacy_dir = Path("_posts")

    MILESTONES = [100, 250, 500, 1000]
    for cat, count in cat_counts.items():
        for milestone in MILESTONES:
            marker_key = f"{cat}-{milestone}"
            # Migrate older marker files that lived inside _posts/.
            legacy_marker = legacy_dir / f"milestone-{cat}-{milestone}.md"
            if legacy_marker.exists():
                markers.add(marker_key)
                try:
                    legacy_marker.unlink()
                except OSError:
                    pass
            if count < milestone or marker_key in markers:
                continue
            date_str = datetime.now().strftime("%Y-%m-%d")
            slug = f"{date_str}-{cat}-{milestone}-articles-milestone"
            filepath = legacy_dir / f"{slug}.md"
            if filepath.exists():
                markers.add(marker_key)
                continue
            # Generate a real OG image (Pillow + WebP, on-disk) instead of
            # relying on the bare Pollinations URL. The milestone Short last
            # week shipped with a grey thumbnail because the Pollinations CDN
            # returned 500 at upload time and the post had no on-disk image.
            milestone_slug = (
                f"{date_str}-{cat}-{milestone}-articles-milestone"
            )
            milestone_img = _generate_og_image(
                f"🎉 {milestone} articles published in {cat}",
                cat,
                milestone_slug,
            )
            if not _validate_image_url(milestone_img):
                milestone_img = _news_image_url(
                    f"{milestone} articles milestone {cat} news celebration",
                    cat,
                )
            if not _validate_image_url(milestone_img):
                log.warning(
                    f"⏭  Skipping milestone post — no usable image: "
                    f"{cat}-{milestone}"
                )
                continue
            milestone_content = f"""---
title: "🎉 {milestone} Articles in {cat.capitalize()}!"
date: {datetime.now(timezone.utc).isoformat()}
categories: [{cat}]
tags: [milestone, {cat}]
description: "GlobalBR News has published {milestone} articles in the {cat.capitalize()} category."
featured: true
sentiment: "positive"
image: "{milestone_img}"
image_alt: "GlobalBR News {milestone} articles milestone in {cat} category"
---

We've reached a milestone: **{milestone} articles** published in the **{cat.capitalize()}** category!

Thank you for reading GlobalBR News.
"""
            try:
                filepath.write_text(milestone_content, encoding="utf-8")
                markers.add(marker_key)
                log.info(f"🎉 Milestone post created: {filepath}")
            except Exception as exc:
                log.warning(f"Milestone post creation failed: {exc}")
            break  # only one milestone per cat per run

    _save_milestone_markers(markers)


def _save_last_run(total_created: int, start_time: float) -> None:
    """Write _data/last_run.json with run summary for health dashboards."""
    import time as _time
    dead_feeds = [name for name, fails in _feed_failures.items() if fails >= _DEAD_FEED_THRESHOLD]
    data: dict = {
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "duration_s":    round(_time.time() - start_time, 1),
        "posts_created": total_created,
        "feeds_total":   len(FEEDS),
        "feeds_dead":    len(dead_feeds),
        "dead_feed_names": dead_feeds,
    }
    try:
        dead_path = Path("_data/dead_feeds.json")
        dead_path.parent.mkdir(exist_ok=True)
        dead_path.write_text(
            json.dumps({"updated": data["timestamp"], "dead": dead_feeds}, indent=2),
            encoding="utf-8",
        )
        Path("_data/last_run.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning(f"Could not write run summary: {exc}")


def main():
    import time as _time
    _run_start = _time.time()

    log.info("=" * 60)
    log.info(f"🚀 GlobalBR News — Fetch iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    # Global timeout — bail out after 55 min so CI job stays within 60 min limit
    _RUN_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT_S", "3300"))

    POSTS_DIR.mkdir(exist_ok=True)

    # ── Cleanup old posts ─────────────────────────────────────────
    try:
        max_age = int(os.environ.get("POST_MAX_AGE_DAYS", "90"))
        cleanup_old_posts(max_age_days=max_age)
    except Exception as exc:
        log.warning(f"Cleanup failed: {exc}")

    # Reset per-run source tracking
    if hasattr(fetch_feed, "_source_counts"):
        fetch_feed._source_counts = {}

    total_created = 0

    trending = _get_trending_keywords()
    if trending:
        log.info(f"🔥 Trending keywords loaded: {len(trending)} terms")

    # ── Pre-fetch crypto prices once per run ──────────────────────
    try:
        _get_crypto_prices()
    except Exception as exc:
        log.debug(f"Crypto prices pre-fetch failed: {exc}")

    # ── Parallel feed fetch ───────────────────────────────────────
    # 135 feeds × ~10s each was the dominant cost (>20 min/run). Running
    # 10 in parallel cuts that to ~2-3 min without changing each feed's
    # internal dedup/AI pipeline. A Lock around `total_created` keeps
    # the global cap honest across threads.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock as _Lock

    counter_lock = _Lock()
    counter = {"created": 0}

    def _budget_left() -> int:
        with counter_lock:
            return MAX_POSTS_PER_RUN - counter["created"]

    def _process_one(feed: dict) -> int:
        # Each worker rechecks the global budget + timeout before starting
        # so we don't burn AI quota when other workers already filled the
        # bucket.
        if _budget_left() <= 0:
            return 0
        if _time.time() - _run_start > _RUN_TIMEOUT:
            return 0
        feed_words = set((feed["name"] + " " + feed.get("category", "")).lower().split())
        budget = _budget_left()
        if trending and feed_words & trending:
            override = min(budget, MAX_PER_FEED + 1)
        else:
            override = min(budget, MAX_PER_FEED)
        try:
            n = fetch_feed(feed, max_override=override)
        except Exception as exc:
            log.warning(f"  ⚠️ feed {feed['name']} crashed: {exc}")
            n = 0
        if n:
            with counter_lock:
                counter["created"] += n
        if SLEEP_BETWEEN_FEEDS > 0:
            sleep(SLEEP_BETWEEN_FEEDS)
        return n

    log.info(f"📡 Processing {len(FEEDS)} feeds with {FEED_WORKERS} workers")
    with ThreadPoolExecutor(max_workers=FEED_WORKERS) as executor:
        futures = [executor.submit(_process_one, feed) for feed in FEEDS]
        for fut in as_completed(futures):
            # We don't strictly need fut.result() — the worker already
            # updated the counter. But pulling it surfaces unexpected
            # exceptions in the log.
            try:
                fut.result()
            except Exception as exc:
                log.debug(f"feed worker exception: {exc}")
            if counter["created"] >= MAX_POSTS_PER_RUN:
                # Cancel pending futures we can; the running ones will
                # honour their own budget check above.
                for f in futures:
                    f.cancel()
                break
            if _time.time() - _run_start > _RUN_TIMEOUT:
                for f in futures:
                    f.cancel()
                break

    total_created = counter["created"]
    log.info(f"📊 Feeds done — {total_created}/{MAX_POSTS_PER_RUN} posts created")

    # ── HackerNews extra source ───────────────────────────────────
    if total_created < MAX_POSTS_PER_RUN:
        log.info("📡 Fetching HackerNews top stories...")
        try:
            hn_items = fetch_hackernews(max_items=20, min_score=100)
            for item in hn_items:
                if total_created >= MAX_POSTS_PER_RUN:
                    break
                total_created += _process_article_dict(item)
                sleep(1)
        except Exception as exc:
            log.warning(f"HackerNews processing failed: {exc}")

    # ── DEV.to extra source ───────────────────────────────────────
    if total_created < MAX_POSTS_PER_RUN:
        log.info("📡 Fetching DEV.to articles...")
        try:
            devto_items = fetch_devto()
            for item in devto_items:
                if total_created >= MAX_POSTS_PER_RUN:
                    break
                total_created += _process_article_dict(item)
                sleep(1)
        except Exception as exc:
            log.warning(f"DEV.to processing failed: {exc}")

    # ── Keyless trending discovery (Reddit + Wikipedia Current Events) ─
    # Implemented in utils/public_sources.py — no API keys required.
    if total_created < MAX_POSTS_PER_RUN:
        try:
            from utils.public_sources import (
                fetch_reddit_trending,
                fetch_wikipedia_current_events,
            )
        except Exception as exc:
            log.debug(f"public_sources unavailable: {exc}")
        else:
            log.info("📡 Fetching Reddit trending threads...")
            try:
                for item in fetch_reddit_trending():
                    if total_created >= MAX_POSTS_PER_RUN:
                        break
                    if _time.time() - _run_start > _RUN_TIMEOUT:
                        break
                    total_created += _process_article_dict(item)
                    sleep(1)
            except Exception as exc:
                log.warning(f"Reddit processing failed: {exc}")

            log.info("📡 Fetching Wikipedia Current Events portal...")
            try:
                for item in fetch_wikipedia_current_events(days=1):
                    if total_created >= MAX_POSTS_PER_RUN:
                        break
                    if _time.time() - _run_start > _RUN_TIMEOUT:
                        break
                    total_created += _process_article_dict(item)
                    sleep(1)
            except Exception as exc:
                log.warning(f"Wikipedia current events processing failed: {exc}")

    # ── Source diversity check ────────────────────────────────────
    source_counts = getattr(fetch_feed, "_source_counts", {})
    if source_counts:
        _check_source_diversity(source_counts)

    # ── Daily roundup ─────────────────────────────────────────────
    try:
        create_daily_roundup()
    except Exception as exc:
        log.warning(f"Daily roundup failed: {exc}")

    # ── Weekly digest (Sundays only) ──────────────────────────────
    try:
        create_weekly_digest()
    except Exception as exc:
        log.warning(f"Weekly digest failed: {exc}")

    # ── Weekly stats post (Sundays only) ──────────────────────────
    try:
        _generate_weekly_stats_post()
    except Exception as exc:
        log.warning(f"Weekly stats post failed: {exc}")

    # ── Milestone posts ───────────────────────────────────────────
    try:
        _check_milestones(total_created)
    except Exception as exc:
        log.warning(f"Milestone check failed: {exc}")

    # ── Save run summary ──────────────────────────────────────────
    try:
        _save_last_run(total_created, _run_start)
    except Exception as exc:
        log.warning(f"Run summary failed: {exc}")

    log.info("=" * 60)
    log.info(f"✨ Concluído! Total de posts criados: {total_created}/{MAX_POSTS_PER_RUN}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
