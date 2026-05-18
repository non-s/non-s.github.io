#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_news.py — Refresh the YouTube Shorts story queue.

Reads ~15 RSS feeds, dedups against the existing queue and the per-feed
ETag/Last-Modified cache, asks Mistral to score the story and write a
short-friendly hook + lead, then appends the result to
_data/stories_queue.json.

`generate_shorts.py` picks the highest-quality pending stories from
that queue on its next run. The two scripts share NO other state —
this is the only contract between them.

Usage:
    python fetch_news.py

Env (see .env.example for the full list):
    MISTRAL_API_KEY            (required)
    MISTRAL_MODEL              (default: mistral-small-latest)
    MISTRAL_MIN_INTERVAL       (default: 8 — seconds between calls)
    FETCH_MAX_PER_FEED         (default: 10)
    FETCH_MAX_PER_RUN          (default: 100)
    FETCH_FEED_WORKERS         (default: 10)
    FETCH_QUALITY_THRESHOLD    (default: 6 — 0-10 scale)
    FETCH_TIMEOUT_S            (default: 3300)
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

# fcntl is POSIX-only — Windows runners would skip queue locking. The
# GitHub Actions runner is Linux so this is fine in production; we
# guard the import for local dev on macOS / Windows.
try:
    import fcntl
except ImportError:  # pragma: no cover — Windows local dev only
    fcntl = None

from utils.ai_helper import (
    ai_text,
    is_breaking_news,
    quality_check,
    quality_score,
    sentiment_score,
)
from utils.dedup import titles_too_similar
from utils.prompt_safety import sanitize_for_prompt, wrap_untrusted
from utils.public_sources import (
    fetch_all_public_sources,
    fetch_google_trends,
    trending_keywords,
)
from utils.ranking import entry_relevance_score
from utils.text import (
    extract_description,
    extract_image,
    parse_date,
    sanitize_text,
    slugify,
)

# ── Config ────────────────────────────────────────────────────────────

DATA_DIR        = Path("_data")
QUEUE_FILE      = DATA_DIR / "stories_queue.json"
CACHE_FILE      = DATA_DIR / "feed_cache.json"
HEALTH_FILE     = DATA_DIR / "feed_health.json"
ANALYTICS_LATEST = DATA_DIR / "analytics" / "latest.json"
LOG_FILE        = "fetch_news.log"

MAX_PER_FEED      = int(os.environ.get("FETCH_MAX_PER_FEED", "10"))
MAX_PER_RUN       = int(os.environ.get("FETCH_MAX_PER_RUN",  "100"))
FEED_WORKERS      = int(os.environ.get("FETCH_FEED_WORKERS", "10"))
QUALITY_THRESHOLD = int(os.environ.get("FETCH_QUALITY_THRESHOLD", "6"))
RUN_TIMEOUT_S     = int(os.environ.get("FETCH_TIMEOUT_S",    "3300"))
DEAD_FEED_SKIP_AT = 5  # consecutive failures before we stop trying
INCLUDE_PUBLIC_SOURCES = os.environ.get("FETCH_INCLUDE_PUBLIC", "1") not in ("0", "false", "False")
INCLUDE_TRENDS         = os.environ.get("FETCH_INCLUDE_TRENDS", "1") not in ("0", "false", "False")
INCLUDE_PTBR_FEEDS     = os.environ.get("FETCH_INCLUDE_PTBR", "1") not in ("0", "false", "False")

# Relevance pre-filter — stories whose headline-only score falls below
# this threshold skip the AI enrichment step entirely. Saves up to ~50 %
# of Mistral / fallback calls per run by dropping low-signal items
# (clickbait, short headlines, no image, etc.) before we spend tokens.
# The score scale is ~0-10 from utils.ranking.entry_relevance_score.
RELEVANCE_MIN_FOR_AI = float(os.environ.get("FETCH_RELEVANCE_MIN_AI", "3.0"))

# Keep the queue bounded — older consumed stories get pruned.
QUEUE_MAX_LEN = 500

# ── RSS feed list (free, no-auth) ──────────────────────────────────
#
# Reuters' historic feeds.reuters.com endpoints were retired years ago —
# they're omitted here intentionally. SCMP / Times of India / Deutsche
# Welle give us non-Anglosphere coverage on the same free terms.
#
# Adding a feed: keep the categories aligned with the playlist map in
# upload_youtube.py (`world`, `technology`, `politics`, `business`,
# `science`, `health`, `environment`, `ai`, `sports`, `entertainment`,
# `security`). Misaligned categories still publish but won't auto-join
# a category playlist.
FEEDS: list[dict] = [
    # World / general
    {"name": "BBC World",         "url": "https://feeds.bbci.co.uk/news/world/rss.xml",                              "category": "world",       "source": "BBC"},
    {"name": "Guardian World",    "url": "https://www.theguardian.com/world/rss",                                    "category": "world",       "source": "The Guardian"},
    {"name": "Al Jazeera",        "url": "https://www.aljazeera.com/xml/rss/all.xml",                                "category": "world",       "source": "Al Jazeera"},
    {"name": "NPR News",          "url": "https://feeds.npr.org/1001/rss.xml",                                       "category": "world",       "source": "NPR"},
    {"name": "Deutsche Welle",    "url": "https://rss.dw.com/atom/rss-en-all",                                       "category": "world",       "source": "Deutsche Welle"},
    {"name": "France 24",         "url": "https://www.france24.com/en/rss",                                          "category": "world",       "source": "France 24"},
    {"name": "Euronews",          "url": "https://feeds.feedburner.com/euronews/en/news",                            "category": "world",       "source": "Euronews"},
    {"name": "Times of India",    "url": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",               "category": "world",       "source": "Times of India"},
    {"name": "SCMP World",        "url": "https://www.scmp.com/rss/91/feed",                                         "category": "world",       "source": "South China Morning Post"},

    # Politics
    {"name": "Guardian Politics", "url": "https://www.theguardian.com/politics/rss",                                 "category": "politics",    "source": "The Guardian"},
    {"name": "Foreign Policy",    "url": "https://foreignpolicy.com/feed/",                                          "category": "politics",    "source": "Foreign Policy"},

    # Tech / AI
    {"name": "TechCrunch",        "url": "https://techcrunch.com/feed/",                                              "category": "technology",  "source": "TechCrunch"},
    {"name": "The Verge",         "url": "https://www.theverge.com/rss/index.xml",                                    "category": "technology",  "source": "The Verge"},
    {"name": "Wired",             "url": "https://www.wired.com/feed/rss",                                            "category": "technology",  "source": "Wired"},
    {"name": "Ars Technica",      "url": "https://feeds.arstechnica.com/arstechnica/index",                           "category": "technology",  "source": "Ars Technica"},
    {"name": "Engadget",          "url": "https://www.engadget.com/rss.xml",                                          "category": "technology",  "source": "Engadget"},
    {"name": "CNET",              "url": "https://www.cnet.com/rss/news/",                                            "category": "technology",  "source": "CNET"},
    {"name": "MIT Tech Review",   "url": "https://www.technologyreview.com/feed/",                                    "category": "technology",  "source": "MIT Tech Review"},
    {"name": "The Register",      "url": "https://www.theregister.com/headlines.atom",                                "category": "technology",  "source": "The Register"},
    {"name": "TechCrunch AI",     "url": "https://techcrunch.com/category/artificial-intelligence/feed/",             "category": "ai",          "source": "TechCrunch"},
    {"name": "VentureBeat AI",    "url": "https://venturebeat.com/category/ai/feed/",                                 "category": "ai",          "source": "VentureBeat"},

    # Business / economy
    {"name": "CNBC",              "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",                     "category": "business",    "source": "CNBC"},
    {"name": "Guardian Business", "url": "https://www.theguardian.com/business/rss",                                 "category": "business",    "source": "The Guardian"},
    {"name": "MarketWatch",       "url": "https://feeds.marketwatch.com/marketwatch/topstories/",                    "category": "business",    "source": "MarketWatch"},
    {"name": "Fortune",           "url": "https://fortune.com/feed/",                                                 "category": "business",    "source": "Fortune"},

    # Science / health / environment
    {"name": "BBC Science",       "url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",              "category": "science",     "source": "BBC"},
    {"name": "ScienceAlert",      "url": "https://www.sciencealert.com/feed",                                         "category": "science",     "source": "ScienceAlert"},
    {"name": "Phys.org",          "url": "https://phys.org/rss-feed/",                                                "category": "science",     "source": "Phys.org"},
    {"name": "NASA News",         "url": "https://www.nasa.gov/feed/",                                                "category": "science",     "source": "NASA"},
    {"name": "BBC Health",        "url": "http://feeds.bbci.co.uk/news/health/rss.xml",                               "category": "health",      "source": "BBC"},
    {"name": "WHO News",          "url": "https://www.who.int/feeds/entity/news/en/rss.xml",                          "category": "health",      "source": "WHO"},
    {"name": "Guardian Environ.", "url": "https://www.theguardian.com/environment/rss",                              "category": "environment", "source": "The Guardian"},
    {"name": "Inside Climate",    "url": "https://insideclimatenews.org/feed/",                                       "category": "environment", "source": "Inside Climate News"},
    {"name": "Carbon Brief",      "url": "https://www.carbonbrief.org/feed",                                          "category": "environment", "source": "Carbon Brief"},

    # Sports / entertainment
    {"name": "Sky Sports",        "url": "https://www.skysports.com/rss/12040",                                       "category": "sports",      "source": "Sky Sports"},
    {"name": "BBC Sport",         "url": "https://feeds.bbci.co.uk/sport/rss.xml",                                    "category": "sports",      "source": "BBC Sport"},
    {"name": "Variety",           "url": "https://variety.com/feed/",                                                 "category": "entertainment","source": "Variety"},
    {"name": "Hollywood Reporter","url": "https://www.hollywoodreporter.com/feed/",                                   "category": "entertainment","source": "Hollywood Reporter"},
    {"name": "Rolling Stone",     "url": "https://www.rollingstone.com/feed/",                                        "category": "entertainment","source": "Rolling Stone"},

    # Security / defense
    {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/",                                          "category": "security",    "source": "Krebs on Security"},
    {"name": "The Hacker News",   "url": "https://feeds.feedburner.com/TheHackersNews",                               "category": "security",    "source": "The Hacker News"},
    {"name": "Defense News",      "url": "https://www.defensenews.com/arc/outboundfeeds/rss/",                        "category": "world",       "source": "Defense News"},
    {"name": "War on the Rocks",  "url": "https://warontherocks.com/feed/",                                           "category": "world",       "source": "War on the Rocks"},
]

# ── PT-BR native sources (no translation) ──────────────────────────
#
# Brazilian-language feeds for the PT-BR sibling channel. When the
# pipeline runs with LANGUAGE=pt-BR (see generate_shorts.py), the
# translation step is skipped for stories tagged native_lang=pt-BR
# — they're already in Portuguese, so we ship them as-is. Massive
# quality win vs translating English wire copy.
#
# Each story still goes through the SAME AI enrichment (hook, script,
# thumbnail_text), only the prompt is in Portuguese. ai_helper.py's
# system message is language-agnostic.
PTBR_FEEDS: list[dict] = [
    {"name": "G1",                "url": "https://g1.globo.com/rss/g1/",                                           "category": "world",        "source": "G1"},
    {"name": "UOL Notícias",      "url": "https://rss.uol.com.br/feed/noticias.xml",                               "category": "world",        "source": "UOL"},
    {"name": "Folha de S.Paulo",  "url": "https://feeds.folha.uol.com.br/poder/rss091.xml",                        "category": "politics",     "source": "Folha de S.Paulo"},
    {"name": "BBC News Brasil",   "url": "https://www.bbc.com/portuguese/index.xml",                                "category": "world",        "source": "BBC News Brasil"},
    {"name": "DW Brasil",         "url": "https://rss.dw.com/atom/rss-br-all",                                     "category": "world",        "source": "DW Brasil"},
    {"name": "Estadão",           "url": "https://www.estadao.com.br/rss/ultimas.xml",                             "category": "world",        "source": "Estadão"},
    {"name": "Olhar Digital",     "url": "https://olhardigital.com.br/feed/",                                       "category": "technology",   "source": "Olhar Digital"},
    {"name": "Tecmundo",          "url": "https://www.tecmundo.com.br/rss",                                         "category": "technology",   "source": "Tecmundo"},
    {"name": "Canaltech",         "url": "https://canaltech.com.br/rss/",                                           "category": "technology",   "source": "Canaltech"},
    {"name": "InfoMoney",         "url": "https://www.infomoney.com.br/feed/",                                      "category": "business",     "source": "InfoMoney"},
    {"name": "Valor Econômico",   "url": "https://valor.globo.com/rss/valor-economico/",                            "category": "business",     "source": "Valor Econômico"},
    {"name": "CartaCapital",      "url": "https://www.cartacapital.com.br/feed/",                                   "category": "politics",     "source": "CartaCapital"},
    {"name": "GE Globo",          "url": "https://ge.globo.com/rss/ultimas/feed.xml",                               "category": "sports",       "source": "GE Globo"},
]


# ── Logging ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("fetch_news")


# ── HTTP session ──────────────────────────────────────────────────────

_session = requests.Session()
_session.headers.update({
    "User-Agent": "GlobalBR-News-Bot/4.0 (+https://github.com/non-s/non-s.github.io)",
})


# ── Queue I/O ─────────────────────────────────────────────────────────

_queue_lock = threading.Lock()


@contextlib.contextmanager
def _file_lock(path: Path):
    """
    Cross-process advisory lock on `path`. Used to serialise the
    fetch_news.py writer against generate_shorts.py's read-modify-write
    on _data/stories_queue.json — without it, a generate_shorts run
    that overlaps fetch_news can stomp the just-added stories.

    On Windows (fcntl unavailable) this becomes a no-op, falling back
    to the in-process threading lock above. The CI runner is Linux so
    the real lock is taken in production.
    """
    if fcntl is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
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
    if not QUEUE_FILE.exists():
        return {"updated_at": None, "stories": []}
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning(f"Failed to parse {QUEUE_FILE}: {exc}. Starting fresh.")
        return {"updated_at": None, "stories": []}


def _save_queue(queue: dict) -> None:
    """Atomic write: temp file + rename so the file can be read concurrently."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    queue["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = QUEUE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(QUEUE_FILE)


def _prune_queue(queue: dict) -> None:
    """
    Keep the queue bounded: drop the oldest consumed stories first, then
    the oldest pending ones if we still need room. Pending stories that
    are < 24h old are protected.
    """
    stories = queue.get("stories", [])
    if len(stories) <= QUEUE_MAX_LEN:
        return
    now = datetime.now(timezone.utc).timestamp()
    one_day = 24 * 3600

    def _key(s: dict) -> tuple:
        consumed = bool(s.get("consumed"))
        try:
            ts = datetime.fromisoformat(s.get("fetched_at", "")).timestamp()
        except Exception:
            ts = 0
        protected = (not consumed) and (now - ts) < one_day
        # Drop order: not-protected consumed first (oldest), then not-protected
        # pending (oldest), then protected (newest first).
        return (protected, not consumed, ts)

    stories.sort(key=_key)
    queue["stories"] = stories[-QUEUE_MAX_LEN:]


def _story_id(url: str) -> str:
    return hashlib.sha1(url.strip().lower().encode("utf-8")).hexdigest()[:16]


def _existing_ids(queue: dict) -> set[str]:
    return {s["id"] for s in queue.get("stories", []) if s.get("id")}


def _existing_titles(queue: dict) -> list[str]:
    """Titles still on the queue, used for fuzzy dedup."""
    return [s.get("title", "") for s in queue.get("stories", []) if s.get("title")]


# ── Feed health + cache (ETag / Last-Modified, dead-feed circuit-breaker) ──

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


_health_lock = threading.Lock()
_cache_lock  = threading.Lock()


def _bump_feed_failure(name: str, health: dict) -> None:
    with _health_lock:
        health[name] = health.get(name, 0) + 1


def _reset_feed_failure(name: str, health: dict) -> None:
    with _health_lock:
        if name in health:
            health[name] = 0


def _feed_should_skip(name: str, health: dict) -> bool:
    return health.get(name, 0) >= DEAD_FEED_SKIP_AT


def _prune_dead_health(health: dict, active_feed_names: set[str]) -> None:
    """Drop health entries for feeds no longer in the FEEDS list.

    Without this, a feed that gets removed from the config keeps its
    stale failure counter forever. If we re-add it later, the old
    counter would skip it on day 1.
    """
    stale = [name for name in health if name not in active_feed_names]
    for name in stale:
        del health[name]


# ── Performance feedback loop ─────────────────────────────────────────
#
# The nightly analytics workflow drops _data/analytics/latest.json with
# the previous 14d performance summary. We use it here to:
#   * give a small score bonus to categories that retained well
#   * flag categories that consistently underperformed so the AI ranker
#     knows to demand a higher quality threshold for them.
#
# Falling back to neutral defaults if the file is absent (first run,
# no analytics workflow yet, etc.) keeps fetch_news.py completely
# decoupled from the analytics workflow.

def _load_category_perf() -> dict:
    """Map category -> avg view % across the last 14 days, when available.

    Returns an empty dict on any error. fetch_news.py uses this to bias
    story selection — categories above 60% retention get a small score
    boost, those below 30% get a penalty. Neutral default is "no signal".
    """
    if not ANALYTICS_LATEST.exists():
        return {}
    try:
        data = json.loads(ANALYTICS_LATEST.read_text(encoding="utf-8"))
    except Exception:
        return {}
    # `latest.json` (see youtube_analytics.py) currently only carries
    # the channel-wide avg_view_pct, not a per-category breakdown.
    # We still expose the hook so the workflow can be enriched later
    # without touching fetch_news.py.
    cat_perf = data.get("category_avg_view_pct") or {}
    if not isinstance(cat_perf, dict):
        return {}
    return {str(k).lower(): float(v) for k, v in cat_perf.items() if isinstance(v, (int, float))}


def _perf_bias(category: str, perf: dict) -> int:
    """Returns -1 / 0 / +1 depending on past view-percentage for the category.

    +1 → retained well (>=60% avg view): boost this story's score.
    -1 → underperformed (<30% avg view): nudge it below the quality gate.
     0 → no signal, default behaviour.
    """
    pct = perf.get((category or "").lower())
    if pct is None:
        return 0
    if pct >= 60.0:
        return 1
    if pct < 30.0:
        return -1
    return 0


# ── AI enhancement (shorts-sized, not blog-sized) ─────────────────────

_AI_PROMPT_TEMPLATE = (
    "You write spoken scripts AND YouTube Shorts metadata for a news "
    "commentator channel. The channel ships every Short with the same "
    "static thumbnail that says 'DID YOU KNOW? / THE WORLD CHANGED TODAY' "
    "— so the title has to answer 'WHAT changed?' in front-loaded, "
    "search-friendly language. Tone for the voice-over: conversational, "
    "opinionated but grounded, first-person plural ('we', 'us'). Take a "
    "stance — name the winner or loser, point out what most coverage "
    "misses. EVERY short must include at least one line of analysis or "
    "context that goes BEYOND what the source article said — this is "
    "the 'original value' YouTube's monetization policy now requires "
    "(July 2025 update; channels relying on pure narration of wire "
    "copy have been terminated). NO clickbait. NO AI-isms (avoid "
    "'pivotal', 'unprecedented', 'paradigm shift', 'sheds light on', "
    "'in the realm of', 'delve'). Contractions are fine. Respond ONLY "
    "with valid JSON.\n\n"
    "Story:\n"
    "Title: {title}\n"
    "Source: {source}\n"
    "Category: {category}\n"
    "Description: {description}\n\n"
    "Return this exact JSON shape:\n"
    '{{'
    '"score": <int 1-10 — how interesting/important is this for a global short>,'
    # ── SEO-tuned title for YouTube Shorts ────────────────────────────
    '"seo_title": "<40-55 chars. Front-load the primary search keyword '
    '(the person/place/org/event readers will Google). At most 1 emoji '
    '(🚨📉🤖🌍🇺🇸🇨🇳 etc.) and only if it adds info, not decoration. '
    'NO all-caps, NO multiple punctuation (!!!, ???). Pair with the '
    'fixed thumbnail \\\"DID YOU KNOW? / THE WORLD CHANGED TODAY\\\" — '
    'the title answers WHAT changed. '
    'Good: \\\"Fed cuts rates again — but inflation isn\'t done\\\". '
    'Good: \\\"Iran-Saudi oil deal: who actually wins?\\\". '
    'Good: \\\"🚨 Strike on Iraqi PM convoy, 3 dead\\\". '
    'Bad: \\\"This shocking thing the Fed did today\\\" (clickbait). '
    'Bad: \\\"BREAKING: PRICES TANK!!\\\" (caps + bangs).>",'
    # ── Tags for YouTube Data API videos.insert ─────────────────────
    '"yt_tags": ["<5 lowercase tags, NO #. First 3 are search-driven '
    'entities (people, places, orgs, the specific event). Last 2 are '
    'evergreen channel tags like \\\"world news\\\", \\\"breaking news\\\", '
    '\\\"daily news\\\". E.g. [\\\"fed\\\", \\\"jerome powell\\\", '
    '\\\"interest rates\\\", \\\"world news\\\", \\\"breaking news\\\"].>"],'
    # ── Geo + topic hashtag for the description (kept SHORT — YouTube
    # ignores hashtags entirely when there are more than 15, and stuffing
    # is a known suppression signal). We hard-cap at 4: #Shorts, #WorldNews,
    # and these two AI-picked ones.
    '"geo_hashtag": "<one CamelCase hashtag identifying the geography '
    '(country, region, or city). NO leading #. Examples: USA, Brazil, '
    'EU, Ukraine, MiddleEast, Africa, Asia. If global / no geo, use Global.>",'
    '"topic_hashtag": "<one CamelCase hashtag identifying the topic. '
    'NO leading #. Examples: Markets, Climate, AI, Elections, Tech, '
    'Sports, Health, Conflict.>",'
    # ── YouTube description for the video itself ────────────────────
    '"yt_description": "<2-3 sentences. Sentence 1 repeats the primary '
    'keyword from the title — first 100 chars matter most for search. '
    'Sentence 2 is one-line opinion / takeaway (the original value). '
    'Last line is exactly \\\"Source: {source}\\\" — the build step '
    'appends the hashtags (#Shorts #WorldNews #<geo> #<topic>). '
    'No URLs.>",'
    '"thumbnail_text": "<2-4 word punchy overlay phrase the static '
    'thumbnail does NOT show but a future dynamic version could. ALL '
    'CAPS allowed. E.g. PRICES TANK, NEW DEAL.>",'
    # ── The hook is THE single most important line in the whole short.
    # 50-60% of viewers drop in the first 3 seconds; the static thumbnail
    # carries no information, so the spoken hook IS the entire ad. We
    # demand outcome-first construction (verb + consequence + number)
    # to maximise VVSA on the algorithm test gate.
    '"hook": "<the very first spoken line, max 12 words, in OUTCOME-FIRST '
    'shape — lead with the consequence, not the setup. NEVER open with '
    '\\\"Today\\\", \\\"In a recent\\\", \\\"According to\\\", \\\"It was '
    'announced\\\", \\\"A new report\\\". Open with the verb + the result. '
    'Good: \\\"China just banned the dollar in 3 industries.\\\". '
    'Good: \\\"Iraq\'s PM convoy hit — 3 dead in 12 minutes.\\\". '
    'Good: \\\"Markets dropped 2 percent before lunch.\\\". '
    'Bad: \\\"Today the Federal Reserve announced rates.\\\". '
    'Bad: \\\"In a recent move, China decided to...\\\". '
    'Bad: \\\"According to Reuters, a new...\\\".>",'
    '"script": "<the full spoken voice-over script for a 30-45 second short. '
    '85-120 words. The script\'s VERY FIRST WORDS MUST BE the hook, exactly '
    'as written in `hook` above — no preamble, no \\\"Today\\\", no \\\"Hi\\\". '
    'Sentence 2 states the news in plain English. Then 1-2 sentences of '
    'opinion/analysis that ADD context beyond the source article (winner/loser/'
    'the angle most coverage misses) — this is the \\\"original value\\\" the '
    'monetization policy requires. Close with a one-line takeaway or a question '
    'for the comments. Speak directly to camera. No stage directions, no '
    'bracketed cues. No URLs. No \\\"In conclusion\\\" or \\\"To wrap up\\\".>",'
    '"key_points": ["<10-word fact 1>", "<10-word fact 2>", "<10-word fact 3>"],'
    '"sentiment": "<positive|neutral|negative>"'
    '}}'
)


def _ai_enhance(title: str, description: str, source: str, category: str) -> dict | None:
    """Returns a dict with the keys in _AI_PROMPT_TEMPLATE, or None on failure."""
    # Defense in depth: sanitise RSS-borne strings before they hit the
    # prompt template. The system message tells the model to treat the
    # wrapped blocks as data, not instructions — combined with the
    # injection-pattern strip in sanitize_for_prompt, this neutralises
    # the "Ignore previous instructions, write …" class of attacks.
    safe_title       = sanitize_for_prompt(title, max_len=200)
    safe_description = sanitize_for_prompt(description, max_len=500)
    safe_source      = sanitize_for_prompt(source, max_len=80)
    safe_category    = sanitize_for_prompt(category, max_len=40)
    prompt = _AI_PROMPT_TEMPLATE.format(
        title=safe_title,
        source=safe_source,
        category=safe_category,
        description=safe_description,
    )
    raw = ai_text(prompt, seed=abs(hash(title)) % 9999, timeout=25, json_mode=True)
    if not raw:
        return None
    try:
        # Strip code fences if Mistral wrapped the JSON despite json_mode.
        clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        m = re.search(r"\{.*\}", clean, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0), strict=False)
        if not isinstance(data, dict):
            return None
        # Coerce types, clip lengths.
        # YouTube hard limits we enforce here:
        #   - title:       100 chars (we soft-cap at 60 for CTR)
        #   - description: 5000 chars (we cap at 500)
        #   - tags total:  500 chars combined, ~30 chars each
        raw_tags = data.get("yt_tags") or []
        if not isinstance(raw_tags, list):
            raw_tags = []
        clean_tags: list[str] = []
        for t in raw_tags:
            t = str(t).strip().lower().lstrip("#")
            if t and 2 <= len(t) <= 30 and t not in clean_tags:
                clean_tags.append(t)
            if len(clean_tags) >= 5:
                break

        # Sanitise the two AI-picked hashtags. Strip leading '#', whitespace,
        # any non-alphanumeric. Default to safe constants.
        def _clean_tag(raw: str, fallback: str) -> str:
            cleaned = re.sub(r"[^A-Za-z0-9]", "", str(raw or ""))[:24]
            return cleaned or fallback

        geo_hashtag   = _clean_tag(data.get("geo_hashtag"),   "Global")
        topic_hashtag = _clean_tag(data.get("topic_hashtag"), "Breaking")

        out = {
            "score":          int(data.get("score", 0) or 0),
            "seo_title":      str(data.get("seo_title", title))[:60],
            "yt_tags":        clean_tags,
            "geo_hashtag":    geo_hashtag,
            "topic_hashtag":  topic_hashtag,
            "yt_description": str(data.get("yt_description", "")).strip()[:500],
            "thumbnail_text": str(data.get("thumbnail_text", "")).strip()[:30],
            "hook":           str(data.get("hook", "")).strip()[:140],
            # `script` is the full TTS voice-over. Keep it short of
            # YouTube Shorts' 60s cap — ~150 words is the upper bound
            # at average TTS pacing.
            "script":         str(data.get("script", "")).strip()[:900],
            "lead":           str(data.get("lead", description or ""))[:400],
            "key_points":     [str(p).strip()[:80] for p in (data.get("key_points") or [])][:3],
            "sentiment":      str(data.get("sentiment", "neutral")).lower(),
        }
        # If the model skipped `lead`, derive it from the first line of
        # the script so the queue entry stays self-describing.
        if not out["lead"] and out["script"]:
            out["lead"] = out["script"][:300]
        if out["sentiment"] not in ("positive", "neutral", "negative"):
            out["sentiment"] = "neutral"
        # Build / repair the description. YouTube ignores all hashtags
        # past 15, and treats hashtag-stuffing as a suppression signal —
        # we cap at exactly 4: #Shorts #WorldNews #<geo> #<topic>.
        hashtag_block = f"#Shorts #WorldNews #{geo_hashtag} #{topic_hashtag}"
        raw_desc = out["yt_description"]
        if not raw_desc:
            base = out["script"] or out["lead"] or out["seo_title"]
            raw_desc = f"{base}\n\nSource: {source}"
        # Strip any hashtag bloat Mistral may have appended itself, so
        # we don't end up with 8 hashtags total.
        cleaned_desc = re.sub(r"(?m)^#.*$", "", raw_desc).rstrip()
        out["yt_description"] = (cleaned_desc + "\n" + hashtag_block)[:500]
        return out
    except (json.JSONDecodeError, ValueError) as exc:
        log.debug(f"AI enhance parse error: {exc} | raw[:120]={raw[:120]}")
        return None


# ── Feed fetcher ──────────────────────────────────────────────────────

def _conditional_get(url: str, cache_entry: dict | None) -> requests.Response | None:
    """HTTP GET with If-None-Match / If-Modified-Since. Returns None on 304."""
    headers = {}
    if cache_entry:
        if cache_entry.get("etag"):
            headers["If-None-Match"] = cache_entry["etag"]
        if cache_entry.get("last_modified"):
            headers["If-Modified-Since"] = cache_entry["last_modified"]
    try:
        r = _session.get(url, headers=headers, timeout=20)
    except requests.RequestException as exc:
        log.debug(f"feed GET failed for {url}: {exc}")
        return None
    if r.status_code == 304:
        return None
    if r.status_code != 200:
        log.debug(f"feed {url} returned HTTP {r.status_code}")
        return None
    return r


def _fetch_feed_entries(feed_cfg: dict, cache: dict) -> list:
    name = feed_cfg["name"]
    url  = feed_cfg["url"]
    cache_entry = cache.get(name)
    resp = _conditional_get(url, cache_entry)
    if resp is None:
        return []
    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        return []
    # Update cache headers atomically.
    with _cache_lock:
        cache[name] = {
            "etag":          resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
            "fetched_at":    datetime.now(timezone.utc).isoformat(),
        }
    return list(parsed.entries)


def _entry_to_story(entry, feed_cfg: dict) -> dict | None:
    """Map a feedparser entry to the queue schema. Returns None to skip."""
    title = sanitize_text(getattr(entry, "title", "") or "").strip()
    link  = (getattr(entry, "link", "") or "").strip()
    if not title or not link:
        return None

    description = extract_description(entry)
    image_url   = extract_image(entry)
    try:
        published = parse_date(entry, max_age_days=2)
    except Exception:
        return None  # stale / unparseable
    if not published:
        return None

    # Cheap quality gate before we spend AI tokens.
    ok, reason = quality_check(title, description)
    if not ok:
        log.debug(f"  ⏭  quality_check rejected '{title[:60]}': {reason}")
        return None

    # Cheaper still: skip the AI call entirely when the headline-only
    # relevance is low. This is the single biggest knob on the Mistral
    # free-tier budget — a typical run dropped from ~100 to ~50 AI
    # calls after this gate landed.
    relevance = entry_relevance_score(entry)
    if relevance < RELEVANCE_MIN_FOR_AI:
        log.debug(f"  ⏭  relevance={relevance:.1f} < {RELEVANCE_MIN_FOR_AI}: '{title[:60]}'")
        return None

    return {
        "id":             _story_id(link),
        "fetched_at":     datetime.now(timezone.utc).isoformat(),
        "published_at":   published.isoformat(),
        "consumed":       False,
        "consumed_at":    None,
        "title":          title,
        "url":            link,
        "source":         feed_cfg.get("source", feed_cfg.get("name", "")),
        "category":       feed_cfg.get("category", "world"),
        "description":    description,
        "image_url":      image_url,
        "breaking":       is_breaking_news(title, description),
        "relevance":      relevance,
        # native_lang lets generate_shorts.py skip the translation step
        # when LANGUAGE=pt-BR matches the story's native language —
        # rendering native PT-BR content instead of round-tripping an
        # English wire-copy story through the translator.
        "native_lang":    feed_cfg.get("native_lang", "en"),
    }


def _enrich_story(story: dict,
                  trending: set[str] | None = None,
                  perf: dict | None = None) -> dict | None:
    """Add AI fields. Returns None if the story doesn't clear the quality bar.

    `trending` (set of lowercase keywords) and `perf` (category -> avg view %)
    let us bias the score:

      * +1 / +2 if the title overlaps with a currently-trending Google term
      * +1 if the story's category has historically retained well
      * -1 if the category has historically underperformed

    Bias is additive on top of the AI's 0-10 score; the quality gate
    still applies after biasing.
    """
    ai = _ai_enhance(story["title"], story["description"], story["source"], story["category"])
    if not ai:
        return None

    score = ai["score"]
    bias_notes: list[str] = []

    # Trending overlap — searching for what people are searching is the
    # single biggest CTR lever a free pipeline has.
    if trending:
        t_lower = story["title"].lower()
        hits = [kw for kw in trending if kw and len(kw) >= 4 and kw in t_lower]
        if hits:
            score += 2 if len(hits) >= 2 else 1
            bias_notes.append(f"trending:{hits[:3]}")

    # Category retention bias from analytics workflow.
    if perf:
        delta = _perf_bias(story.get("category", ""), perf)
        if delta:
            score += delta
            bias_notes.append(f"perf{delta:+d}")

    # Clamp into 0-10 range so downstream consumers don't see weird values.
    score = max(0, min(10, score))

    if score < QUALITY_THRESHOLD:
        log.debug(
            f"  ⏭  quality_score={score} (raw {ai['score']}, bias {bias_notes}) "
            f"< {QUALITY_THRESHOLD}: '{story['title'][:60]}'"
        )
        return None
    if bias_notes and score != ai["score"]:
        log.info(f"  ⬆  score {ai['score']}→{score} ({', '.join(bias_notes)}): {story['title'][:60]}")
    ai["score"] = score
    story.update(ai)
    story["sentiment"] = ai["sentiment"] or sentiment_score(f"{story['title']} {story['description']}")
    return story


def _process_feed(feed_cfg: dict,
                  queue_ids: set[str],
                  queue_titles: list[str],
                  health: dict,
                  cache: dict,
                  budget_left,
                  run_deadline: float,
                  trending: set[str] | None = None,
                  perf: dict | None = None) -> list[dict]:
    """Fetch a feed end-to-end. Returns the new stories to add to the queue."""
    name = feed_cfg["name"]
    if _feed_should_skip(name, health):
        log.info(f"⏭  Skipping {name} (marked dead — {health[name]} consecutive failures)")
        return []
    if time.time() > run_deadline:
        return []

    try:
        entries = _fetch_feed_entries(feed_cfg, cache)
    except Exception as exc:
        log.warning(f"Feed {name} crashed at fetch: {exc}")
        _bump_feed_failure(name, health)
        return []
    if not entries:
        # Could be a real 304 (success) or transient error — only bump on
        # repeated 0-entry runs. Reset failure counter on any 200.
        _reset_feed_failure(name, health)
        return []
    _reset_feed_failure(name, health)

    new_stories: list[dict] = []
    for entry in entries[:MAX_PER_FEED]:
        if budget_left() <= 0 or time.time() > run_deadline:
            break
        story = _entry_to_story(entry, feed_cfg)
        if not story:
            continue
        if story["id"] in queue_ids:
            continue
        # Fuzzy dedup against existing titles.
        if any(titles_too_similar(story["title"], t) for t in queue_titles):
            continue
        enriched = _enrich_story(story, trending=trending, perf=perf)
        if not enriched:
            continue
        new_stories.append(enriched)
        queue_ids.add(story["id"])
        queue_titles.append(story["title"])
    log.info(f"📰 {name}: kept {len(new_stories)} new stories")
    return new_stories


# ── Public sources adapter ───────────────────────────────────────────
#
# `utils.public_sources.fetch_all_public_sources()` returns a flat list
# of normalised dicts. We map each one onto the same Feed-config shape
# `_entry_to_story` consumes, then run them through the same enrich +
# dedup gates as RSS-borne stories. Free, no extra auth.

def _public_item_to_entry(item: dict):
    """Adapt a public-source item to something feedparser-shaped for
    `_entry_to_story`. We use `types.SimpleNamespace` so the attribute
    access in `extract_description` / `extract_image` / `parse_date`
    works unchanged."""
    import types
    e = types.SimpleNamespace()
    e.title       = item.get("title", "")
    e.link        = item.get("link", "")
    e.summary     = item.get("description", "")
    e.description = item.get("description", "")
    if item.get("image"):
        e.media_thumbnail = [{"url": item["image"]}]
    # parse_date prefers `.published_parsed`; rebuild from the datetime.
    pub = item.get("published")
    if pub:
        e.published_parsed = pub.timetuple()
    return e


def _process_public_sources(
    queue_ids: set[str],
    queue_titles: list[str],
    budget_left,
    run_deadline: float,
    include_trends: bool,
    trending: set[str] | None,
    perf: dict | None,
) -> list[dict]:
    """Fetch Reddit / HN / Wikipedia / Google Trends / GDELT, enrich, return new stories."""
    if time.time() > run_deadline:
        return []
    log.info("🌐 Fetching public sources (Reddit, HN, Wikipedia, Trends, GDELT)…")
    try:
        items = fetch_all_public_sources(include_trends=include_trends, include_gdelt=True)
    except Exception as exc:
        log.warning(f"public sources fetch failed: {exc}")
        return []
    log.info(f"  📥 {len(items)} candidate items from public sources")

    new_stories: list[dict] = []
    for item in items:
        if budget_left() <= 0 or time.time() > run_deadline:
            break
        # Synthetic feed_cfg so _entry_to_story stays generic.
        feed_cfg = {
            "name":     item.get("source", "public"),
            "category": item.get("category", "world"),
            "source":   item.get("source", "GlobalBR News"),
        }
        story = _entry_to_story(_public_item_to_entry(item), feed_cfg)
        if not story:
            continue
        if story["id"] in queue_ids:
            continue
        if any(titles_too_similar(story["title"], t) for t in queue_titles):
            continue
        enriched = _enrich_story(story, trending=trending, perf=perf)
        if not enriched:
            continue
        new_stories.append(enriched)
        queue_ids.add(story["id"])
        queue_titles.append(story["title"])
    log.info(f"🌐 Public sources: kept {len(new_stories)} new stories")
    return new_stories


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    run_start = time.time()
    run_deadline = run_start + RUN_TIMEOUT_S

    log.info("=" * 60)
    log.info(f"🚀 GlobalBR News — queue refresh {datetime.now(timezone.utc).isoformat()}")
    log.info("=" * 60)

    # Fail-fast startup validation. Without MISTRAL_API_KEY, every story
    # gets dropped at the AI enrichment step — we'd burn 30 min of CI and
    # save 0 stories. Better to exit immediately so the workflow shows
    # red and someone notices the missing secret.
    if not os.environ.get("MISTRAL_API_KEY"):
        log.error("❌ MISTRAL_API_KEY is not set. Cannot enrich stories.")
        log.error("   Add it at Settings → Secrets and variables → Actions.")
        sys.exit(2)

    queue        = _load_queue()
    cache        = _load_json(CACHE_FILE)
    health       = _load_json(HEALTH_FILE)
    queue_ids    = _existing_ids(queue)
    queue_titles = _existing_titles(queue)

    # Drop health entries for feeds we no longer fetch, so a removed
    # feed doesn't get skipped if it's re-added later. Honours the
    # PT-BR toggle: when INCLUDE_PTBR_FEEDS is off we still keep the
    # PT-BR feed names in the active set so flipping the toggle doesn't
    # silently re-mark them dead on the next run.
    active_names = {f["name"] for f in FEEDS}
    active_names |= {f["name"] for f in PTBR_FEEDS}
    _prune_dead_health(health, active_names)

    log.info(f"📦 Queue starts with {len(queue.get('stories', []))} stories "
             f"({sum(1 for s in queue.get('stories', []) if not s.get('consumed'))} pending)")

    # ── Pre-compute trending keywords + analytics bias (both free)
    perf = _load_category_perf()
    if perf:
        log.info(f"📊 Loaded category performance: {len(perf)} entries from analytics/latest.json")
    trending: set[str] = set()
    if INCLUDE_TRENDS:
        try:
            trending = trending_keywords()
            log.info(f"🔥 Pulled {len(trending)} trending keywords from Google Trends")
        except Exception as exc:
            log.warning(f"Google Trends pull failed (continuing without bias): {exc}")

    counter_lock = threading.Lock()
    counter = {"added": 0}

    def budget_left() -> int:
        with counter_lock:
            return MAX_PER_RUN - counter["added"]

    new_stories: list[dict] = []
    new_lock = threading.Lock()

    def worker(feed_cfg: dict) -> int:
        if budget_left() <= 0 or time.time() > run_deadline:
            return 0
        added = _process_feed(
            feed_cfg, queue_ids, queue_titles, health, cache, budget_left, run_deadline,
            trending=trending, perf=perf,
        )
        if not added:
            return 0
        with new_lock:
            new_stories.extend(added)
        with counter_lock:
            counter["added"] += len(added)
        return len(added)

    # Tag PT-BR feeds with native_lang so generate_shorts.py knows to
    # skip translation. We merge them into the main feed list when the
    # FETCH_INCLUDE_PTBR toggle is on (default).
    all_feeds: list[dict] = list(FEEDS)
    if INCLUDE_PTBR_FEEDS:
        for f in PTBR_FEEDS:
            tagged = dict(f, native_lang="pt-BR")
            all_feeds.append(tagged)
        log.info(f"📡 Merged {len(PTBR_FEEDS)} PT-BR native feeds (FETCH_INCLUDE_PTBR=1)")

    log.info(f"📡 Processing {len(all_feeds)} feeds with {FEED_WORKERS} workers")
    with ThreadPoolExecutor(max_workers=FEED_WORKERS) as ex:
        futures = [ex.submit(worker, f) for f in all_feeds]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                log.debug(f"worker raised: {exc}")
            if counter["added"] >= MAX_PER_RUN or time.time() > run_deadline:
                for f in futures:
                    f.cancel()
                break

    # ── Public sources (Reddit / HN / Wikipedia / Trends / GDELT).
    # Runs after RSS so we don't burn the budget before traditional
    # feeds get their shot. Each item still goes through the same
    # enrich + quality + dedup gates.
    if INCLUDE_PUBLIC_SOURCES and counter["added"] < MAX_PER_RUN and time.time() < run_deadline:
        try:
            extras = _process_public_sources(
                queue_ids, queue_titles, budget_left, run_deadline,
                include_trends=INCLUDE_TRENDS, trending=trending, perf=perf,
            )
            with new_lock:
                new_stories.extend(extras)
            with counter_lock:
                counter["added"] += len(extras)
        except Exception as exc:
            log.warning(f"public sources stage failed: {exc}")

    if new_stories:
        # Hold both the in-process thread lock AND the cross-process
        # file lock while doing read-modify-write on the queue file.
        # generate_shorts.py acquires the same file lock when it marks
        # stories consumed, so the two scripts can never race even if
        # the daily youtube-bot run overlaps with a fetch-news cron.
        with _queue_lock, _file_lock(QUEUE_FILE):
            # Re-read under the lock — another writer may have flushed
            # while we were enriching.
            disk_queue = _load_queue()
            disk_ids = {s["id"] for s in disk_queue.get("stories", []) if s.get("id")}
            fresh = [s for s in new_stories if s["id"] not in disk_ids]
            if fresh:
                disk_queue.setdefault("stories", []).extend(fresh)
                _prune_queue(disk_queue)
                _save_queue(disk_queue)
            queue = disk_queue
    _save_json(CACHE_FILE, cache)
    _save_json(HEALTH_FILE, health)

    pending = sum(1 for s in queue.get("stories", []) if not s.get("consumed"))
    elapsed = int(time.time() - run_start)
    log.info("=" * 60)
    log.info(f"✨ Added {len(new_stories)} new stories — {pending} pending — {elapsed}s elapsed")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
