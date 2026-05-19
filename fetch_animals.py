#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_animals.py — Build the daily Shorts queue from animal Pexels clips.

Replaces fetch_news.py for the channel's content pivot from news to
animal compilation Shorts. The downstream pipeline (generate_shorts.py
+ upload_youtube.py) is unchanged — this script writes the same
`_data/stories_queue.json` shape, so every existing consumer keeps
working.

How it works
============

1. Walks a static topic table (`ANIMAL_TOPICS`) that maps each animal
   category to (a) Pexels search queries and (b) channel-side tags +
   topic hashtag + a short description prefix used by the AI prompt.

2. For each topic, queries Pexels (1 query per slot per run, rotating
   so we don't burn through the same 5 queries every 3 hours). Each
   matching Pexels clip becomes one queue entry — the clip is what
   `generate_shorts.py` will see when it later asks the b-roll picker
   for "cats playing" or "dolphins jumping".

3. Calls `utils.ai_helper.ai_text` with an animal-tuned JSON prompt
   to produce hook + script + seo_title + thumbnail_text + tags. The
   prompt mirrors the fields fetch_news.py asks for so the downstream
   schema is identical.

4. Merges new entries onto the existing `stories_queue.json`,
   deduplicating by `id` (= sha1 of the Pexels clip URL). Older,
   consumed entries are pruned to keep the file bounded.

What's intentionally NOT here
=============================

* No RSS / no feedparser — Pexels IS the discovery layer now.
* No brand-safety filter — animal content has no political RPM risk.
* No breaking-news classifier — same reason.
* No translation — start with EN, PT-BR is a future pass.
* No native-lang feeds — Pexels metadata is mostly English regardless.

Operator knobs (env vars)
=========================

  PEXELS_API_KEY          (required) — same secret used by utils/broll.py
  MISTRAL_API_KEY         (required) — AI enhancement
  ANIMALS_MAX_PER_TOPIC   (default 4) — clips fetched per topic per run
  ANIMALS_KEEP_DAYS       (default 14) — prune older entries
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from utils.ai_cache import prune as ai_cache_prune
from utils.ai_helper import ai_text
from utils.broll import fetch_pexels

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("fetch_animals.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


QUEUE_FILE = Path("_data/stories_queue.json")
MAX_PER_TOPIC = int(os.environ.get("ANIMALS_MAX_PER_TOPIC", "4"))
KEEP_DAYS = int(os.environ.get("ANIMALS_KEEP_DAYS", "14"))


# ── Topic table ───────────────────────────────────────────────────
#
# Each topic carries:
#   * `queries`    — list of Pexels search phrases. We rotate through
#                    them per-run so a 3-hour cron doesn't burn the
#                    same 4 phrases every time.
#   * `topic_hashtag` — CamelCase channel hashtag for the description.
#   * `tags`       — base evergreen tags appended after the AI-picked ones.
#   * `description_prefix` — handed to the AI as the "what this clip
#                    shows" context. Keeps the prompt under control
#                    without giving the model open license to invent.
ANIMAL_TOPICS: dict[str, dict] = {
    "cats": {
        "queries": [
            "cat playing", "kitten", "cat sleeping", "cat funny",
            "cat jumping", "cat hunting", "domestic cat",
        ],
        "topic_hashtag": "Cats",
        "tags": ["cats", "kittens", "cat facts", "feline"],
        "description_prefix": "A clip of cats / kittens",
    },
    "dogs": {
        "queries": [
            "dog playing", "puppy", "dog running", "dog beach",
            "golden retriever", "dog snow", "puppy playing",
        ],
        "topic_hashtag": "Dogs",
        "tags": ["dogs", "puppies", "dog facts", "canine"],
        "description_prefix": "A clip of dogs / puppies",
    },
    "ocean": {
        "queries": [
            "dolphin", "whale", "shark", "underwater fish",
            "sea turtle", "octopus", "coral reef",
        ],
        "topic_hashtag": "Ocean",
        "tags": ["ocean", "marine life", "sea animals", "underwater"],
        "description_prefix": "A clip of marine life in the ocean",
    },
    "wildlife": {
        "queries": [
            "lion", "elephant", "tiger", "leopard",
            "bear", "wolf", "deer", "fox",
        ],
        "topic_hashtag": "Wildlife",
        "tags": ["wildlife", "wild animals", "nature", "safari"],
        "description_prefix": "A clip of wild animals in nature",
    },
    "birds": {
        "queries": [
            "eagle flying", "parrot", "hummingbird", "owl",
            "penguin", "flamingo", "macaw",
        ],
        "topic_hashtag": "Birds",
        "tags": ["birds", "bird facts", "avian", "wildlife"],
        "description_prefix": "A clip of birds",
    },
    "farm": {
        "queries": [
            "horse running", "baby goat", "cow", "sheep",
            "duckling", "farm animals",
        ],
        "topic_hashtag": "FarmAnimals",
        "tags": ["farm animals", "horses", "farm life", "countryside"],
        "description_prefix": "A clip of farm animals",
    },
}


# ── AI prompt ─────────────────────────────────────────────────────

_AI_PROMPT_TEMPLATE = (
    "You write fun, educational scripts about animals for YouTube "
    "Shorts. Every Short combines stock footage of an animal with a "
    "30-second voice-over packed with surprising facts. The viewer "
    "should learn something they did not know. Tone: friendly, "
    '"did you know..." energy, no clickbait, no AI-isms (avoid '
    "'pivotal', 'unprecedented', 'paradigm shift', 'delve', 'in the "
    "realm of'). Contractions are fine. Speak directly to camera. "
    "Respond ONLY with valid JSON.\n\n"
    "Clip:\n"
    "Subject: {subject}\n"
    "Context: {context}\n\n"
    "Return this exact JSON shape:\n"
    "{{"
    '"score": <int 1-10 — how interesting is this subject for a '
    "global animal-fact Short>,"
    '"seo_title": "<40-55 chars. Front-load the search keyword '
    "(the animal name + the curious angle). At most 1 relevant "
    "emoji (🐱🐶🦅🐬 etc.) and only if it adds info. NO all-caps, "
    "NO multiple punctuation. "
    'Good: \\"Why cats really purr — it is not just happiness\\". '
    'Good: \\"Dolphins call each other by name (yes, really)\\". '
    'Bad: \\"You won\'t BELIEVE what this cat did!!!\\".>",'
    '"yt_tags": ["<5 lowercase tags. First 3 are subject-specific '
    "(animal name, behavior, body part). Last 2 are evergreen "
    '(\\"animals\\", \\"animal facts\\", \\"wildlife\\", '
    '\\"nature\\").>"],'
    '"topic_hashtag": "<one CamelCase hashtag identifying the '
    "animal group. NO leading #. Examples: Cats, Dogs, Wildlife, "
    'Ocean, Birds, FarmAnimals.>",'
    '"yt_description": "<2-3 sentences. Sentence 1 repeats the '
    "subject keyword. Sentence 2 is the single most surprising "
    "fact from the script. Last line is exactly "
    '\\"Source: Pexels\\" — the build step appends the hashtags '
    "(#Shorts #Animals #<topic>). No URLs.>\","
    '"thumbnail_text": "<2-4 word punchy phrase the thumbnail '
    "overlay will use. ALL CAPS allowed. "
    'E.g. WHY CATS PURR, DOLPHIN NAMES, FOX SECRETS.>",'
    '"hook": "<the very first spoken line, max 12 words. Lead '
    "with the surprising fact, not setup. "
    'Good: \\"Cats purr to heal their own bones.\\". '
    'Good: \\"Dolphins call each other by name.\\". '
    'Bad: \\"Today I will tell you about cats.\\".>",'
    '"script": "<the full voice-over for a 30-45 second short. '
    "85-120 words. The script's FIRST WORDS MUST BE the hook, "
    "verbatim. Then 3-5 surprising facts about the subject, each "
    "as a short sentence. Close with a one-line question for the "
    'comments. No \\"In conclusion\\", no \\"To wrap up\\", '
    "no stage directions, no URLs.>\","
    '"sentiment": "positive"'
    "}}"
)


def _ai_enhance_animal(subject: str, context: str) -> dict | None:
    """Run the AI enhancement for an animal subject + return the
    parsed JSON, or None on parse failure. Mirrors the shape of
    fetch_news._ai_enhance so downstream code is unchanged.
    """
    prompt = _AI_PROMPT_TEMPLATE.format(subject=subject, context=context)
    raw = ai_text(prompt, seed=abs(hash(subject)) % 9999, timeout=25,
                  json_mode=True)
    if not raw:
        return None
    try:
        # Strip code fences if the model wrapped the JSON.
        clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        m = re.search(r"\{.*\}", clean, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0), strict=False)
        if not isinstance(data, dict):
            return None
    except (json.JSONDecodeError, ValueError) as exc:
        log.debug("animal AI parse error: %s | raw[:120]=%s", exc, raw[:120])
        return None

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

    def _clean_tag(raw: str, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]", "", str(raw or ""))[:24]
        return cleaned or fallback

    topic_hashtag = _clean_tag(data.get("topic_hashtag"), "Animals")
    geo_hashtag = "Global"  # animal content is universal

    out = {
        "score":          int(data.get("score", 7) or 7),
        "seo_title":      str(data.get("seo_title", subject))[:60],
        "yt_tags":        clean_tags,
        "geo_hashtag":    geo_hashtag,
        "topic_hashtag":  topic_hashtag,
        "yt_description": str(data.get("yt_description", "")).strip()[:500],
        "thumbnail_text": str(data.get("thumbnail_text", "")).strip()[:30],
        "hook":           str(data.get("hook", "")).strip()[:140],
        "script":         str(data.get("script", "")).strip()[:900],
        "lead":           str(data.get("script", subject))[:400],
        "sentiment":      "positive",  # animal content is always positive
    }

    # Build the final description with channel-standard hashtags.
    hashtag_block = f"#Shorts #Animals #{topic_hashtag}"
    raw_desc = out["yt_description"]
    if not raw_desc:
        base = out["script"] or out["seo_title"]
        raw_desc = f"{base}\n\nSource: Pexels"
    cleaned_desc = re.sub(r"(?m)^#.*$", "", raw_desc).rstrip()
    out["yt_description"] = (cleaned_desc + "\n" + hashtag_block)[:500]
    return out


# ── Queue I/O ─────────────────────────────────────────────────────

def _story_id(url: str) -> str:
    """Short stable id from the Pexels page URL — used for dedupe."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _load_queue() -> dict:
    if QUEUE_FILE.exists():
        try:
            d = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("stories"), list):
                return d
        except Exception as exc:
            log.warning("queue read failed (%s) — starting fresh", exc)
    return {"updated_at": None, "stories": []}


def _prune_queue(stories: list[dict], keep_days: int) -> list[dict]:
    """Drop consumed stories older than `keep_days`."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    out: list[dict] = []
    for s in stories:
        if not s.get("consumed"):
            out.append(s)
            continue
        consumed_at_raw = s.get("consumed_at") or s.get("fetched_at")
        try:
            consumed_at = datetime.fromisoformat(consumed_at_raw)
        except (TypeError, ValueError):
            out.append(s)
            continue
        if consumed_at >= cutoff:
            out.append(s)
    return out


def _build_story(clip_subject: str,
                 topic_key: str,
                 topic_cfg: dict,
                 pexels_clip: "BrollClip",
                 ai_out: dict) -> dict:
    """Assemble the queue entry. Matches the news queue shape so
    `generate_shorts.py` doesn't need to change."""
    url = pexels_clip.url or f"https://www.pexels.com/video/{_story_id(pexels_clip.download_url)}"
    now = datetime.now(timezone.utc).isoformat()
    # Merge the AI-picked tags with the topic's evergreen tags,
    # deduplicating. Capped at 8 to leave room for upload_youtube's
    # tag-packer + evergreens it adds later.
    merged_tags: list[str] = list(ai_out.get("yt_tags") or [])
    for t in topic_cfg.get("tags", []):
        if t not in merged_tags:
            merged_tags.append(t)
        if len(merged_tags) >= 8:
            break
    return {
        "id":             _story_id(url),
        "fetched_at":     now,
        "published_at":   now,
        "consumed":       False,
        "consumed_at":    None,
        "title":          clip_subject,
        "url":            url,
        "source":         "Pexels",
        "category":       topic_key,
        "description":    f"{topic_cfg.get('description_prefix', 'A clip of an animal')}: {pexels_clip.title or clip_subject}".strip(),
        # BrollClip doesn't carry a preview image — leave empty; the
        # generator renders its own title card frame.
        "image_url":      "",
        "breaking":       False,
        # Animals are always relevant for this channel — score the AI's
        # opinion on top of a high baseline so a story with score=8 from
        # the AI still wins over a 4 even after the bias chain.
        "relevance":      9.0,
        "score":          ai_out.get("score", 7),
        "safety_penalty": 0,
        "native_lang":    "en",
        # AI-enriched fields below.
        "seo_title":      ai_out["seo_title"],
        "yt_tags":        merged_tags[:8],
        "geo_hashtag":    ai_out["geo_hashtag"],
        "topic_hashtag":  ai_out["topic_hashtag"],
        "yt_description": ai_out["yt_description"],
        "thumbnail_text": ai_out["thumbnail_text"],
        "hook":           ai_out["hook"],
        "script":         ai_out["script"],
        "lead":           ai_out["lead"],
        "sentiment":      ai_out["sentiment"],
        # Pexels-specific extras — kept so a follow-up PR can later
        # bias `generate_shorts.acquire_broll_clips` to PREFER the
        # exact clip that informed the script.
        "pexels_video_id":     pexels_clip.url.rsplit("/", 2)[-2] if pexels_clip.url else "",
        "pexels_download_url": pexels_clip.download_url,
    }


# ── Main ──────────────────────────────────────────────────────────

def _rotate_queries(topic_key: str, queries: list[str], take: int) -> list[str]:
    """Pick `take` queries deterministically rotated by the current
    3-hour window. This stops the same N runs/day from hitting the
    same N queries every time, keeping the queue more diverse.
    """
    if not queries:
        return []
    window = datetime.now(timezone.utc).hour // 3  # 0..7
    start = (hash(topic_key) + window) % len(queries)
    return [queries[(start + i) % len(queries)] for i in range(take)]


def main() -> int:
    from utils.panic import abort_if_halted
    abort_if_halted("fetch_animals")

    log.info("=" * 60)
    log.info("🐾 GlobalBR News — animal queue refresh %s",
             datetime.now(timezone.utc).isoformat())
    log.info("=" * 60)

    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not pexels_key:
        log.error("❌ PEXELS_API_KEY not set — cannot fetch animal clips.")
        return 2
    if not os.environ.get("MISTRAL_API_KEY", "").strip():
        log.error("❌ MISTRAL_API_KEY not set — cannot enrich scripts.")
        return 2

    queue = _load_queue()
    existing_ids: set[str] = {s.get("id") for s in queue["stories"] if s.get("id")}
    new_entries: list[dict] = []

    for topic_key, topic_cfg in ANIMAL_TOPICS.items():
        per_topic_n = MAX_PER_TOPIC
        queries = _rotate_queries(topic_key, topic_cfg["queries"], take=2)
        log.info("🔎 %s: queries=%s", topic_key, queries)
        clips: list = []
        for q in queries:
            if len(clips) >= per_topic_n:
                break
            try:
                clips.extend(fetch_pexels(q, per_page=4))
            except Exception as exc:
                log.warning("pexels fetch failed for %r: %s", q, exc)
        # Cap, shuffle a little so consecutive runs don't always
        # consume the same top-of-results clip.
        random.shuffle(clips)
        clips = clips[:per_topic_n]
        log.info("📹 %s: %d clip(s) returned by Pexels", topic_key, len(clips))

        for clip in clips:
            sid = _story_id(clip.url or clip.download_url)
            if sid in existing_ids:
                continue
            subject = clip.title or queries[0]
            context = topic_cfg.get("description_prefix", "an animal clip")
            ai_out = _ai_enhance_animal(subject, context)
            if not ai_out:
                log.debug("  ⏭  AI enrichment failed for %s", subject[:60])
                continue
            story = _build_story(subject, topic_key, topic_cfg, clip, ai_out)
            new_entries.append(story)
            existing_ids.add(story["id"])

    # Merge + prune.
    queue["stories"].extend(new_entries)
    queue["stories"] = _prune_queue(queue["stories"], KEEP_DAYS)
    queue["updated_at"] = datetime.now(timezone.utc).isoformat()
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(
        json.dumps(queue, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    pending = sum(1 for s in queue["stories"] if not s.get("consumed"))
    log.info("✅ +%d new animal entries (queue: %d total, %d pending)",
             len(new_entries), len(queue["stories"]), pending)

    # Keep the AI disk cache bounded — same chore fetch_news.py does.
    try:
        ai_cache_prune(ttl_days=30)
    except Exception as exc:
        log.debug("ai_cache prune skipped: %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
