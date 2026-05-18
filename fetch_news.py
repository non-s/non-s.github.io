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

import hashlib
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

from utils.ai_helper import (
    ai_text,
    is_breaking_news,
    quality_check,
    quality_score,
    sentiment_score,
)
from utils.dedup import titles_too_similar
from utils.ranking import entry_relevance_score
from utils.text import (
    extract_description,
    extract_image,
    parse_date,
    sanitize_text,
    slugify,
)

# ── Config ────────────────────────────────────────────────────────────

DATA_DIR    = Path("_data")
QUEUE_FILE  = DATA_DIR / "stories_queue.json"
CACHE_FILE  = DATA_DIR / "feed_cache.json"
HEALTH_FILE = DATA_DIR / "feed_health.json"
LOG_FILE    = "fetch_news.log"

MAX_PER_FEED      = int(os.environ.get("FETCH_MAX_PER_FEED", "10"))
MAX_PER_RUN       = int(os.environ.get("FETCH_MAX_PER_RUN",  "100"))
FEED_WORKERS      = int(os.environ.get("FETCH_FEED_WORKERS", "10"))
QUALITY_THRESHOLD = int(os.environ.get("FETCH_QUALITY_THRESHOLD", "6"))
RUN_TIMEOUT_S     = int(os.environ.get("FETCH_TIMEOUT_S",    "3300"))
DEAD_FEED_SKIP_AT = 5  # consecutive failures before we stop trying

# Keep the queue bounded — older consumed stories get pruned.
QUEUE_MAX_LEN = 500

FEEDS: list[dict] = [
    # World / general
    {"name": "BBC World",         "url": "https://feeds.bbci.co.uk/news/world/rss.xml",                              "category": "world",       "source": "BBC"},
    {"name": "Reuters World",     "url": "https://feeds.reuters.com/Reuters/worldNews",                              "category": "world",       "source": "Reuters"},
    {"name": "Guardian World",    "url": "https://www.theguardian.com/world/rss",                                    "category": "world",       "source": "The Guardian"},
    {"name": "Al Jazeera",        "url": "https://www.aljazeera.com/xml/rss/all.xml",                                "category": "world",       "source": "Al Jazeera"},

    # Tech / AI
    {"name": "TechCrunch",        "url": "https://techcrunch.com/feed/",                                              "category": "technology",  "source": "TechCrunch"},
    {"name": "The Verge",         "url": "https://www.theverge.com/rss/index.xml",                                    "category": "technology",  "source": "The Verge"},
    {"name": "Wired",             "url": "https://www.wired.com/feed/rss",                                            "category": "technology",  "source": "Wired"},
    {"name": "Ars Technica",      "url": "https://feeds.arstechnica.com/arstechnica/index",                           "category": "technology",  "source": "Ars Technica"},
    {"name": "TechCrunch AI",     "url": "https://techcrunch.com/category/artificial-intelligence/feed/",             "category": "ai",          "source": "TechCrunch"},

    # Business
    {"name": "Reuters Business",  "url": "https://feeds.reuters.com/reuters/businessNews",                            "category": "business",    "source": "Reuters"},
    {"name": "CNBC",              "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",                     "category": "business",    "source": "CNBC"},

    # Science / health / sports / entertainment
    {"name": "BBC Science",       "url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",              "category": "science",     "source": "BBC"},
    {"name": "BBC Health",        "url": "http://feeds.bbci.co.uk/news/health/rss.xml",                               "category": "health",      "source": "BBC"},
    {"name": "ESPN Top",          "url": "https://www.espn.com/espn/rss/news",                                        "category": "sports",      "source": "ESPN"},
    {"name": "Variety",           "url": "https://variety.com/feed/",                                                 "category": "entertainment","source": "Variety"},

    # Security
    {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/",                                          "category": "security",    "source": "Krebs on Security"},
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


# ── AI enhancement (shorts-sized, not blog-sized) ─────────────────────

_AI_PROMPT_TEMPLATE = (
    "You write spoken scripts AND YouTube Shorts metadata for a news "
    "commentator channel. The channel ships every Short with the same "
    "static thumbnail that says 'DID YOU KNOW? / THE WORLD CHANGED TODAY' "
    "— so the title has to answer 'WHAT changed?' in front-loaded, "
    "search-friendly language. Tone for the voice-over: conversational, "
    "opinionated but grounded, first-person plural ('we', 'us'). Take a "
    "stance — name the winner or loser, point out what most coverage "
    "misses. NO clickbait. NO AI-isms (avoid 'pivotal', 'unprecedented', "
    "'paradigm shift', 'sheds light on', 'in the realm of', 'delve'). "
    "Contractions are fine. Respond ONLY with valid JSON.\n\n"
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
    # ── YouTube description for the video itself ────────────────────
    '"yt_description": "<2-3 sentences. Sentence 1 repeats the primary '
    'keyword from the title — first 100 chars matter most for search. '
    'Sentence 2 is one-line opinion / takeaway. Last line is exactly '
    '\\\"Source: {source}\\\\n#Shorts #BreakingNews\\\" (literal newline). '
    'No URLs.>",'
    '"thumbnail_text": "<2-4 word punchy overlay phrase the static '
    'thumbnail does NOT show but a future dynamic version could. ALL '
    'CAPS allowed. E.g. PRICES TANK, NEW DEAL.>",'
    '"hook": "<the very first spoken line, max 12 words, snappy enough to stop a scroll>",'
    '"script": "<the full spoken voice-over script for a 30-45 second short. 85-120 words. Starts with the hook. State the news in plain English in one sentence. Then 1-2 sentences of opinion/analysis (call out who wins, who loses, what is suspect, the angle most coverage misses). Close with a one-line takeaway or a question for the comments. Speak directly to camera. No stage directions, no bracketed cues. No URLs.>",'
    '"key_points": ["<10-word fact 1>", "<10-word fact 2>", "<10-word fact 3>"],'
    '"sentiment": "<positive|neutral|negative>"'
    '}}'
)


def _ai_enhance(title: str, description: str, source: str, category: str) -> dict | None:
    """Returns a dict with the keys in _AI_PROMPT_TEMPLATE, or None on failure."""
    prompt = _AI_PROMPT_TEMPLATE.format(
        title=title[:200],
        source=source,
        category=category,
        description=(description or "")[:500],
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

        out = {
            "score":          int(data.get("score", 0) or 0),
            "seo_title":      str(data.get("seo_title", title))[:60],
            "yt_tags":        clean_tags,
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
        # If the model returned no description, synthesise a usable one
        # from script + source. Better to fall back than to upload with
        # an empty description (YouTube SEO suffers).
        if not out["yt_description"]:
            base = out["script"] or out["lead"] or out["seo_title"]
            out["yt_description"] = f"{base}\n\nSource: {source}\n#Shorts #BreakingNews"[:500]
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
        "relevance":      entry_relevance_score(entry),
    }


def _enrich_story(story: dict) -> dict | None:
    """Add AI fields. Returns None if the story doesn't clear the quality bar."""
    ai = _ai_enhance(story["title"], story["description"], story["source"], story["category"])
    if not ai:
        return None
    if ai["score"] < QUALITY_THRESHOLD:
        log.debug(f"  ⏭  quality_score={ai['score']} < {QUALITY_THRESHOLD}: '{story['title'][:60]}'")
        return None
    story.update(ai)
    story["sentiment"] = ai["sentiment"] or sentiment_score(f"{story['title']} {story['description']}")
    return story


def _process_feed(feed_cfg: dict,
                  queue_ids: set[str],
                  queue_titles: list[str],
                  health: dict,
                  cache: dict,
                  budget_left,
                  run_deadline: float) -> list[dict]:
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
        enriched = _enrich_story(story)
        if not enriched:
            continue
        new_stories.append(enriched)
        queue_ids.add(story["id"])
        queue_titles.append(story["title"])
    log.info(f"📰 {name}: kept {len(new_stories)} new stories")
    return new_stories


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    run_start = time.time()
    run_deadline = run_start + RUN_TIMEOUT_S

    log.info("=" * 60)
    log.info(f"🚀 GlobalBR News — queue refresh {datetime.now(timezone.utc).isoformat()}")
    log.info("=" * 60)

    queue        = _load_queue()
    cache        = _load_json(CACHE_FILE)
    health       = _load_json(HEALTH_FILE)
    queue_ids    = _existing_ids(queue)
    queue_titles = _existing_titles(queue)

    log.info(f"📦 Queue starts with {len(queue.get('stories', []))} stories "
             f"({sum(1 for s in queue.get('stories', []) if not s.get('consumed'))} pending)")

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
        )
        if not added:
            return 0
        with new_lock:
            new_stories.extend(added)
        with counter_lock:
            counter["added"] += len(added)
        return len(added)

    log.info(f"📡 Processing {len(FEEDS)} feeds with {FEED_WORKERS} workers")
    with ThreadPoolExecutor(max_workers=FEED_WORKERS) as ex:
        futures = [ex.submit(worker, f) for f in FEEDS]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                log.debug(f"worker raised: {exc}")
            if counter["added"] >= MAX_PER_RUN or time.time() > run_deadline:
                for f in futures:
                    f.cancel()
                break

    if new_stories:
        with _queue_lock:
            queue.setdefault("stories", []).extend(new_stories)
            _prune_queue(queue)
            _save_queue(queue)
    _save_json(CACHE_FILE, cache)
    _save_json(HEALTH_FILE, health)

    pending = sum(1 for s in queue.get("stories", []) if not s.get("consumed"))
    elapsed = int(time.time() - run_start)
    log.info("=" * 60)
    log.info(f"✨ Added {len(new_stories)} new stories — {pending} pending — {elapsed}s elapsed")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
