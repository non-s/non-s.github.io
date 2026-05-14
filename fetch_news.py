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
import hashlib
import unicodedata
import math
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

# HTTP session reutilizável (melhor performance)
_session = requests.Session()
_session.headers.update({"User-Agent": "GlobalBR-News-Bot/3.0 (+https://non-s.github.io)"})

# ============================================================
# AI TEXT — Groq (primário) + Gemini Flash (secundário) + Pollinations (fallback)
# ============================================================

GROQ_API_URL          = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL            = "llama-3.3-70b-versatile"
GEMINI_API_URL        = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
POLLINATIONS_TEXT_URL = "https://text.pollinations.ai/"

def _ai_text(prompt: str, system: str = "", seed: int = 0, timeout: int = 30) -> str:
    """
    Gera texto via:
    1. Groq (Llama 3.3 70B — rápido, gratuito com chave)
    2. Google Gemini 1.5 Flash (15 req/min, 1M tokens/dia — gratuito com chave)
    3. Pollinations.ai (sem chave, sem limites)
    """
    sys_msg = system or "You are a professional journalist and SEO expert. Be concise and accurate."

    # ── 1. Groq ──────────────────────────────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            r = _session.post(
                GROQ_API_URL,
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": sys_msg},
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2500,
                },
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            log.warning(f"Groq error (tentando Gemini): {exc}")

    # ── 2. Gemini 1.5 Flash ───────────────────────────────────
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            r = _session.post(
                f"{GEMINI_API_URL}?key={gemini_key}",
                json={
                    "contents": [{"parts": [{"text": f"{sys_msg}\n\n{prompt}"}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2000},
                },
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            log.warning(f"Gemini error (tentando Pollinations): {exc}")

    # ── 3. Pollinations.ai — sem chave, gratuito ─────────────
    try:
        r = _session.post(
            POLLINATIONS_TEXT_URL,
            json={
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user",   "content": prompt},
                ],
                "model":      "openai",
                "seed":       seed or abs(hash(prompt)) % 9999,
                "private":    True,
                "max_tokens": 2500,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "choices" in data:
            return data["choices"][0]["message"]["content"].strip()
        return str(data).strip()
    except Exception as exc:
        log.warning(f"Pollinations error: {exc}")
        return ""

# Alias para compatibilidade interna
_pollinations_text = _ai_text


# ============================================================
# WIKIPEDIA API — Enriquecimento de artigos
# ============================================================

def _fetch_wikipedia_summary(query: str) -> str:
    """Busca resumo do Wikipedia em inglês para o título dado. Retorna até 500 chars."""
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(query)}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "GlobalBRNews/1.0"})
        if r.status_code == 200:
            data = r.json()
            return data.get("extract", "")[:500]
    except Exception:
        pass
    return ""


# ============================================================
# GOOGLE FACT CHECK TOOLS API
# ============================================================

def _fact_check_api(claim_text: str):
    """
    Consulta Google Fact Check Tools API. Retorna 'false', 'verified', 'developing' ou None.
    Só funciona se GOOGLE_FACT_CHECK_API_KEY estiver definida.
    """
    key = os.getenv("GOOGLE_FACT_CHECK_API_KEY")
    if not key:
        return None
    url = (
        f"https://factchecktools.googleapis.com/v1alpha1/claims:search"
        f"?key={key}&query={requests.utils.quote(claim_text[:200])}&languageCode=en"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            claims = data.get("claims", [])
            if claims:
                rating = claims[0].get("claimReview", [{}])[0].get("textualRating", "")
                rating_lower = rating.lower()
                if any(w in rating_lower for w in ["false", "pants on fire", "mostly false"]):
                    return "false"
                elif any(w in rating_lower for w in ["true", "mostly true", "correct"]):
                    return "verified"
                return "developing"
    except Exception:
        pass
    return None


# ============================================================
# DEEPL — Tradução PT-BR
# ============================================================

def _translate_to_ptbr(text: str, api_key: str):
    """Traduz texto para PT-BR usando DeepL API Free. Retorna None em caso de falha."""
    if not api_key or not text:
        return None
    try:
        r = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"auth_key": api_key, "text": text, "target_lang": "PT-BR"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["translations"][0]["text"]
    except Exception:
        pass
    return None


# ============================================================
# COHERE — Embeddings semânticos para artigos relacionados
# ============================================================

_EMBEDDINGS_FILE = Path("_data/embeddings.json")

def _get_cohere_embedding(text: str, api_key: str):
    """Gera embedding via Cohere embed-english-v3.0. Retorna lista de floats ou None."""
    try:
        r = requests.post(
            "https://api.cohere.ai/v1/embed",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "texts": [text[:512]],
                "model": "embed-english-v3.0",
                "input_type": "search_document",
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["embeddings"][0]
    except Exception:
        pass
    return None


def _cosine_similarity(a: list, b: list) -> float:
    """Calcula similaridade de cosseno entre dois vetores."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _load_embeddings() -> dict:
    """Carrega embeddings do arquivo _data/embeddings.json."""
    try:
        if _EMBEDDINGS_FILE.exists():
            return json.loads(_EMBEDDINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_embeddings(data: dict) -> None:
    """Salva embeddings em _data/embeddings.json."""
    try:
        _EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _EMBEDDINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.debug(f"Failed to save embeddings: {exc}")


def _store_cohere_embedding(title: str, text: str) -> None:
    """Gera e persiste embedding para o título dado, se COHERE_API_KEY existir."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        return
    try:
        embedding = _get_cohere_embedding(text, api_key)
        if embedding:
            data = _load_embeddings()
            data[title] = embedding
            _save_embeddings(data)
    except Exception:
        pass


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


def cleanup_old_posts(max_age_days: int = 90) -> int:
    """
    Scans _posts/ for .md files older than max_age_days.
    Skips roundup/digest files. Deletes old posts and returns count deleted.
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    deleted = 0
    for post_path in POSTS_DIR.glob("*.md"):
        filename = post_path.name
        # Skip roundup and digest files
        if "roundup" in filename or "digest" in filename:
            continue
        # Parse date from YYYY-MM-DD prefix
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


def _upload_to_cloudinary(local_path, public_id=None):
    """Upload image to Cloudinary and return CDN URL. Returns None if not configured or on error."""
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not all([cloud_name, api_key, api_secret]):
        return None
    try:
        import hashlib, time as _time
        timestamp = str(int(_time.time()))
        params = f"timestamp={timestamp}"
        if public_id:
            params = f"public_id={public_id}&{params}"
        signature = hashlib.sha1(f"{params}{api_secret}".encode()).hexdigest()
        with open(local_path, "rb") as f:
            files = {"file": f}
            data = {"api_key": api_key, "timestamp": timestamp, "signature": signature}
            if public_id:
                data["public_id"] = public_id
            r = requests.post(
                f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload",
                files=files, data=data, timeout=30
            )
        if r.status_code == 200:
            return r.json().get("secure_url")
    except Exception as e:
        logging.warning(f"Cloudinary upload failed: {e}")
    return None


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
    """
    fallback = _news_image_url(title, category)
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        out_dir = Path("assets/images/posts")
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

        # ── Dark overlay for readability ─────────────────────────
        overlay = Image.new("RGBA", (1200, 630), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        ov_draw.rectangle([(0, 0), (1200, 630)], fill=(0, 0, 0, 140))
        bg_img = bg_img.convert("RGBA")
        bg_img = Image.alpha_composite(bg_img, overlay).convert("RGB")
        draw = ImageDraw.Draw(bg_img)

        # ── Fonts ────────────────────────────────────────────────
        try:
            font_title = ImageFont.load_default(size=52)
            font_cat   = ImageFont.load_default(size=24)
            font_brand = ImageFont.load_default(size=22)
        except TypeError:
            # Older Pillow without size param
            font_title = ImageFont.load_default()
            font_cat   = ImageFont.load_default()
            font_brand = ImageFont.load_default()

        # ── Category label (top-left) ────────────────────────────
        cat_text = category.upper()
        draw.text((48, 36), cat_text, font=font_cat, fill=(249, 115, 22),
                  stroke_width=1, stroke_fill=(0, 0, 0))

        # ── Title (wrapped, centred vertically) ──────────────────
        max_w = 1200 - 96
        words = title.split()
        lines = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            # Estimate width: ~30px per char for size-52 default font
            if len(test) * 30 > max_w and current:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        lines = lines[:4]  # max 4 lines

        line_h = 64
        total_h = len(lines) * line_h
        y_start = (630 - total_h) // 2 - 20
        for line in lines:
            draw.text((48, y_start), line, font=font_title, fill=(255, 255, 255),
                      stroke_width=2, stroke_fill=(0, 0, 0))
            y_start += line_h

        # ── Branding (bottom-left) ───────────────────────────────
        draw.text((48, 630 - 52), "GlobalBR News", font=font_brand,
                  fill=(180, 180, 180), stroke_width=1, stroke_fill=(0, 0, 0))

        # ── Resize to max 1200x630 before saving (only if >= 400px wide) ─
        if bg_img.width >= 400:
            bg_img.thumbnail((1200, 630), Image.LANCZOS)

        # ── Save as JPG first, then convert to WebP ──────────────
        jpg_path = out_dir / f"{slug}.jpg"
        bg_img.save(str(jpg_path), "JPEG", quality=82, optimize=True)

        webp_path = _to_webp(jpg_path)
        final_local = str(webp_path) if (webp_path and webp_path.exists()) else (str(jpg_path) if jpg_path.exists() else None)
        local_url = f"/assets/images/posts/{slug}.webp" if (webp_path and webp_path.exists()) else (f"/assets/images/posts/{slug}.jpg" if jpg_path.exists() else fallback)

        # ── Cloudinary CDN upload (optional) ────────────────────
        if final_local:
            cdn_url = _upload_to_cloudinary(final_local, public_id=f"globalbr/{slug}")
            if cdn_url:
                return cdn_url

        return local_url

    except ImportError:
        log.debug("Pillow not available — using Pollinations URL for OG image")
        return fallback
    except Exception as exc:
        log.warning(f"OG image generation failed ({exc}) — falling back to Pollinations URL")
        return fallback

_POSITIVE_WORDS = {
    "breakthrough", "success", "discover", "innovation", "growth", "record",
    "victory", "achieve", "advance", "cure", "save", "improve", "rise",
    "hope", "peace", "agreement", "award", "celebrate", "launch", "win",
    "boom", "rally", "recover", "benefit", "progress", "surge", "historic",
}
_NEGATIVE_WORDS = {
    "war", "attack", "kill", "death", "dead", "crisis", "disaster", "collapse",
    "crash", "fall", "fail", "worst", "threat", "danger", "flood", "fire",
    "earthquake", "explosion", "shooting", "murder", "arrest", "ban", "loss",
    "decline", "drop", "recession", "conflict", "violence", "protest", "riot",
    "scandal", "corrupt", "terror", "bomb", "casualt", "injur", "evacuate",
}

def _sentiment_score(text: str) -> str:
    """Returns 'positive', 'negative', or 'neutral' based on keyword presence."""
    words = re.findall(r'\b\w+\b', text.lower())
    pos = sum(1 for w in words if any(w.startswith(p) for p in _POSITIVE_WORDS))
    neg = sum(1 for w in words if any(w.startswith(p) for p in _NEGATIVE_WORDS))
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


_FACT_VERIFIED_PHRASES = {
    "officials confirmed", "according to", "announced", "reported by",
    "confirmed by", "published by", "data shows", "study found",
    "research shows", "percent", "million", "billion", "january",
    "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "2024", "2025", "2026",
}
_FACT_DEVELOPING_PHRASES = {
    "reportedly", "sources say", "unconfirmed", "alleged", "claims",
    "rumored", "believed to", "said to be", "may have", "might have",
    "anonymous source", "sources close", "could be",
}
_FACT_OPINION_PHRASES = {
    "opinion", "analysis", "commentary", "editorial", "think",
    "perspective", "column", "op-ed", "viewpoint", "argue",
    "believe we should", "it is time to",
}
_FACT_SATIRE_PHRASES = {
    "satire", "parody", "humor", "humour", "spoof", "onion",
    "satirical", "comedic take",
}


def _fact_check_score(title: str, description: str) -> str | None:
    """
    Returns fact-check badge label: 'verified', 'developing', 'opinion', 'satire', or None.
    Checks title + description against known phrase sets.
    """
    combined = (title + " " + description).lower()
    for phrase in _FACT_SATIRE_PHRASES:
        if phrase in combined:
            return "satire"
    for phrase in _FACT_OPINION_PHRASES:
        if phrase in combined:
            return "opinion"
    for phrase in _FACT_DEVELOPING_PHRASES:
        if phrase in combined:
            return "developing"
    for phrase in _FACT_VERIFIED_PHRASES:
        if phrase in combined:
            return "verified"
    return None


_SPAM_PATTERNS = re.compile(
    r'\bclick here\b|\byou won\'t believe\b|\bshoking\b|\bshocking\b',
    re.IGNORECASE,
)


def _quality_check(title: str, description: str) -> tuple[bool, str]:
    """
    Returns (ok, reason). Posts failing quality check should be skipped.
    Checks:
    - Title too short (< 15 chars)
    - Description too short (< 50 chars)
    - Spam title patterns
    - All-caps title (> 80% uppercase letters)
    """
    if len(title) < 15:
        return False, f"title too short ({len(title)} chars)"
    if len(description) < 50:
        return False, f"description too short ({len(description)} chars)"
    if _SPAM_PATTERNS.search(title):
        return False, "spam pattern in title"
    letters = [c for c in title if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.80:
        return False, "title is ALL CAPS"
    return True, ""


def _fetch_wikipedia_summary(query: str) -> str:
    """Fetches a short Wikipedia extract for the given query (EN). Returns up to 500 chars."""
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(query)}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "GlobalBRNews/1.0"})
        if r.status_code == 200:
            data = r.json()
            return data.get("extract", "")[:500]
    except Exception:
        pass
    return ""


def _fact_check_api(claim_text: str) -> str | None:
    """
    Calls Google Fact Check Tools API to verify a claim.
    Returns 'false', 'verified', 'developing', or None if unavailable.
    Requires GOOGLE_FACT_CHECK_API_KEY env var.
    """
    key = os.getenv("GOOGLE_FACT_CHECK_API_KEY")
    if not key:
        return None
    url = (
        f"https://factchecktools.googleapis.com/v1alpha1/claims:search"
        f"?key={key}&query={requests.utils.quote(claim_text[:200])}&languageCode=en"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            claims = data.get("claims", [])
            if claims:
                rating = claims[0].get("claimReview", [{}])[0].get("textualRating", "")
                rating_lc = rating.lower()
                if any(w in rating_lc for w in ["false", "pants on fire", "mostly false"]):
                    return "false"
                elif any(w in rating_lc for w in ["true", "mostly true", "correct"]):
                    return "verified"
                return "developing"
    except Exception:
        pass
    return None


def _translate_to_ptbr(text: str, api_key: str) -> str | None:
    """Translate text to PT-BR using DeepL free API. Returns translated string or None."""
    if not api_key or not text:
        return None
    try:
        r = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"auth_key": api_key, "text": text, "target_lang": "PT-BR"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["translations"][0]["text"]
    except Exception:
        pass
    return None


def _get_cohere_embedding(text: str, api_key: str) -> list | None:
    """Returns an embedding vector from Cohere or None on failure."""
    try:
        r = requests.post(
            "https://api.cohere.ai/v1/embed",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "texts": [text[:512]],
                "model": "embed-english-v3.0",
                "input_type": "search_document",
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["embeddings"][0]
    except Exception:
        pass
    return None


# ── Embeddings cache ──────────────────────────────────────────
_EMBEDDINGS_PATH = Path("_data/embeddings.json")
_embeddings_cache: dict | None = None


def _load_embeddings() -> dict:
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache
    try:
        if _EMBEDDINGS_PATH.exists():
            _embeddings_cache = json.loads(_EMBEDDINGS_PATH.read_text(encoding="utf-8"))
        else:
            _embeddings_cache = {}
    except Exception:
        _embeddings_cache = {}
    return _embeddings_cache


def _save_embeddings(data: dict) -> None:
    try:
        _EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _EMBEDDINGS_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.debug(f"Failed to save embeddings: {exc}")


def _cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two equal-length vectors."""
    try:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
    except Exception:
        return 0.0


def _fetch_crypto_prices() -> dict:
    """Fetches current USD prices and 24h change for major cryptocurrencies from CoinGecko."""
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


# ── Crypto prices cache (fetched once per run) ─────────────────
_crypto_prices_cache: dict | None = None
_CRYPTO_PRICES_PATH = Path("_data/crypto_prices.json")
_CRYPTO_KEYWORDS = {"bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency", "ripple", "xrp", "cardano", "solana"}


def _get_crypto_prices() -> dict:
    """Returns cached crypto prices, fetching once per run if not yet loaded."""
    global _crypto_prices_cache
    if _crypto_prices_cache is not None:
        return _crypto_prices_cache
    _crypto_prices_cache = _fetch_crypto_prices()
    if _crypto_prices_cache:
        try:
            _CRYPTO_PRICES_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CRYPTO_PRICES_PATH.write_text(
                json.dumps(_crypto_prices_cache, ensure_ascii=False),
                encoding="utf-8",
            )
            log.info(f"CoinGecko prices saved to {_CRYPTO_PRICES_PATH}")
        except Exception as exc:
            log.debug(f"Failed to save crypto prices: {exc}")
    return _crypto_prices_cache


def _ai_enhance_post(title: str, description: str, body: str, category: str, source_name: str) -> dict:
    """
    Gera conteúdo SEO-otimizado por artigo via AI.
    Retorna dict com: seo_title, meta_description, article_body, faq, keywords, key_points.
    Also fetches Wikipedia summary and stores it under 'wikipedia_summary'.
    """
    combined = f"{description}\n\n{body}".strip()[:2000]
    cat = category.capitalize()
    prompt = (
        f'You are a world-class SEO journalist. Enhance this news article. '
        f'Respond ONLY with valid JSON, no markdown, no code blocks, no extra text.\n\n'
        f'Title: {title}\nCategory: {cat}\nSource: {source_name}\nContent:\n{combined}\n\n'
        f'Required JSON:\n'
        f'{{"seo_title":"Compelling SEO headline under 65 chars: use numbers when relevant (e.g. \'5 Countries...\'), ask a question, or create urgency. No clickbait. Must be accurate.","meta_description":"<150-155 chars ending with period>",'
        f'"key_points":["concise point 1","concise point 2","concise point 3"],'
        f'"article_body":"3 journalistic paragraphs 300-400 words total. Add ## H2 heading before each paragraph. '
        f'For key people/places/organizations add Wikipedia links: [Name](https://en.wikipedia.org/wiki/Name). No bullet points.",'
        f'"image_caption":"One sentence caption describing what the image likely shows, relevant to the article topic",'
        f'"faq":[{{"q":"question 1","a":"clear 1-2 sentence answer."}},'
        f'{{"q":"question 2","a":"clear 1-2 sentence answer."}},'
        f'{{"q":"question 3","a":"clear 1-2 sentence answer."}},'
        f'{{"q":"question 4","a":"clear 1-2 sentence answer."}},'
        f'{{"q":"question 5","a":"clear 1-2 sentence answer."}}],'
        f'"keywords":["primary keyword","secondary keyword","long tail phrase","topic","subtopic"]}}'
    )
    raw = _pollinations_text(prompt, seed=abs(hash(title)) % 9999, timeout=25)
    result = {}
    if raw:
        try:
            clean = re.sub(r'```(?:json)?\s*|\s*```', '', raw).strip()
            m = re.search(r'\{.*\}', clean, re.DOTALL)
            if m:
                result = json.loads(m.group())
        except Exception as e:
            log.warning(f"AI enhance parse error: {e} | raw[:120]={raw[:120]}")

    # ── Wikipedia enrichment ──────────────────────────────────
    wiki_summary = _fetch_wikipedia_summary(title)
    if wiki_summary:
        result["wikipedia_summary"] = wiki_summary

    return result

# ============================================================
# CONFIGURAÇÕES
# ============================================================

POSTS_DIR        = Path("_posts")
LOG_FILE         = "fetch_news.log"
MAX_PER_FEED     = 2                   # Max posts por feed por execução
MAX_POSTS_PER_RUN = 20                # Limite global por execução (muitos feeds agora)
REQUEST_TIMEOUT  = 15
SLEEP_BETWEEN_FEEDS = 2
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
    # ── Reddit (OAuth2, requer REDDIT_CLIENT_ID) ─────────────
    {
        "name":     "Reddit worldnews",
        "url":      "__reddit__worldnews",
        "category": "world",
        "tags":     ["reddit", "worldnews", "international"],
        "source":   "Reddit",
    },
    {
        "name":     "Reddit technology",
        "url":      "__reddit__technology",
        "category": "technology",
        "tags":     ["reddit", "technology", "tech"],
        "source":   "Reddit",
    },
    {
        "name":     "Reddit science",
        "url":      "__reddit__science",
        "category": "science",
        "tags":     ["reddit", "science", "research"],
        "source":   "Reddit",
    },
    {
        "name":     "Reddit geopolitics",
        "url":      "__reddit__geopolitics",
        "category": "world",
        "tags":     ["reddit", "geopolitics", "politics"],
        "source":   "Reddit",
    },
    {
        "name":     "Reddit economics",
        "url":      "__reddit__economics",
        "category": "business",
        "tags":     ["reddit", "economics", "finance"],
        "source":   "Reddit",
    },
]


# ============================================================
# EXTRA SOURCES — HackerNews, DEV.to, Reddit
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


_REDDIT_SUBREDDITS: dict[str, str] = {
    "worldnews":  "world",
    "technology": "technology",
    "science":    "science",
    "geopolitics": "politics",
    "economics":  "business",
}


def _get_reddit_token(client_id: str, client_secret: str) -> str | None:
    """Obtains a Reddit OAuth2 client-credentials access token."""
    try:
        r = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": "GlobalBRNews/1.0 by non-s"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception as exc:
        log.warning(f"Reddit OAuth2 token fetch failed: {exc}")
    return None


def fetch_reddit(max_per_sub: int = 5) -> list[dict]:
    """
    Fetches top posts from configured subreddits using Reddit OAuth2.
    Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars.
    Returns list of article dicts compatible with the post pipeline.
    """
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return []

    token = _get_reddit_token(client_id, client_secret)
    if not token:
        log.warning("Reddit: could not obtain access token — skipping.")
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "GlobalBRNews/1.0 by non-s",
    }
    items = []
    seen_links: set = set()

    for subreddit, category in _REDDIT_SUBREDDITS.items():
        try:
            r = requests.get(
                f"https://oauth.reddit.com/r/{subreddit}/top.json?limit={max_per_sub}&t=day",
                headers=headers,
                timeout=15,
            )
            if r.status_code != 200:
                log.debug(f"Reddit r/{subreddit} returned HTTP {r.status_code}")
                continue
            posts = r.json().get("data", {}).get("children", [])
            for post in posts:
                d = post.get("data", {})
                if d.get("is_self") or d.get("stickied"):
                    continue
                link = d.get("url", "")
                if not link or link in seen_links or link.startswith("https://www.reddit.com"):
                    continue
                seen_links.add(link)
                title = sanitize_text(d.get("title", ""))
                description = sanitize_text((d.get("selftext") or d.get("title", ""))[:400])
                if not title:
                    continue
                pub_date = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
                image_url = ""
                if d.get("thumbnail", "").startswith("http"):
                    image_url = d["thumbnail"]
                subreddit_tags = ["reddit", f"r-{subreddit}", category]
                items.append({
                    "title": title,
                    "link": link,
                    "description": description if len(description) >= 50 else title,
                    "pub_date": pub_date,
                    "image_url": image_url,
                    "category": category,
                    "tags": subreddit_tags,
                    "source": f"Reddit r/{subreddit}",
                })
        except Exception as exc:
            log.warning(f"Reddit r/{subreddit} fetch error: {exc}")
            continue

    log.info(f"Reddit: {len(items)} posts fetched across {len(_REDDIT_SUBREDDITS)} subreddits")
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

def slugify(text: str) -> str:
    """Converte texto em slug URL-amigável."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:80].strip("-")


def sanitize_text(text: str) -> str:
    """Remove caracteres problemáticos para YAML/Markdown."""
    if not text:
        return ""
    text = text.replace('"', "'").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def extract_description(entry) -> str:
    """Extrai descrição/resumo do item RSS, priorizando conteúdo mais longo."""
    candidates = []

    # Coleta todos os candidatos disponíveis
    if hasattr(entry, "content"):
        for c in entry.content:
            val = c.get("value", "")
            if val:
                candidates.append(val)

    if hasattr(entry, "summary"):
        candidates.append(entry.summary)

    if hasattr(entry, "description"):
        candidates.append(entry.description)

    # Limpa HTML e escolhe o mais longo
    best = ""
    for raw in candidates:
        clean = re.sub(r"<[^>]+>", " ", raw)
        clean = re.sub(r"&[a-z]+;", " ", clean)
        clean = re.sub(r"&#\d+;", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if len(clean) > len(best):
            best = clean

    return sanitize_text(best[:800])


def extract_image(entry) -> str:
    """Tenta extrair URL de imagem do item RSS."""
    if hasattr(entry, "media_content"):
        for m in entry.media_content:
            if m.get("type", "").startswith("image"):
                url = m.get("url", "")
                if url:
                    return url
    if hasattr(entry, "media_thumbnail"):
        for t in entry.media_thumbnail:
            url = t.get("url", "")
            if url:
                return url
    if hasattr(entry, "enclosures"):
        for e in entry.enclosures:
            if e.get("type", "").startswith("image"):
                url = e.get("href", "")
                if url:
                    return url
    content = ""
    if hasattr(entry, "content"):
        content = entry.content[0].get("value", "")
    elif hasattr(entry, "summary"):
        content = entry.summary
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return ""


def parse_date(entry) -> datetime:
    """Extrai data do item RSS como objeto datetime."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


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


def get_extra_tags(title: str, description: str) -> tuple[str, list]:
    """Detecta categoria e tags extras a partir do conteúdo."""
    combined = (title + " " + description).lower()
    for keyword, (cat, tags) in KEYWORD_CATEGORIES.items():
        if keyword in combined:
            return cat, tags
    return "", []


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


def _title_similarity(t1: str, t2: str) -> float:
    """Returns 0.0-1.0 similarity between two titles using Jaccard on non-stopword words."""
    w1 = set(re.sub(r'[^\w\s]', '', t1.lower()).split())
    w2 = set(re.sub(r'[^\w\s]', '', t2.lower()).split())
    stops = {
        'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
        'but', 'is', 'was', 'are', 'were', 'be', 'been', 'by', 'from', 'with',
        'this', 'that', 'it',
    }
    w1 -= stops
    w2 -= stops
    if not w1 or not w2:
        return 0.0
    intersection = w1 & w2
    union = w1 | w2
    return len(intersection) / len(union)


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
) -> str:
    """Monta o frontmatter YAML do post Jekyll."""
    date_str  = date.strftime("%Y-%m-%d %H:%M:%S %z").strip()
    cats_yaml = "[" + ", ".join(categories) + "]"
    tags_yaml = "[" + ", ".join(t for t in tags if t) + "]"

    # ── Google Fact Check API (priority) then heuristic ───────────
    if fact_check is None:
        fact_check = _fact_check_api(title)
    # If still None, fall through — caller already called _fact_check_score

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
    if last_updated:
        front += f'last_updated: "{last_updated}"\n'
    if image:
        front += f'image: "{image}"\n'
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
    Scans the last 20 posts in the same category.
    Uses Cohere embeddings (cosine similarity) when available;
    otherwise falls back to keyword overlap (2+ shared nouns).
    Returns a Markdown 'Continuing coverage' link or empty string.
    """
    # ── Cohere semantic search (if embeddings exist) ──────────────
    try:
        cohere_key = os.getenv("COHERE_API_KEY", "")
        if cohere_key:
            current_emb = _get_cohere_embedding(title, cohere_key)
            if current_emb:
                embeddings = _load_embeddings()
                best_title = None
                best_score = 0.0
                for stored_title, stored_emb in embeddings.items():
                    if stored_title == title:
                        continue
                    sim = _cosine_similarity(current_emb, stored_emb)
                    if sim > best_score:
                        best_score = sim
                        best_title = stored_title
                if best_title and best_score > 0.85:
                    # Try to find the file for best_title
                    for post_path in sorted(POSTS_DIR.glob("*.md"), reverse=True)[:40]:
                        try:
                            text = post_path.read_text(encoding="utf-8")
                            for line in text.splitlines():
                                if line.startswith("title:"):
                                    m = re.match(r'title:\s*"?([^"]+)"?\s*$', line)
                                    if m and m.group(1).strip() == best_title:
                                        stem = post_path.stem
                                        mm = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)$', stem)
                                        if mm:
                                            yr, mo, dy, sl = mm.group(1), mm.group(2), mm.group(3), mm.group(4)
                                            url = f"/{category}/{yr}/{mo}/{dy}/{sl}/"
                                            return f"> 📰 **Continuing coverage:** [{best_title}]({url})\n\n"
                        except Exception:
                            continue
    except Exception:
        pass

    # ── Keyword-based fallback ────────────────────────────────────
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

    frontmatter = f"""---
layout: post
title: "Daily News Roundup — {date_display}"
date: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000")}
categories: [roundup]
tags: [daily, news, roundup]
author: "GlobalBR News"
description: "Your daily roundup of the top {len(today_posts)} news stories for {date_display}."
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
# TRENDING KEYWORDS — Google Trends RSS
# ============================================================

def _get_trending_keywords() -> set:
    """
    Fetches Google Trends daily RSS for the US and returns a set of lowercase
    keywords extracted from trending titles. Returns empty set on any failure.
    """
    try:
        parsed = feedparser.parse(
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
            request_headers={"User-Agent": "GlobalBR-News-Bot/3.0 (+https://non-s.github.io)"},
        )
        keywords: set = set()
        for entry in parsed.get("entries", []):
            title = getattr(entry, "title", "")
            for word in title.split():
                word = word.lower().strip(".,!?\"'")
                if len(word) > 4:
                    keywords.add(word)
        return keywords
    except Exception:
        return set()


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

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
        return 0

    if parsed.bozo:
        log.warning(f"  ⚠️  Feed com problemas de parse: {parsed.bozo_exception}")

    entries = parsed.entries
    if not entries:
        log.info(f"  ℹ️  Nenhuma entrada encontrada em {name}")
        return 0

    log.info(f"  📋 {len(entries)} entradas encontradas")

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

            all_tags = list(dict.fromkeys(base_tags + extra_tags))

            slug     = slugify(title)
            filename = post_filename(pub_date, slug)

            if post_exists(filename, link):
                log.debug(f"  ⏭  Post já existe: {filename}")
                continue

            # ── Title similarity deduplication ────────────────────
            similar_found = False
            for existing_title, existing_file in _load_known_titles():
                sim = _title_similarity(title, existing_title)
                if sim > 0.6:
                    log.info(
                        f"  ⏭  Título similar ({sim:.2f}) a '{existing_file}': {title[:60]}"
                    )
                    similar_found = True
                    break
            if similar_found:
                continue

            # ── AI Enhancement (Pollinations — gratuito) ─────────
            ai = _ai_enhance_post(title, description, og.get("body", ""), category, source)
            if ai.get("seo_title") and 10 < len(ai["seo_title"]) <= 70:
                log.info(f"  🤖 AI title: {ai['seo_title'][:60]}")
                title = ai["seo_title"]
            if ai.get("meta_description") and len(ai["meta_description"]) > 50:
                description = ai["meta_description"][:160]
            if ai.get("keywords"):
                all_tags = list(dict.fromkeys(all_tags + [k.lower().replace(" ", "-") for k in ai["keywords"]]))

            # ── Imagem: OG > gerada localmente (Pillow+WebP) > Pollinations URL ─
            if not image_url:
                image_url = _generate_og_image(title, category, slug)
                log.info(f"  🎨 Generated OG image: {image_url}")
            else:
                log.debug(f"  🖼  Using source image: {image_url[:60]}")

            sentiment   = _sentiment_score(f"{title} {description}")
            # Heuristic fact-check (API override happens inside build_frontmatter)
            fact_check  = _fact_check_score(title, description)

            # ── DeepL translation PT-BR ───────────────────────────
            deepl_key = os.getenv("DEEPL_API_KEY", "")
            description_ptbr = ""
            if deepl_key:
                description_ptbr = _translate_to_ptbr(description[:500], deepl_key) or ""
                if description_ptbr:
                    log.debug(f"  🌍 DeepL PT-BR description translated")

            # ── Cohere embeddings ─────────────────────────────────
            cohere_key = os.getenv("COHERE_API_KEY", "")
            if cohere_key:
                emb = _get_cohere_embedding(f"{title} {description}", cohere_key)
                if emb:
                    embeddings = _load_embeddings()
                    embeddings[title] = emb
                    _save_embeddings(embeddings)
                    log.debug(f"  🔢 Cohere embedding saved for: {title[:50]}")

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

            post_path = POSTS_DIR / filename
            post_path.write_text(frontmatter + "\n" + post_content, encoding="utf-8")

            # ── DeepL: create PT post file if translation available ─
            if deepl_key and description_ptbr:
                try:
                    pt_dir = POSTS_DIR / "pt"
                    pt_dir.mkdir(parents=True, exist_ok=True)
                    pt_title = _translate_to_ptbr(title, deepl_key) or title
                    pt_fm = build_frontmatter(
                        title             = pt_title,
                        date              = pub_date,
                        categories        = categories,
                        tags              = all_tags,
                        author            = "GlobalBR News",
                        description       = description_ptbr[:160],
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
                    )
                    # Replace lang field for PT post
                    pt_fm = pt_fm.replace('lang: "en"', 'lang: "pt-BR"')
                    pt_content = build_content(
                        title       = pt_title,
                        description = description_ptbr,
                        source_url  = link,
                        source_name = source,
                        date        = pub_date,
                        categories  = categories,
                        tags        = all_tags,
                        body        = og.get("body", ""),
                        ai_body     = ai.get("article_body", ""),
                    )
                    pt_path = pt_dir / filename
                    pt_path.write_text(pt_fm + "\n" + pt_content, encoding="utf-8")
                    log.info(f"  🇧🇷 PT post created: pt/{filename}")
                except Exception as pt_exc:
                    log.debug(f"  DeepL PT post creation failed: {pt_exc}")

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
    Processes a single article dict (from HackerNews / DEV.to / Reddit) through
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
        if _title_similarity(title, existing_title) > 0.6:
            log.info(f"  ⏭  Título similar a '{existing_file}': {title[:60]}")
            return 0

    ai = _ai_enhance_post(title, description, og.get("body", ""), category, source)
    if ai.get("seo_title") and 10 < len(ai["seo_title"]) <= 70:
        title = ai["seo_title"]
    if ai.get("meta_description") and len(ai["meta_description"]) > 50:
        description = ai["meta_description"][:160]
    if ai.get("keywords"):
        all_tags = list(dict.fromkeys(all_tags + [k.lower().replace(" ", "-") for k in ai["keywords"]]))

    if not image_url:
        image_url = _generate_og_image(title, category, slug)

    sentiment  = _sentiment_score(f"{title} {description}")
    fact_check = _fact_check_score(title, description)

    deepl_key = os.getenv("DEEPL_API_KEY", "")
    description_ptbr = ""
    if deepl_key:
        description_ptbr = _translate_to_ptbr(description[:500], deepl_key) or ""

    cohere_key = os.getenv("COHERE_API_KEY", "")
    if cohere_key:
        emb = _get_cohere_embedding(f"{title} {description}", cohere_key)
        if emb:
            embeddings = _load_embeddings()
            embeddings[title] = emb
            _save_embeddings(embeddings)

    crypto_prices_for_post: dict | None = None
    if category == "business":
        combined_text = (title + " " + description).lower()
        if any(kw in combined_text for kw in _CRYPTO_KEYWORDS):
            crypto_prices_for_post = _get_crypto_prices() or None

    continuation = _find_related_story(title, all_tags, category)
    last_updated_val = pub_date.strftime("%Y-%m-%d") if continuation else ""

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

    post_path = POSTS_DIR / filename
    post_path.write_text(frontmatter + "\n" + post_content, encoding="utf-8")

    if deepl_key and description_ptbr:
        try:
            pt_dir = POSTS_DIR / "pt"
            pt_dir.mkdir(parents=True, exist_ok=True)
            pt_title = _translate_to_ptbr(title, deepl_key) or title
            pt_fm = build_frontmatter(
                title             = pt_title,
                date              = pub_date,
                categories        = categories,
                tags              = all_tags,
                author            = "GlobalBR News",
                description       = description_ptbr[:160],
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
            )
            pt_fm = pt_fm.replace('lang: "en"', 'lang: "pt-BR"')
            pt_content = build_content(
                title       = pt_title,
                description = description_ptbr,
                source_url  = link,
                source_name = source,
                date        = pub_date,
                categories  = categories,
                tags        = all_tags,
                body        = og.get("body", ""),
                ai_body     = ai.get("article_body", ""),
            )
            (pt_dir / filename).write_text(pt_fm + "\n" + pt_content, encoding="utf-8")
            log.info(f"  🇧🇷 PT post created: pt/{filename}")
        except Exception as pt_exc:
            log.debug(f"  DeepL PT post creation failed: {pt_exc}")

    log.info(f"  ✅ Post criado [{source}]: {filename}")
    _load_known_urls().add(link)
    _load_known_titles().insert(0, (title, filename))
    if not hasattr(fetch_feed, "_source_counts"):
        fetch_feed._source_counts = {}
    fetch_feed._source_counts[source] = fetch_feed._source_counts.get(source, 0) + 1
    return 1


def main():
    log.info("=" * 60)
    log.info(f"🚀 GlobalBR News — Fetch iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

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

    for i, feed in enumerate(FEEDS):
        if total_created >= MAX_POSTS_PER_RUN:
            log.info(f"  🏁 Limite global atingido ({MAX_POSTS_PER_RUN} posts/hora). Parando.")
            break
        remaining = MAX_POSTS_PER_RUN - total_created

        # Trending boost: fetch one extra article from feeds matching a trending keyword
        feed_words = set((feed["name"] + " " + feed.get("category", "")).lower().split())
        if trending and feed_words & trending:
            log.info(f"🔥 Trending boost: {feed['name']}")
            max_override = min(remaining, MAX_PER_FEED + 1)
        else:
            max_override = remaining

        created = fetch_feed(feed, max_override=max_override)
        total_created += created
        if i < len(FEEDS) - 1 and total_created < MAX_POSTS_PER_RUN:
            log.info(f"  ⏳ Aguardando {SLEEP_BETWEEN_FEEDS}s antes do próximo feed...")
            sleep(SLEEP_BETWEEN_FEEDS)

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

    # ── Reddit extra source (only if credentials available) ───────
    if total_created < MAX_POSTS_PER_RUN and os.getenv("REDDIT_CLIENT_ID"):
        log.info("📡 Fetching Reddit top posts...")
        try:
            reddit_items = fetch_reddit(max_per_sub=5)
            for item in reddit_items:
                if total_created >= MAX_POSTS_PER_RUN:
                    break
                total_created += _process_article_dict(item)
                sleep(1)
        except Exception as exc:
            log.warning(f"Reddit processing failed: {exc}")

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

    log.info("=" * 60)
    log.info(f"✨ Concluído! Total de posts criados: {total_created}/{MAX_POSTS_PER_RUN}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
