#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_animals.py — Build the daily Shorts queue from animal Pexels clips.

Runs the channel's animal-facts queue from discovery to enrichment.
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
   prompt mirrors the fields fetch_animals.py asks for so the downstream
   schema is identical.

4. Merges new entries onto the existing `stories_queue.json`,
   deduplicating by `id` (= sha1 of the Pexels clip URL). Older,
   consumed entries are pruned to keep the file bounded.

What's intentionally NOT here
=============================

* No RSS / no feedparser — Pexels IS the discovery layer now.
* No brand-safety filter — every queue item is already animal content.
* No urgency classifier — evergreen facts do not need one.
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
# Permanent ledger of Pexels clips we already published. Survives
# `_prune_queue` and any queue rebuild, so a clip that was shipped
# weeks ago can never re-enter the rotation. `upload_youtube.py`
# appends to this on a successful upload (see
# `record_published_clip()` below); `main()` filters Pexels candidates
# against it before paying for AI enrichment.
PUBLISHED_CLIPS_FILE = Path("_data/published_clips.json")
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
#   * `discovery_hashtags` — YouTube Shorts search hashtags. Each row
#                    mixes topic, niche, and educational intent.
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
        "discovery_hashtags": [
            "cats", "kittens", "catfacts", "animals", "funfacts",
        ],
        "description_prefix": "A clip of cats / kittens",
    },
    "dogs": {
        "queries": [
            "dog playing", "puppy", "dog running", "dog beach",
            "golden retriever", "dog snow", "puppy playing",
        ],
        "topic_hashtag": "Dogs",
        "tags": ["dogs", "puppies", "dog facts", "canine"],
        "discovery_hashtags": [
            "dogs", "puppies", "dogfacts", "animals", "funfacts",
        ],
        "description_prefix": "A clip of dogs / puppies",
    },
    "ocean": {
        "queries": [
            "dolphin", "whale", "shark", "underwater fish",
            "sea turtle", "octopus", "coral reef",
        ],
        "topic_hashtag": "Ocean",
        "tags": ["ocean", "marine life", "sea animals", "underwater"],
        "discovery_hashtags": [
            "ocean", "oceanlife", "marinelife", "animalfacts", "funfacts",
        ],
        "description_prefix": "A clip of marine life in the ocean",
    },
    "wildlife": {
        "queries": [
            "lion", "elephant", "tiger", "leopard",
            "bear", "wolf", "deer", "fox",
        ],
        "topic_hashtag": "Wildlife",
        "tags": ["wildlife", "wild animals", "nature", "safari"],
        "discovery_hashtags": [
            "wildlife", "wildanimals", "safari", "animalfacts", "funfacts",
        ],
        "description_prefix": "A clip of wild animals in nature",
    },
    "birds": {
        "queries": [
            "eagle flying", "parrot", "hummingbird", "owl",
            "penguin", "flamingo", "macaw",
        ],
        "topic_hashtag": "Birds",
        "tags": ["birds", "bird facts", "avian", "wildlife"],
        "discovery_hashtags": [
            "birds", "birdfacts", "nature", "animals", "funfacts",
        ],
        "description_prefix": "A clip of birds",
    },
    "farm": {
        "queries": [
            "horse running", "baby goat", "cow", "sheep",
            "duckling", "farm animals",
        ],
        "topic_hashtag": "FarmAnimals",
        "tags": ["farm animals", "horses", "farm life", "countryside"],
        "discovery_hashtags": [
            "farmanimals", "countrylife", "animalfacts", "nature", "funfacts",
        ],
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
    '\\"Source: Pexels\\". Do NOT include any hashtags — the build '
    "step adds YouTube Shorts hashtags afterwards. No URLs.>\","
    '"thumbnail_text": "<2-4 word punchy phrase the thumbnail '
    "overlay will use. ALL CAPS allowed. "
    'E.g. WHY CATS PURR, DOLPHIN NAMES, FOX SECRETS.>",'
    '"hook": "<the very first spoken line, max 12 words. Lead '
    "with the surprising fact, not setup. "
    'Good: \\"Cats purr to heal their own bones.\\". '
    'Good: \\"Dolphins call each other by name.\\". '
    'Bad: \\"Today I will tell you about cats.\\".>",'
    '"script": "<the full voice-over for a 25-35 second short. '
    "70-90 words MAX (YouTube Shorts rewards completion-rate; "
    "shorter wins). The script's FIRST WORDS MUST BE the hook, "
    "verbatim. Then 2-3 surprising facts about the subject, each "
    "as a short sentence. Close with a one-line question for the "
    'comments. No \\"In conclusion\\", no \\"To wrap up\\", '
    "no stage directions, no URLs.>\","
    '"sentiment": "positive"'
    "}}"
)


def _ai_enhance_animal(subject: str, context: str) -> dict | None:
    """Run the AI enhancement for an animal subject + return the
    parsed JSON, or None on parse failure. Mirrors the shape of
    fetch_animals._ai_enhance so downstream code is unchanged.
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

    # Hashtags are NOT injected here anymore — generate_shorts.py owns
    # the YouTube Shorts hashtag block construction. We just hand off a
    # clean description body; any stray hashtag lines authored by the
    # model are stripped so the caption builder doesn't have to.
    raw_desc = out["yt_description"]
    if not raw_desc:
        base = out["script"] or out["seo_title"]
        raw_desc = f"{base}\n\nSource: Pexels"
    cleaned_desc = re.sub(r"(?m)^#.*$", "", raw_desc).rstrip()
    out["yt_description"] = cleaned_desc[:500]
    return out


# ── Queue I/O ─────────────────────────────────────────────────────

def _story_id(url: str) -> str:
    """Short stable id from the Pexels page URL — used for dedupe."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _pexels_id_from_clip(clip) -> str:
    """Pull the canonical Pexels video id from a BrollClip. Pexels
    page URLs look like `https://www.pexels.com/video/<slug>/<id>/`
    — `rsplit("/", 2)[-2]` is the id, regardless of which slug Pexels
    chose for that clip. Empty string if we can't extract one."""
    url = getattr(clip, "url", "") or ""
    if not url:
        return ""
    try:
        candidate = url.rstrip("/").rsplit("/", 1)[-1]
        if candidate.isdigit():
            return candidate
        return url.rsplit("/", 2)[-2]
    except Exception:
        return ""


# ── Published-clips ledger ────────────────────────────────────────

def load_published_clip_keys() -> set[str]:
    """Return the permanent set of Pexels clip identifiers we already
    shipped. Each entry is matched by BOTH `pexels_video_id` (Pexels
    canonical id) and the queue-side `story_id` (sha1 of the page
    URL) — whichever is recorded survives schema variations.

    Empty set if the ledger doesn't exist yet.
    """
    if not PUBLISHED_CLIPS_FILE.exists():
        return set()
    try:
        data = json.loads(PUBLISHED_CLIPS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("published_clips parse failed: %s — treating as empty", exc)
        return set()
    if not isinstance(data, dict):
        return set()
    keys: set[str] = set()
    for entry in (data.get("clips") or []):
        if not isinstance(entry, dict):
            continue
        for field in ("pexels_video_id", "story_id"):
            val = entry.get(field)
            if val:
                keys.add(str(val))
    return keys


def record_published_clip(*, pexels_video_id: str = "",
                          story_id: str = "",
                          pexels_url: str = "",
                          platform_video_id: str = "",
                          **_legacy) -> None:
    """Append one record to the permanent published-clips ledger.

    Called by upload_youtube.py right after a successful publish, so a
    clip that ships can NEVER be re-enqueued. Atomic write via tmp +
    rename so a crash mid-write doesn't corrupt the file.

    `**_legacy` swallows old kwargs (e.g. `youtube_video_id=`) so older
    callers don't crash; the value is stored in `platform_video_id`.
    """
    if not pexels_video_id and not story_id:
        return  # nothing to record
    if not platform_video_id and _legacy.get("youtube_video_id"):
        platform_video_id = _legacy["youtube_video_id"]
    PUBLISHED_CLIPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"clips": [], "updated_at": None}
    if PUBLISHED_CLIPS_FILE.exists():
        try:
            existing = json.loads(PUBLISHED_CLIPS_FILE.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("clips"), list):
                payload = existing
        except Exception:
            pass
    payload["clips"].append({
        "pexels_video_id":     pexels_video_id or "",
        "story_id":            story_id or "",
        "pexels_url":          pexels_url or "",
        "platform_video_id":   platform_video_id or "",
        "uploaded_at":         datetime.now(timezone.utc).isoformat(),
    })
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = PUBLISHED_CLIPS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(PUBLISHED_CLIPS_FILE)


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
    """Assemble the queue entry. Matches the shared queue shape so
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
        # YouTube Shorts discovery hashtags.
        # Carried on the queue so generate_shorts can drop them into the
        # caption without reaching back into ANIMAL_TOPICS.
        "discovery_hashtags": list(topic_cfg.get("discovery_hashtags") or []),
        # Pexels-specific extras — kept so a follow-up PR can later
        # bias `generate_shorts.acquire_broll_clips` to PREFER the
        # exact clip that informed the script.
        "pexels_video_id":     _pexels_id_from_clip(pexels_clip),
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
    log.info("🐾 Wild Brief — animal queue refresh %s",
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
    # Dedup keys come from three places, unioned into a single set:
    #   1. Queue ids — anything still on the queue (pending or recently
    #      consumed, before prune).
    #   2. Published clips ledger — the permanent record of clips we
    #      already shipped to YouTube. This is the line of defence
    #      against re-uploading the same Pexels clip after the queue
    #      pruned its consumed entry weeks later.
    #   3. The pexels_video_id of every queue entry — same defense,
    #      but for entries that have it (added in commit 2026-05-19).
    queue_ids: set[str] = {s.get("id") for s in queue["stories"] if s.get("id")}
    queue_pexels_ids: set[str] = {
        str(s.get("pexels_video_id", "")) for s in queue["stories"]
        if s.get("pexels_video_id")
    }
    published_keys = load_published_clip_keys()
    dedupe_keys: set[str] = queue_ids | queue_pexels_ids | published_keys
    log.info("🧮 Dedup keyset: %d queue ids + %d published clips = %d total",
             len(queue_ids), len(published_keys), len(dedupe_keys))
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
            pid = _pexels_id_from_clip(clip)
            if sid in dedupe_keys or (pid and pid in dedupe_keys):
                continue
            subject = clip.title or queries[0]
            context = topic_cfg.get("description_prefix", "an animal clip")
            ai_out = _ai_enhance_animal(subject, context)
            if not ai_out:
                log.debug("  ⏭  AI enrichment failed for %s", subject[:60])
                continue
            story = _build_story(subject, topic_key, topic_cfg, clip, ai_out)
            new_entries.append(story)
            dedupe_keys.add(story["id"])
            if pid:
                dedupe_keys.add(pid)

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

    # Keep the AI disk cache bounded — same chore fetch_animals.py does.
    try:
        ai_cache_prune(ttl_days=30)
    except Exception as exc:
        log.debug("ai_cache prune skipped: %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
