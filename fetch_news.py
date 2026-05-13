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
     - Gera slug único
     - Verifica duplicatas (arquivo já existe?)
     - Cria arquivo .md em _posts/ com frontmatter Jekyll
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

# ============================================================
# CONFIGURAÇÕES
# ============================================================

POSTS_DIR   = Path("_posts")          # Diretório de posts Jekyll
LOG_FILE    = "fetch_news.log"        # Arquivo de log
MAX_PER_FEED = 5                      # Máximo de posts por feed por execução
REQUEST_TIMEOUT = 15                  # Timeout em segundos para requests HTTP
SLEEP_BETWEEN_FEEDS = 2               # Pausa entre feeds (evitar bloqueio)

# Feeds RSS configurados
FEEDS = [
    {
        "name":     "G1 Tecnologia",
        "url":      "https://g1.globo.com/rss/g1/tecnologia/",
        "category": "tecnologia",
        "tags":     ["g1", "globo", "tecnologia"],
        "source":   "G1 — O Portal de Notícias da Globo",
    },
    {
        "name":     "TecMundo",
        "url":      "https://rss.tecmundo.com.br/feed",
        "category": "tecnologia",
        "tags":     ["tecmundo", "tecnologia", "gadgets"],
        "source":   "TecMundo",
    },
    {
        "name":     "TechTudo",
        "url":      "https://www.techtudo.com.br/rss/all.xml",
        "category": "gadgets",
        "tags":     ["techtudo", "gadgets", "reviews"],
        "source":   "TechTudo",
    },
    {
        "name":     "Olhar Digital",
        "url":      "https://olhardigital.com.br/feed/",
        "category": "tecnologia",
        "tags":     ["olhardigital", "tecnologia", "inovacao"],
        "source":   "Olhar Digital",
    },
]

# Mapeamento de palavras-chave para categorias/tags extras
KEYWORD_CATEGORIES = {
    "inteligência artificial": ("ia", ["ia", "inteligencia-artificial"]),
    "machine learning":        ("ia", ["ia", "machine-learning"]),
    "chatgpt":                 ("ia", ["ia", "chatgpt", "openai"]),
    "gemini":                  ("ia", ["ia", "google", "gemini"]),
    "smartphone":              ("mobile", ["mobile", "smartphone"]),
    "iphone":                  ("mobile", ["mobile", "iphone", "apple"]),
    "android":                 ("mobile", ["mobile", "android"]),
    "startup":                 ("startups", ["startups", "empreendedorismo"]),
    "cibersegurança":          ("segurança", ["seguranca", "privacidade"]),
    "ciberataque":             ("segurança", ["seguranca", "ciberataque"]),
    "bitcoin":                 ("criptomoedas", ["bitcoin", "criptomoedas"]),
    "crypto":                  ("criptomoedas", ["cripto", "blockchain"]),
}

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
    # Normaliza acentos → ASCII
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Remove caracteres inválidos
    text = re.sub(r"[^\w\s-]", "", text)
    # Substitui espaços e underscores por hifens
    text = re.sub(r"[\s_]+", "-", text)
    # Remove hifens múltiplos
    text = re.sub(r"-{2,}", "-", text)
    return text[:80].strip("-")


def sanitize_text(text: str) -> str:
    """Remove caracteres problemáticos para YAML/Markdown."""
    if not text:
        return ""
    # Remove aspas duplas (problemas no frontmatter YAML)
    text = text.replace('"', "'").replace("\n", " ").replace("\r", " ")
    # Remove caracteres de controle
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def extract_description(entry) -> str:
    """Extrai descrição/resumo do item RSS."""
    desc = ""
    if hasattr(entry, "summary"):
        desc = entry.summary
    elif hasattr(entry, "description"):
        desc = entry.description
    # Remove tags HTML
    desc = re.sub(r"<[^>]+>", "", desc)
    desc = re.sub(r"&[a-z]+;", " ", desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    return sanitize_text(desc[:500])


def extract_image(entry) -> str:
    """Tenta extrair URL de imagem do item RSS."""
    # 1. Media content
    if hasattr(entry, "media_content"):
        for m in entry.media_content:
            if m.get("type", "").startswith("image"):
                return m.get("url", "")
    # 2. Media thumbnail
    if hasattr(entry, "media_thumbnail"):
        for t in entry.media_thumbnail:
            url = t.get("url", "")
            if url:
                return url
    # 3. Enclosures
    if hasattr(entry, "enclosures"):
        for e in entry.enclosures:
            if e.get("type", "").startswith("image"):
                return e.get("href", "")
    # 4. Procura img src no conteúdo HTML
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


def post_exists(filename: str) -> bool:
    """Verifica se o post já existe (evita duplicatas)."""
    return (POSTS_DIR / filename).exists()


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
    cats_yaml = "[" + ", ".join(cats for cats in categories) + "]"
    tags_yaml = "[" + ", ".join(t for t in tags if t) + "]"

    front = f"""---
layout: post
title: "{sanitize_text(title)}"
date: {date_str if date_str else date.strftime("%Y-%m-%d %H:%M:%S")} -0300
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
) -> str:
    """Monta o conteúdo Markdown do post."""
    date_br = date.strftime("%d/%m/%Y às %H:%M")
    content = f"""{description}

<!--more-->

## Sobre esta notícia

Esta publicação é um resumo automático de curadoria baseado no feed RSS de **{source_name}**.

> 📰 **Leia o artigo completo** em [{source_name}]({source_url})

O conteúdo original foi publicado em {date_br}. Todos os direitos pertencem ao(s) respectivo(s) autor(es) e ao veículo **{source_name}**.

---

*Notícia coletada automaticamente pelo [TechBR News](https://non-s.github.io). [Veja a fonte original]({source_url}).*
"""
    return content


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def fetch_feed(feed_config: dict) -> int:
    """
    Processa um feed RSS e cria posts novos.
    Retorna o número de posts criados.
    """
    name     = feed_config["name"]
    url      = feed_config["url"]
    category = feed_config["category"]
    base_tags = feed_config["tags"]
    source   = feed_config["source"]

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

    for entry in entries[:MAX_PER_FEED]:
        try:
            # Extrai dados do item
            title       = sanitize_text(getattr(entry, "title", "Sem título"))
            link        = getattr(entry, "link", "")
            description = extract_description(entry)
            pub_date    = parse_date(entry)
            image_url   = extract_image(entry)

            if not title or not link:
                log.debug(f"  ⏭  Item sem título ou link, pulando.")
                continue

            # Detecta categoria e tags extras por palavra-chave
            extra_cat, extra_tags = get_extra_tags(title, description)
            categories = [category]
            if extra_cat and extra_cat not in categories:
                categories.append(extra_cat)

            all_tags = list(dict.fromkeys(base_tags + extra_tags))  # dedup preservando ordem

            # Gera slug e nome do arquivo
            slug     = slugify(title)
            filename = post_filename(pub_date, slug)

            # Verifica duplicata
            if post_exists(filename):
                log.debug(f"  ⏭  Post já existe: {filename}")
                continue

            # Monta o post
            frontmatter = build_frontmatter(
                title       = title,
                date        = pub_date,
                categories  = categories,
                tags        = all_tags,
                author      = "TechBR News Bot",
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
            )

            # Escreve o arquivo
            post_path = POSTS_DIR / filename
            post_path.write_text(frontmatter + "\n" + post_content, encoding="utf-8")

            log.info(f"  ✅ Post criado: {filename}")
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

    # Garante que o diretório _posts existe
    POSTS_DIR.mkdir(exist_ok=True)

    total_created = 0

    for i, feed in enumerate(FEEDS):
        created = fetch_feed(feed)
        total_created += created
        if i < len(FEEDS) - 1:
            log.info(f"  ⏳ Aguardando {SLEEP_BETWEEN_FEEDS}s antes do próximo feed...")
            sleep(SLEEP_BETWEEN_FEEDS)

    log.info("=" * 60)
    log.info(f"✨ Concluído! Total de posts criados: {total_created}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
