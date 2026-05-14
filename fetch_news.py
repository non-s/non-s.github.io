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
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

# HTTP session reutilizável (melhor performance)
_session = requests.Session()
_session.headers.update({"User-Agent": "GlobalBR-News-Bot/3.0 (+https://non-s.github.io)"})

# ============================================================
# AI TEXT — Groq (primário, rápido) + Pollinations (fallback gratuito)
# ============================================================

GROQ_API_URL          = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL            = "llama-3.3-70b-versatile"
POLLINATIONS_TEXT_URL = "https://text.pollinations.ai/"

def _ai_text(prompt: str, system: str = "", seed: int = 0, timeout: int = 22) -> str:
    """
    Gera texto via Groq (Llama 3.3 70B — rápido, gratuito com chave).
    Fallback automático para Pollinations.ai se Groq não estiver configurado ou falhar.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system or "You are a professional journalist and SEO expert. Be concise and accurate."},
                    {"role": "user",   "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1500,
            }
            r = _session.post(GROQ_API_URL, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            log.warning(f"Groq API error (falling back to Pollinations): {exc}")

    # Fallback: Pollinations.ai — sem chave, gratuito
    try:
        payload = {
            "messages": [
                {"role": "system", "content": system or "You are a professional journalist and SEO expert. Be concise and accurate."},
                {"role": "user",   "content": prompt},
            ],
            "model":   "openai",
            "seed":    seed or abs(hash(prompt)) % 9999,
            "private": True,
        }
        r = _session.post(POLLINATIONS_TEXT_URL, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "choices" in data:
            return data["choices"][0]["message"]["content"].strip()
        return str(data).strip()
    except Exception as exc:
        log.warning(f"Pollinations fallback error: {exc}")
        return ""

# Alias para compatibilidade interna
_pollinations_text = _ai_text

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


def _ai_enhance_post(title: str, description: str, body: str, category: str, source_name: str) -> dict:
    """
    Usa Pollinations AI para gerar conteúdo SEO-otimizado por artigo.
    Retorna dict com: seo_title, meta_description, article_body, faq, keywords.
    Retorna {} em caso de falha — o caller usa template como fallback.
    """
    combined = f"{description}\n\n{body}".strip()[:2000]
    cat = category.capitalize()
    prompt = (
        f'You are a world-class SEO journalist. Enhance this news article. '
        f'Respond ONLY with valid JSON, no markdown, no code blocks, no extra text.\n\n'
        f'Title: {title}\nCategory: {cat}\nSource: {source_name}\nContent:\n{combined}\n\n'
        f'Required JSON:\n'
        f'{{"seo_title":"<65 chars with main keyword>","meta_description":"<150-155 chars ending with period>",'
        f'"article_body":"3 journalistic paragraphs 300-400 words total. Add ## H2 heading before each paragraph. No bullet points.",'
        f'"faq":[{{"q":"specific question about this news?","a":"clear 1-2 sentence answer."}},'
        f'{{"q":"second relevant question?","a":"clear 1-2 sentence answer."}}],'
        f'"keywords":["primary keyword","secondary keyword","long tail phrase","topic","subtopic"]}}'
    )
    raw = _pollinations_text(prompt, seed=abs(hash(title)) % 9999, timeout=22)
    if not raw:
        return {}
    try:
        clean = re.sub(r'```(?:json)?\s*|\s*```', '', raw).strip()
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        log.warning(f"AI enhance parse error: {e} | raw[:120]={raw[:120]}")
    return {}

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
]


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
    keywords:    list | None = None,
    faq:         list | None = None,
    sentiment:   str  = "neutral",
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
sentiment: "{sentiment}"
"""
    if image:
        front += f'image: "{image}"\n'
    if keywords:
        kw_yaml = "[" + ", ".join(f'"{k}"' for k in keywords[:8] if k and len(k) > 1) + "]"
        front += f"keywords: {kw_yaml}\n"
    if faq:
        front += "faq:\n"
        for item in faq[:3]:
            q = sanitize_text(str(item.get("q", ""))).replace('"', "'")
            a = sanitize_text(str(item.get("a", ""))).replace('"', "'")
            if q and a:
                front += f'  - q: "{q}"\n    a: "{a}"\n'
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
    """Generates a Portuguese (PT-BR) summary section using AI."""
    try:
        prompt = (
            f"Translate and summarize the following news article into Brazilian Portuguese (PT-BR). "
            f"Write only a 2-3 sentence plain text summary — no JSON, no bullet points, no headings.\n\n"
            f"Title: {title}\nDescription: {description}"
        )
        pt_text = _ai_text(prompt, system="Você é um jornalista profissional. Responda apenas em português do Brasil.")
        if not pt_text:
            return ""
        lines = [l.strip() for l in pt_text.strip().splitlines() if l.strip()]
        pt_title = lines[0] if lines else title
        pt_summary = " ".join(lines[1:]) if len(lines) > 1 else lines[0] if lines else ""
        if not pt_summary:
            pt_summary = pt_title
            pt_title = title
        return f"\n\n---\n\n## 🇧🇷 Resumo em Português\n\n**{pt_title}**\n\n{pt_summary}\n"
    except Exception:
        return ""


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

            # ── AI Enhancement (Pollinations — gratuito) ─────────
            ai = _ai_enhance_post(title, description, og.get("body", ""), category, source)
            if ai.get("seo_title") and 10 < len(ai["seo_title"]) <= 70:
                log.info(f"  🤖 AI title: {ai['seo_title'][:60]}")
                title = ai["seo_title"]
            if ai.get("meta_description") and len(ai["meta_description"]) > 50:
                description = ai["meta_description"][:160]
            if ai.get("keywords"):
                all_tags = list(dict.fromkeys(all_tags + [k.lower().replace(" ", "-") for k in ai["keywords"]]))

            # ── Imagem: OG > AI gerada > fallback ────────────────
            if not image_url:
                image_url = _news_image_url(title, category)
                log.info(f"  🎨 AI image: {title[:50]}")

            sentiment   = _sentiment_score(f"{title} {description}")

            frontmatter = build_frontmatter(
                title       = title,
                date        = pub_date,
                categories  = categories,
                tags        = all_tags,
                author      = "GlobalBR News",
                description = description,
                source_url  = link,
                source_name = source,
                image       = image_url,
                keywords    = ai.get("keywords", []),
                faq         = ai.get("faq", []),
                sentiment   = sentiment,
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

            post_content = _add_internal_links(post_content, category, Path(filename).stem)
            pt_section = _add_pt_summary(title, description, category)
            post_content += pt_section

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
    log.info(f"🚀 GlobalBR News — Fetch iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    POSTS_DIR.mkdir(exist_ok=True)

    total_created = 0

    trending = _get_trending_keywords()
    if trending:
        log.info(f"🔥 Trending keywords loaded: {len(trending)} terms")

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

    log.info("=" * 60)
    log.info(f"✨ Concluído! Total de posts criados: {total_created}/{MAX_POSTS_PER_RUN}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
