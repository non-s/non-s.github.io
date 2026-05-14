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
import logging
import hashlib
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

# HTTP session reutilizável (melhor performance)
_session = requests.Session()
_session.headers.update({"User-Agent": "TechBR-News-Bot/2.0 (+https://non-s.github.io)"})

# ============================================================
# CONFIGURAÇÕES
# ============================================================

POSTS_DIR        = Path("_posts")
LOG_FILE         = "fetch_news.log"
MAX_PER_FEED     = 2                   # Max posts por feed por execução
MAX_POSTS_PER_RUN = 5                 # Limite global por execução (cadência horária controlada)
REQUEST_TIMEOUT  = 15
SLEEP_BETWEEN_FEEDS = 2
MIN_DESCRIPTION_LEN = 80              # Descrição mínima para publicar

# Feeds RSS configurados
FEEDS = [
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
    # ── Developer / General ───────────────────────────────────
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
]


# ============================================================
# KEYWORD → CATEGORY / TAG MAPPING
# ============================================================

KEYWORD_CATEGORIES: dict[str, tuple[str, list]] = {
    # AI / Machine Learning
    "artificial intelligence": ("ai",        ["ai", "machine-learning"]),
    "machine learning":        ("ai",        ["ai", "machine-learning"]),
    "deep learning":           ("ai",        ["ai", "deep-learning"]),
    "neural network":          ("ai",        ["ai", "neural-networks"]),
    "large language model":    ("ai",        ["ai", "llm"]),
    " llm ":                   ("ai",        ["ai", "llm"]),
    "chatgpt":                 ("ai",        ["ai", "chatgpt", "openai"]),
    "openai":                  ("ai",        ["ai", "openai"]),
    "anthropic":               ("ai",        ["ai", "anthropic"]),
    "gemini":                  ("ai",        ["ai", "google", "gemini"]),
    "copilot":                 ("ai",        ["ai", "microsoft", "copilot"]),
    "generative ai":           ("ai",        ["ai", "generative-ai"]),
    "claude":                  ("ai",        ["ai", "anthropic", "claude"]),
    "grok":                    ("ai",        ["ai", "xai", "grok"]),
    "mistral":                 ("ai",        ["ai", "mistral"]),

    # Security
    "cybersecurity":           ("security",  ["security", "cybersecurity"]),
    "ransomware":              ("security",  ["security", "ransomware"]),
    "malware":                 ("security",  ["security", "malware"]),
    "data breach":             ("security",  ["security", "data-breach"]),
    "vulnerability":           ("security",  ["security", "vulnerability"]),
    "hacker":                  ("security",  ["security", "hacking"]),
    "zero-day":                ("security",  ["security", "zero-day"]),
    "phishing":                ("security",  ["security", "phishing"]),
    "exploit":                 ("security",  ["security", "exploit"]),
    "spyware":                 ("security",  ["security", "spyware"]),

    # Mobile
    "iphone":                  ("mobile",    ["mobile", "apple", "iphone"]),
    "android":                 ("mobile",    ["mobile", "android"]),
    "smartphone":              ("mobile",    ["mobile", "smartphone"]),
    "samsung galaxy":          ("mobile",    ["mobile", "samsung"]),
    "pixel phone":             ("mobile",    ["mobile", "google", "pixel"]),
    "ios 18":                  ("mobile",    ["mobile", "apple", "ios"]),
    "android 15":              ("mobile",    ["mobile", "android", "google"]),

    # Gadgets
    "smartwatch":              ("gadgets",   ["gadgets", "wearables"]),
    "headphones":              ("gadgets",   ["gadgets", "audio"]),
    "laptop":                  ("gadgets",   ["gadgets", "laptop"]),
    "graphics card":           ("gadgets",   ["gadgets", "gpu"]),
    "electric vehicle":        ("gadgets",   ["gadgets", "ev", "electric-vehicle"]),
    "gpu":                     ("gadgets",   ["gadgets", "gpu", "nvidia"]),
    "processor":               ("gadgets",   ["gadgets", "processor", "chip"]),

    # Startups
    "startup":                 ("startups",  ["startups"]),
    "venture capital":         ("startups",  ["startups", "venture-capital"]),
    "series a":                ("startups",  ["startups", "funding"]),
    "series b":                ("startups",  ["startups", "funding"]),
    "series c":                ("startups",  ["startups", "funding"]),
    "ipo":                     ("startups",  ["startups", "ipo"]),
    "unicorn":                 ("startups",  ["startups", "unicorn"]),
    "funding round":           ("startups",  ["startups", "funding"]),
    "raised":                  ("startups",  ["startups", "funding"]),
    "acquisition":             ("startups",  ["startups", "acquisition"]),
}

# ============================================================
# FILTRO DE QUALIDADE — BLACKLIST
# Termos que indicam conteúdo irrelevante para um blog de tecnologia
# ============================================================

BLACKLIST_PHRASES = [
    # Entretenimento/lifestyle sem relação com tech
    "crossword", "crossword answers", "wordle", "mini crossword",
    "horoscope", "zodiac", "astrology",
    "recipe", "cooking", "restaurant",
    "discount code", "coupon", "promo code", "deals up to",
    "best deals", "sale ends", "limited time offer",
    "sex toy", "vibrator", "we-vibe", "adult toy",
    "deepfake porn", "deepfake nude", "nonconsensual",
    "celebrity gossip", "celebrity news",
    "reality tv", "reality show",
    "sports score", "game score", "nfl", "nba", "mlb", "nhl",
    # Artigos de baixa qualidade
    "sponsored", "advertisement", "buy now",
    "click here to win", "giveaway",
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
    r"\brecipe\b",
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


def fetch_og_metadata(url: str, timeout: int = 8) -> dict:
    """
    Faz uma requisição parcial à URL do artigo e extrai metadados OG.
    Retorna dict com 'description' e 'image' se encontrados.
    Usa stream=True e lê apenas os primeiros 32 KB para eficiência.
    """
    result = {"description": "", "image": ""}
    try:
        resp = _session.get(url, timeout=timeout, stream=True,
                            headers={"Accept": "text/html"})
        resp.raise_for_status()
        # Lê apenas os primeiros 32 KB (suficiente para a <head>)
        chunk = b""
        for data in resp.iter_content(chunk_size=8192):
            chunk += data
            if len(chunk) >= 32768:
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


def build_frontmatter(
    title:       str,
    date:        datetime,
    categories:  list,
    tags:        list,
    author:      str,
    description: str,
    source_url:  str,
    source_name: str,
    image:       str,
) -> str:
    """Monta o frontmatter YAML do post Jekyll."""
    date_str  = date.strftime("%Y-%m-%d %H:%M:%S %z").strip()
    cats_yaml = "[" + ", ".join(categories) + "]"
    tags_yaml = "[" + ", ".join(t for t in tags if t) + "]"

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
"""
    if image:
        front += f'image: "{image}"\n'
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
) -> str:
    """Monta o conteúdo Markdown do post com estrutura rica."""
    date_str = date.strftime("%B %d, %Y")
    time_str = date.strftime("%H:%M UTC")
    category_label = categories[0].upper() if categories else "TECH"

    # Divide descrição em até 2 parágrafos para melhor leitura
    sentences = re.split(r'(?<=[.!?])\s+', description.strip())
    if len(sentences) > 3:
        para1 = " ".join(sentences[:3])
        para2 = " ".join(sentences[3:])
    else:
        para1 = description.strip()
        para2 = ""

    # Tags relevantes para "Read more" section
    related_tags = [f"`{t}`" for t in tags[:5] if len(t) > 2]
    tags_line = "  ".join(related_tags) if related_tags else ""

    content = f"""{para1}

<!--more-->
"""

    if para2:
        content += f"""
{para2}
"""

    content += f"""
## What You Need to Know

- **Source:** {source_name}
- **Published:** {date_str} at {time_str}
- **Category:** {category_label}
- **Read time:** ~2 min

## Full Story

This is a curated summary. For complete coverage, in-depth analysis, and all supporting details, read the original article:

> **[Read the full story on {source_name} →]({source_url})**

*Original reporting and all rights belong to the respective author(s) at **{source_name}**.*

---
"""

    if tags_line:
        content += f"""
**Related topics:** {tags_line}

"""

    content += f"*Curated by [TechBR News](https://non-s.github.io) · {date_str}*\n"

    return content


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
            "User-Agent": "TechBR-News-Bot/1.0 (+https://non-s.github.io)"
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

            # Filtro de imagem obrigatória
            if not image_url:
                log.info(f"  ⏭  Sem imagem: {title[:60]}")
                continue

            # Filtro de descrição mínima
            if len(description) < MIN_DESCRIPTION_LEN:
                log.info(f"  ⏭  Descrição muito curta ({len(description)} chars): {title[:60]}")
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

            # Re-verificar imagem após OG
            if not image_url:
                log.info(f"  ⏭  Sem imagem mesmo após OG: {title[:60]}")
                continue

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

            frontmatter = build_frontmatter(
                title       = title,
                date        = pub_date,
                categories  = categories,
                tags        = all_tags,
                author      = "TechBR News",
                description = description,
                source_url  = link,
                source_name = source,
                image       = image_url,
            )
            post_content = build_content(
                title       = title,
                description = description,
                source_url  = link,
                source_name = source,
                date        = pub_date,
                categories  = categories,
                tags        = all_tags,
            )

            post_path = POSTS_DIR / filename
            post_path.write_text(frontmatter + "\n" + post_content, encoding="utf-8")

            log.info(f"  ✅ Post criado: {filename}")
            _load_known_urls().add(link)
            created_count += 1

        except Exception as e:
            log.error(f"  ❌ Erro ao processar item '{getattr(entry, 'title', '?')}': {e}")
            continue

    log.info(f"  📝 {created_count} posts criados para {name}")
    return created_count


def main():
    log.info("=" * 60)
    log.info(f"🚀 TechBR News — Fetch iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    POSTS_DIR.mkdir(exist_ok=True)

    total_created = 0

    for i, feed in enumerate(FEEDS):
        if total_created >= MAX_POSTS_PER_RUN:
            log.info(f"  🏁 Limite global atingido ({MAX_POSTS_PER_RUN} posts/hora). Parando.")
            break
        remaining = MAX_POSTS_PER_RUN - total_created
        created = fetch_feed(feed, max_override=remaining)
        total_created += created
        if i < len(FEEDS) - 1 and total_created < MAX_POSTS_PER_RUN:
            log.info(f"  ⏳ Aguardando {SLEEP_BETWEEN_FEEDS}s antes do próximo feed...")
            sleep(SLEEP_BETWEEN_FEEDS)

    log.info("=" * 60)
    log.info(f"✨ Concluído! Total de posts criados: {total_created}/{MAX_POSTS_PER_RUN}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
