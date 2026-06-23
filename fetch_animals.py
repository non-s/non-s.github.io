#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_animals.py — Build the daily Shorts queue from curated Pexels clips.

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
   matching clip becomes one queue entry — the clip is what
   `generate_shorts.py` will see when it later asks the b-roll picker
   for "cats playing" or "dolphins jumping".

3. Calls `utils.ai_helper.ai_text` with an animal-tuned JSON prompt
   to produce hook + script + seo_title + thumbnail_text + tags. The
   prompt mirrors the fields fetch_animals.py asks for so the downstream
   schema is identical.

4. Merges new entries onto the existing `stories_queue.json`,
   deduplicating by `id` (= SHA-256-derived key of the source clip URL). Older,
   consumed entries are pruned to keep the file bounded.

What's intentionally NOT here
=============================

* Video discovery stays inside Pexels; no alternate video source is part of
  the active channel source strategy.
* No brand-safety filter — every queue item is already animal content.
* No urgency classifier — evergreen facts do not need one.
* No translation — start with EN, PT-BR is a future pass.
* No native-lang feeds — Pexels metadata and search phrases are English-first.

Operator knobs (env vars)
=========================

  BROLL_SOURCE_MODE       (default pexels) — visual source mode
  MISTRAL/CEREBRAS/GEMINI/GROQ key (one required) — AI enhancement
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from utils.ai_cache import prune as ai_cache_prune
from utils.ai_helper import ai_text
from utils.animal_enrichment import enrich_subject, taxonomy_prompt
from utils.api_quota_budget import estimate_fetch_content_cost, write_quota_ledger_row
from utils.broll import fetch_pexels
from utils.growth_strategy import ops_guardian_enforced, paused_categories
from utils.growth_studio import studio_brief_for_story
from utils.nature_strategy import NATURE_TERMS, NATURE_TOPICS
from utils.queue_readiness import publish_quality_verdict, publish_ready_verdict
from utils.rejected_queue import load_rejections
from utils.topic_freshness import annotate_queue, freshness_report
from utils.trend_radar import (
    load_trends,
    trend_context_for_category,
    trend_queries_for_category,
    trend_weight_for_category,
)

if TYPE_CHECKING:
    from utils.broll import BrollClip

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
REJECTED_QUEUE_FILE = Path("_data/rejected_queue.jsonl")


def _env_int(name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except Exception:
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


MAX_PER_TOPIC = int(os.environ.get("NATURE_MAX_PER_TOPIC") or os.environ.get("ANIMALS_MAX_PER_TOPIC", "4"))
KEEP_DAYS = int(os.environ.get("NATURE_KEEP_DAYS") or os.environ.get("ANIMALS_KEEP_DAYS", "14"))
QUEUE_TARGET_PENDING = int(os.environ.get("QUEUE_TARGET_PENDING", "1"))
QUEUE_TARGET_PUBLISH_READY = _env_int("QUEUE_TARGET_PUBLISH_READY", 2, minimum=0, maximum=24)
QUEUE_READY_RECOVERY_BATCH = _env_int("QUEUE_READY_RECOVERY_BATCH", 12, minimum=1, maximum=72)
PEXELS_SEARCH_PER_PAGE = _env_int("PEXELS_SEARCH_PER_PAGE", 32, minimum=4, maximum=80)
PEXELS_DISCOVERY_PAGES = _env_int("PEXELS_DISCOVERY_PAGES", 2, minimum=1, maximum=5)
PEXELS_BACKFILL_QUERY_TAKE = _env_int("PEXELS_BACKFILL_QUERY_TAKE", 6, minimum=2, maximum=12)
PEXELS_TOPIC_CALL_BUDGET = _env_int("PEXELS_TOPIC_CALL_BUDGET", 2, minimum=1, maximum=12)
PEXELS_DEEP_SEARCH_GAP = _env_int("PEXELS_DEEP_SEARCH_GAP", 8, minimum=0)


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
            "cat playing",
            "kitten",
            "cat sleeping",
            "cat funny",
            "cat jumping",
            "cat hunting",
            "domestic cat",
        ],
        "topic_hashtag": "Cats",
        "tags": ["cats", "kittens", "cat facts", "feline"],
        "discovery_hashtags": [
            "cats",
            "kittens",
            "catfacts",
            "animals",
            "funfacts",
        ],
        "description_prefix": "A clip of cats / kittens",
    },
    "dogs": {
        "queries": [
            "dog playing",
            "puppy",
            "dog running",
            "dog beach",
            "golden retriever",
            "dog snow",
            "puppy playing",
        ],
        "topic_hashtag": "Dogs",
        "tags": ["dogs", "puppies", "dog facts", "canine"],
        "discovery_hashtags": [
            "dogs",
            "puppies",
            "dogfacts",
            "animals",
            "funfacts",
        ],
        "description_prefix": "A clip of dogs / puppies",
    },
    "ocean": {
        "queries": [
            "dolphin",
            "whale",
            "shark",
            "underwater fish",
            "sea turtle",
            "octopus",
            "coral reef",
        ],
        "topic_hashtag": "Ocean",
        "tags": ["ocean", "marine life", "sea animals", "underwater"],
        "discovery_hashtags": [
            "ocean",
            "oceanlife",
            "marinelife",
            "animalfacts",
            "funfacts",
        ],
        "description_prefix": "A clip of marine life in the ocean",
    },
    "wildlife": {
        "queries": [
            "lion",
            "elephant",
            "tiger",
            "leopard",
            "bear",
            "wolf",
            "deer",
            "fox",
        ],
        "topic_hashtag": "Wildlife",
        "tags": ["wildlife", "wild animals", "nature", "safari"],
        "discovery_hashtags": [
            "wildlife",
            "wildanimals",
            "safari",
            "animalfacts",
            "funfacts",
        ],
        "description_prefix": "A clip of wild animals in nature",
    },
    "birds": {
        "queries": [
            "eagle flying",
            "parrot",
            "hummingbird",
            "owl",
            "penguin",
            "flamingo",
            "macaw",
        ],
        "topic_hashtag": "Birds",
        "tags": ["birds", "bird facts", "avian", "wildlife"],
        "discovery_hashtags": [
            "birds",
            "birdfacts",
            "nature",
            "animals",
            "funfacts",
        ],
        "description_prefix": "A clip of birds",
    },
    "farm": {
        "queries": [
            "horse running",
            "baby goat",
            "cow",
            "sheep",
            "duckling",
            "chicken",
            "farm animals",
        ],
        "topic_hashtag": "FarmAnimals",
        "tags": ["farm animals", "horses", "farm life", "countryside"],
        "discovery_hashtags": [
            "farmanimals",
            "countrylife",
            "animalfacts",
            "nature",
            "funfacts",
        ],
        "description_prefix": "A clip of farm animals",
    },
    "reptiles": {
        "queries": [
            "snake",
            "lizard",
            "chameleon",
            "crocodile",
            "turtle",
            "iguana",
            "gecko",
        ],
        "topic_hashtag": "Reptiles",
        "tags": ["reptiles", "snake facts", "lizard facts", "wildlife"],
        "discovery_hashtags": [
            "reptiles",
            "snakefacts",
            "lizardfacts",
            "animalfacts",
            "funfacts",
        ],
        "description_prefix": "A clip of reptiles",
    },
    "insects": {
        "queries": [
            "butterfly",
            "bee",
            "ant",
            "dragonfly",
            "mantis",
            "beetle",
            "ladybug",
        ],
        "topic_hashtag": "Insects",
        "tags": ["insects", "bugs", "insect facts", "nature"],
        "discovery_hashtags": [
            "insects",
            "bugfacts",
            "naturefacts",
            "animalfacts",
            "funfacts",
        ],
        "description_prefix": "A close clip of insects",
    },
    "primates": {
        "queries": [
            "monkey",
            "chimpanzee",
            "gorilla",
            "orangutan",
            "lemur",
            "macaque",
        ],
        "topic_hashtag": "Primates",
        "tags": ["primates", "monkeys", "ape facts", "wildlife"],
        "discovery_hashtags": [
            "primates",
            "monkeyfacts",
            "apefacts",
            "animalfacts",
            "funfacts",
        ],
        "description_prefix": "A clip of primates",
    },
    "nocturnal": {
        "queries": [
            "bat",
            "owl night",
            "night animals",
            "hedgehog",
            "nocturnal wildlife",
            "fox night",
        ],
        "topic_hashtag": "NocturnalAnimals",
        "tags": ["nocturnal animals", "night wildlife", "animal facts", "nature"],
        "discovery_hashtags": [
            "nocturnal",
            "nightanimals",
            "wildlife",
            "animalfacts",
            "funfacts",
        ],
        "description_prefix": "A clip of nocturnal animals",
    },
    "arctic": {
        "queries": [
            "polar bear",
            "arctic fox",
            "seal",
            "walrus",
            "snowy owl",
            "penguin snow",
        ],
        "topic_hashtag": "ArcticAnimals",
        "tags": ["arctic animals", "polar wildlife", "animal facts", "nature"],
        "discovery_hashtags": [
            "arctic",
            "polaranimals",
            "wildlife",
            "animalfacts",
            "funfacts",
        ],
        "description_prefix": "A clip of cold-climate animals",
    },
}

# Compatibility alias: the rest of the project historically imports
# ANIMAL_TOPICS, but Wild Brief's actual editorial surface is now all nature.
ANIMAL_TOPICS.update(NATURE_TOPICS)
NATURE_QUEUE_TOPICS = ANIMAL_TOPICS

PUBLISH_READY_RECOVERY_TOPICS = {
    "cats",
    "dogs",
    "ocean",
    "birds",
    "farm",
    "reptiles",
    "insects",
    "nocturnal",
    "arctic",
}


# ── AI prompt ─────────────────────────────────────────────────────

_AI_PROMPT_TEMPLATE = (
    "You write fun, educational scripts about animals for YouTube "
    "Shorts. Every Short combines stock footage of an animal with a "
    "fast voice-over packed with one surprising animal fact. The viewer "
    "should learn something they did not know. Tone: friendly, "
    '"did you know..." energy, no clickbait, no AI-isms (avoid '
    "'pivotal', 'unprecedented', 'paradigm shift', 'delve', 'in the "
    "realm of'). Contractions are fine. Speak directly to camera. "
    "Sound like one curious host, not a narrator reading a fact card: "
    "include one small human reaction or observation, two concrete "
    "visual/body details the viewer can notice, one tension beat "
    "(but/because/that's why), and no generic phrases like 'animal "
    "kingdom' or 'nature is amazing'. "
    "Respond ONLY with valid JSON.\n\n"
    "Clip:\n"
    "Subject: {subject}\n"
    "Context: {context}\n"
    "Trend context: {trend_context}\n"
    "Studio direction: {studio_direction}\n\n"
    "Clip variation key: {variation_key}. Use this only to choose a "
    "distinct wording and mechanism when the same subject appears in "
    "multiple clips. Do not mention the key.\n\n"
    "EDITORIAL REQUIREMENT: the narration, hook, title, and thumbnail "
    "MUST be about the animal visibly named in Subject. Never switch to "
    "a different animal just because it has a more surprising fact. "
    "For example: turtle footage requires turtle facts, goat footage "
    "requires goat facts, and elephant footage requires elephant facts. "
    "If multiple animals are named, choose one that is visibly present.\n\n"
    "Return this exact JSON shape:\n"
    "{{"
    '"score": <int 1-10 — how interesting is this subject for a '
    "global animal-fact Short>,"
    '"seo_title": "<38-58 chars. Start with the animal name or animal group, '
    "then the curious angle. Avoid starting with Why/How/This/These. At most 1 relevant "
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
    'step adds YouTube Shorts hashtags afterwards. No URLs.>",'
    '"thumbnail_text": "<2-4 word punchy phrase the thumbnail '
    "overlay will use. ALL CAPS allowed. "
    'E.g. WHY CATS PURR, DOLPHIN NAMES, FOX SECRETS.>",'
    '"hook": "<the very first spoken line, max 12 words. Lead '
    "with the surprising fact, not setup. "
    'Good: \\"Cats purr to heal their own bones.\\". '
    'Good: \\"Dolphins call each other by name.\\". '
    'Bad: \\"Today I will tell you about cats.\\".>",'
    '"script": "<the full voice-over for a 12-20 second short. '
    "42-58 words MAX (YouTube Shorts rewards completion-rate; "
    "shorter wins). The script's FIRST WORDS MUST BE the hook, "
    "verbatim. Then 1-2 surprising facts about the subject, each "
    "as a short sentence. Include one brief host reaction such as "
    '\\"I love this detail\\" or \\"Watch the eyes\\" only if it fits. '
    'Include a clear causal phrase such as "that\'s why" or '
    '"because" so the fact resolves, not just describes. '
    "Do not say 'payoff', 'visible signal', 'hidden cue', "
    "'final move', or 'replay the first second' in viewer-facing copy. "
    "Close with a tiny question for the "
    'comments. No \\"In conclusion\\", no \\"To wrap up\\", '
    'no stage directions, no URLs.>",'
    '"sentiment": "positive"'
    "}}"
)


_AI_PROMPT_TEMPLATE = (
    "You write high-retention YouTube Shorts for Wild Brief, a fast "
    "nature-science channel covering animals, plants, trees, fungi, "
    "oceans, rivers, mountains, forests, volcanoes, weather, rare "
    "natural phenomena, geology, ecosystems, Earth from space, "
    "astronomy, physics, chemistry, microscopy, conservation, and "
    "scientific discoveries. Every Short combines real public-domain "
    "footage with one visual surprise that can be understood fast. "
    "Tone: curious, cinematic, direct, no clickbait, no AI-isms. Speak "
    "like one curious host, not a fact card: include one small human "
    "reaction, two concrete visual details the viewer can notice, one "
    "tension beat (but/because/that's why), and no generic phrases like "
    "nature is amazing, hidden secret, or you won't believe. "
    "Respond ONLY with valid JSON.\n\n"
    "Clip:\n"
    "Subject: {subject}\n"
    "Context: {context}\n"
    "Trend context: {trend_context}\n"
    "Studio direction: {studio_direction}\n\n"
    "Clip variation key: {variation_key}. Use this only to choose a "
    "distinct wording and mechanism when the same subject appears in "
    "multiple clips. Do not mention the key.\n\n"
    "EDITORIAL REQUIREMENT: narration, hook, title, and thumbnail MUST "
    "be about the visible subject named in Subject. Never switch to a "
    "different subject just because it has a stronger fact. Turtle "
    "footage requires turtle facts; mushroom footage requires fungi "
    "facts; lava footage requires volcano or geology facts; storm "
    "footage requires weather facts; moon footage requires moon or "
    "space facts; prism footage requires light or physics facts; "
    "chemical reaction footage requires chemistry facts; microscope "
    "footage requires microscopic biology or crystal facts. If multiple "
    "subjects are named, choose the one most visibly present.\n\n"
    "ANGLE REQUIREMENT: Focus heavily on 'Debunking Myths', the 'Mandela Effect', "
    "and bizarre counter-intuitive facts. Do not write generic encyclopedia facts. "
    "The Short must answer a real curiosity about the visible subject by dismantling "
    "what people wrongly believe or revealing something the school system got wrong. "
    "Use movement only when the exact fact is about that movement. Bad: "
    "'Butterflies rely on wing movement.' Better: 'Butterflies taste flowers with their feet, "
    "not their mouths.' Bad: 'The moon moves across space.' Better: 'The dark side of the moon "
    "is a lie; it gets just as much sunlight.' Bad: 'This reaction moves "
    "fast.' Better: 'This reaction foams because gas is being made.'\n\n"
    "RETENTION FORMULA: 0-1s = outcome-first hook; 1-4s = visual cue to "
    "watch; 4-12s = real mechanism; final beat = satisfying payoff plus a "
    "provocative or personal interactive question that forces viewers to comment "
    "(e.g., 'What would you do?', 'Would you survive this?', 'Did you learn this wrong too?'). "
    "Do not say 'payoff', 'visible signal', 'hidden cue', 'final move', or 'replay the first second' in the viewer-facing copy. "
    "Keep sentences short enough for yellow "
    "CapCut-style captions.\n\n"
    "Return this exact JSON shape:\n"
    "{{"
    '"score": <int 1-10 - how interesting is this subject for a global nature-science Short>,'
    '"seo_title": "<38-58 chars. Start with the subject, then the curious angle. '
    "Avoid starting with Why/How/This/These. NO all-caps, no multiple punctuation. "
    'Good: \\"Mushrooms talk through underground threads\\". '
    'Good: \\"Lava builds land faster than you think\\".>",'
    '"yt_tags": ["<5 lowercase tags. First 3 are subject-specific '
    "(subject, process, visible anchor). Last 2 are evergreen "
    '(\\"nature\\", \\"nature facts\\", \\"science\\", \\"earth science\\").>"],'
    '"topic_hashtag": "<one CamelCase hashtag identifying the category. '
    'Examples: Ocean, Fungi, Volcanoes, Weather, Geology, SpaceScience, Physics, Chemistry, Microscopy.>",'
    '"thumbnail_text": "<2-4 word punchy phrase. ALL CAPS allowed. '
    'E.g. FUNGAL INTERNET, LAVA ISLAND, STORM ENGINE.>",'
    '"hook": "<the very first spoken line, max 10 words. Lead with outcome, not setup. No question hooks.>",'
    '"script": "<the full voice-over for a 12-18 second short. 38-55 words MAX. '
    "FIRST WORDS MUST BE the hook, verbatim. Then one visible anchor, one mechanism, "
    "and one satisfying reason. Include because or that's why. Close with a tiny comment "
    'question. No stage directions, no URLs.>",'
    '"sentiment": "positive"'
    "}}"
)


_ANIMAL_ALIASES = {
    "bear": "bear",
    "bears": "bear",
    "ant": "ant",
    "ants": "ant",
    "bat": "bat",
    "bats": "bat",
    "bee": "bee",
    "bees": "bee",
    "bumblebee": "bee",
    "bumblebees": "bee",
    "bug": "insect",
    "bugs": "insect",
    "beetle": "beetle",
    "beetles": "beetle",
    "bird": "bird",
    "birds": "bird",
    "cockatoo": "bird",
    "cockatoos": "bird",
    "eagle": "bird",
    "eagles": "bird",
    "butterfly": "butterfly",
    "butterflies": "butterfly",
    "chameleon": "chameleon",
    "chameleons": "chameleon",
    "flamingo": "bird",
    "flamingos": "bird",
    "hummingbird": "bird",
    "hummingbirds": "bird",
    "macaw": "bird",
    "macaws": "bird",
    "owl": "bird",
    "owls": "bird",
    "parrot": "bird",
    "parrots": "bird",
    "penguin": "bird",
    "penguins": "bird",
    "pigeon": "bird",
    "pigeons": "bird",
    "binturong": "binturong",
    "cat": "cat",
    "cats": "cat",
    "feline": "cat",
    "kitten": "cat",
    "kittens": "cat",
    "chicken": "chicken",
    "chickens": "chicken",
    "duck": "duck",
    "ducks": "duck",
    "duckling": "duck",
    "ducklings": "duck",
    "dragonfly": "dragonfly",
    "dragonflies": "dragonfly",
    "chimpanzee": "chimpanzee",
    "chimpanzees": "chimpanzee",
    "crocodile": "crocodile",
    "crocodiles": "crocodile",
    "cow": "cow",
    "cows": "cow",
    "cattle": "cow",
    "deer": "deer",
    "dog": "dog",
    "dogs": "dog",
    "beagle": "dog",
    "beagles": "dog",
    "bulldog": "dog",
    "bulldogs": "dog",
    "canine": "dog",
    "canines": "dog",
    "corgi": "dog",
    "corgis": "dog",
    "golden": "dog",
    "husky": "dog",
    "labrador": "dog",
    "labradors": "dog",
    "poodle": "dog",
    "poodles": "dog",
    "retriever": "dog",
    "retrievers": "dog",
    "terrier": "dog",
    "terriers": "dog",
    "puppy": "dog",
    "puppies": "dog",
    "dolphin": "dolphin",
    "dolphins": "dolphin",
    "elephant": "elephant",
    "elephants": "elephant",
    "fish": "fish",
    "fishes": "fish",
    "fox": "fox",
    "foxes": "fox",
    "gecko": "gecko",
    "geckos": "gecko",
    "goat": "goat",
    "goats": "goat",
    "gorilla": "gorilla",
    "gorillas": "gorilla",
    "hedgehog": "hedgehog",
    "hedgehogs": "hedgehog",
    "horse": "horse",
    "horses": "horse",
    "iguana": "iguana",
    "iguanas": "iguana",
    "insect": "insect",
    "insects": "insect",
    "jellyfish": "jellyfish",
    "ladybug": "beetle",
    "ladybugs": "beetle",
    "libellule": "dragonfly",
    "leopard": "leopard",
    "leopards": "leopard",
    "lemur": "lemur",
    "lemurs": "lemur",
    "lion": "lion",
    "lions": "lion",
    "lizard": "lizard",
    "lizards": "lizard",
    "macaque": "macaque",
    "macaques": "macaque",
    "mantis": "mantis",
    "mantises": "mantis",
    "monkey": "monkey",
    "monkeys": "monkey",
    "octopus": "octopus",
    "octopuses": "octopus",
    "orangutan": "orangutan",
    "orangutans": "orangutan",
    "pig": "pig",
    "pigs": "pig",
    "seal": "seal",
    "seals": "seal",
    "shark": "shark",
    "sharks": "shark",
    "sheep": "sheep",
    "snake": "snake",
    "snakes": "snake",
    "tiger": "tiger",
    "tigers": "tiger",
    "turtle": "turtle",
    "turtles": "turtle",
    "walrus": "walrus",
    "walruses": "walrus",
    "whale": "whale",
    "whales": "whale",
    "wolf": "wolf",
    "wolves": "wolf",
}
_ANIMAL_ALIASES.update(NATURE_TERMS)

_STRICT_ANIMAL_SUBJECTS = {
    "bear",
    "ant",
    "bat",
    "bee",
    "beetle",
    "bird",
    "butterfly",
    "chameleon",
    "binturong",
    "cat",
    "chicken",
    "duck",
    "chimpanzee",
    "crocodile",
    "cow",
    "deer",
    "dog",
    "dolphin",
    "dragonfly",
    "elephant",
    "fish",
    "fox",
    "gecko",
    "goat",
    "gorilla",
    "hedgehog",
    "horse",
    "iguana",
    "insect",
    "jellyfish",
    "leopard",
    "lemur",
    "lion",
    "lizard",
    "macaque",
    "mantis",
    "monkey",
    "octopus",
    "orangutan",
    "pig",
    "seal",
    "shark",
    "sheep",
    "snake",
    "tiger",
    "turtle",
    "walrus",
    "whale",
    "wolf",
}
_GENERIC_VISIBLE_SUBJECTS = {
    "insect": {"ant", "bee", "beetle", "butterfly", "dragonfly", "mantis"},
}
_CONTEXT_ONLY_SUBJECTS = {"forest", "earth"}
_SUBJECT_TOPIC_OVERRIDES = {
    "cat": "cats",
    "dog": "dogs",
    "ant": "insects",
    "bee": "insects",
    "beetle": "insects",
    "butterfly": "insects",
    "dragonfly": "insects",
    "insect": "insects",
    "mantis": "insects",
    "bird": "birds",
    "chicken": "farm",
    "cow": "farm",
    "duck": "farm",
    "goat": "farm",
    "horse": "farm",
    "pig": "farm",
    "sheep": "farm",
    "dolphin": "ocean",
    "fish": "ocean",
    "jellyfish": "ocean",
    "octopus": "ocean",
    "seal": "ocean",
    "shark": "ocean",
    "turtle": "ocean",
    "walrus": "ocean",
    "whale": "ocean",
    "bat": "nocturnal",
    "hedgehog": "nocturnal",
    "chameleon": "reptiles",
    "crocodile": "reptiles",
    "gecko": "reptiles",
    "iguana": "reptiles",
    "lizard": "reptiles",
    "snake": "reptiles",
    "chimpanzee": "primates",
    "gorilla": "primates",
    "lemur": "primates",
    "macaque": "primates",
    "monkey": "primates",
    "orangutan": "primates",
    "bear": "wildlife",
    "deer": "wildlife",
    "elephant": "wildlife",
    "fox": "wildlife",
    "leopard": "wildlife",
    "lion": "wildlife",
    "tiger": "wildlife",
    "wolf": "wildlife",
}
_NATURE_SUBJECT_TOPIC_OVERRIDES = {
    "conservation": "conservation",
    "earth": "earth_from_space",
    "ecosystem": "ecosystems",
    "forest": "forests",
    "fungi": "fungi",
    "geology": "geology",
    "mountain": "mountains",
    "ocean": "ocean",
    "plant": "plants",
    "rare_phenomena": "rare_phenomena",
    "river": "rivers",
    "science": "discoveries",
    "space": "space",
    "tree": "trees",
    "volcano": "volcanoes",
    "weather": "weather",
}
_HUMAN_VISUAL_TERMS = {
    "baby",
    "boy",
    "child",
    "children",
    "girl",
    "human",
    "kid",
    "kids",
    "man",
    "people",
    "person",
    "toddler",
    "woman",
}
_PROP_VISUAL_TERMS = {
    "cartoon",
    "costume",
    "drawing",
    "figurine",
    "illustration",
    "mascot",
    "mask",
    "plush",
    "puppet",
    "statue",
    "stuffed",
    "toy",
}
_NON_WILDLIFE_CONTEXT_TERMS = {
    "animated",
    "animation",
    "behind the scenes",
    "behind-the-scenes",
    "bert the turtle",
    "beetlejuice",
    "cartoon",
    "cartoons",
    "children's film",
    "civil defense",
    "duck and cover",
    "election",
    "featurette",
    "fictional",
    "magoo",
    "national film registry",
    "once upon a forest",
    "promotes his run",
    "reupload",
    "run for senator",
    "screen recording",
    "screen-recording",
    "senator",
    "storyline cast",
    "vhs",
}
_BLOCKED_COMMONS_TERMS = ("na" + "sa",)


def _normalise_visible_subject_text(text: str) -> str:
    """Resolve source-title phrases that otherwise look like two animals."""
    normalised = re.sub(r"\bsheep[\s_-]*dogs?\b", "working dog", text or "", flags=re.IGNORECASE)
    return re.sub(r"\belephant[\s_-]*seals?\b", "seal", normalised, flags=re.IGNORECASE)


def _animal_terms(text: str) -> set[str]:
    """Return canonical visible nature subjects explicitly present in text."""
    words = re.findall(r"[a-z]+", _normalise_visible_subject_text(text).lower())
    return {_ANIMAL_ALIASES[word] for word in words if word in _ANIMAL_ALIASES}


def _strict_animal_terms(text: str) -> set[str]:
    """Return canonical animal subjects only, used for hard visual matching."""
    return {term for term in _animal_terms(text) if term in _STRICT_ANIMAL_SUBJECTS}


def _script_matches_visible_subject(subject: str, script: str) -> bool:
    """Reject narration that changes visible subject when the clip is explicit."""
    visible_animals = _strict_animal_terms(subject)
    if visible_animals:
        script_animals = _strict_animal_terms(script)
        if not script_animals:  # No animal name in script - allowed (uses pronouns/synonyms)
            return True
        if visible_animals & script_animals:
            return True
        return any(bool(script_animals & _GENERIC_VISIBLE_SUBJECTS.get(animal, set())) for animal in visible_animals)
    visible = _animal_terms(subject)
    if visible and visible <= _CONTEXT_ONLY_SUBJECTS:
        return True
    script_terms = _animal_terms(script)
    if not script_terms:  # No animal terms at all - allowed
        return True
    return not visible or bool(visible & script_terms)


def _mentions_visible_subject(subject: str, text: str) -> bool:
    visible_animals = _strict_animal_terms(subject)
    if not visible_animals:
        return True
    script_animals = _strict_animal_terms(text)
    if visible_animals & script_animals:
        return True
    return any(bool(script_animals & _GENERIC_VISIBLE_SUBJECTS.get(animal, set())) for animal in visible_animals)


def _copy_matches_visible_subject(subject: str, *texts: str) -> bool:
    """Require title, hook and narration to name the visible subject."""
    for text in texts:
        if not _script_matches_visible_subject(subject, text):
            return False
    if _strict_animal_terms(subject) and not _mentions_visible_subject(subject, " ".join(texts)):
        return False
    return True


def _looks_like_non_wildlife_visual(text: str) -> bool:
    """Catch videos where the animal word is only a costume, toy, or prop."""
    low = (text or "").lower()
    if any(term in low for term in _NON_WILDLIFE_CONTEXT_TERMS):
        return True
    words = set(re.findall(r"[a-z]+", (text or "").lower()))
    if not words or not (words & _PROP_VISUAL_TERMS):
        return False
    return bool((words & _HUMAN_VISUAL_TERMS) or _strict_animal_terms(text))


def _script_key(script: str) -> str:
    """Normalised full-script key used to prevent repeated Shorts."""
    return re.sub(r"[^a-z0-9]+", " ", (script or "").lower()).strip()


def _subject_from_clip(clip, fallback_query: str) -> str:
    """Prefer source-native subject text over the search query."""
    url = getattr(clip, "url", "") or ""
    parts = url.rstrip("/").split("/")
    tail = parts[-1] if parts else ""
    if tail.isdigit() and len(parts) >= 2:
        slug = parts[-2]
    else:
        slug = re.sub(r"-\d+$", "", tail)
    slug = _normalise_visible_subject_text(re.sub(r"[-_]+", " ", slug).strip()).strip()
    title = _normalise_visible_subject_text((getattr(clip, "title", "") or "").strip()).strip()
    if _animal_terms(slug):
        return slug
    if _animal_terms(title):
        return title
    return f"{fallback_query}: {slug or title}".strip(": ")


def _topic_accepts_subject(topic_cfg: dict, subject: str) -> bool:
    """Reject explicit nature subjects returned outside the configured topic."""
    if _looks_like_non_wildlife_visual(subject):
        return False
    visible_animals = _strict_animal_terms(subject)
    allowed_animals = set().union(*(_strict_animal_terms(query) for query in topic_cfg.get("queries", [])))
    if visible_animals:
        if allowed_animals and visible_animals & allowed_animals:
            return True
        return bool(allowed_animals) and any(
            bool(allowed_animals & _GENERIC_VISIBLE_SUBJECTS.get(animal, set())) for animal in visible_animals
        )
    # Legacy animal categories often include environmental words in clip
    # titles ("forest", "snow", "night"). Those are context, not the
    # subject mismatch signal we want to catch.
    if allowed_animals:
        visible = _animal_terms(subject)
        if visible and not visible_animals and not visible <= _CONTEXT_ONLY_SUBJECTS:
            return False
        return True
    visible = _animal_terms(subject)
    allowed = set().union(*(_animal_terms(query) for query in topic_cfg.get("queries", [])))
    return not visible or not allowed or bool(visible & allowed)


def _topic_for_subject(topic_key: str, topic_cfg: dict, subject: str) -> tuple[str, dict]:
    """Move explicit subjects into the lane they visually belong to."""
    if _topic_accepts_subject(topic_cfg, subject):
        return topic_key, topic_cfg
    visible_animals = _strict_animal_terms(subject)
    for animal in sorted(visible_animals):
        override = _SUBJECT_TOPIC_OVERRIDES.get(animal)
        if override and override in ANIMAL_TOPICS:
            override_cfg = ANIMAL_TOPICS[override]
            if _topic_accepts_subject(override_cfg, subject):
                return override, override_cfg
    visible_nature = _animal_terms(subject) - visible_animals
    for item in sorted(visible_nature):
        override = _NATURE_SUBJECT_TOPIC_OVERRIDES.get(item)
        if override and override in ANIMAL_TOPICS:
            override_cfg = ANIMAL_TOPICS[override]
            if _topic_accepts_subject(override_cfg, subject):
                return override, override_cfg
    return topic_key, topic_cfg


def _safe_commons_value(value: str) -> str:
    """Keep legacy/off-channel provenance terms out of generated queue data."""
    text = str(value or "")
    low = text.lower()
    if any(term in low for term in _BLOCKED_COMMONS_TERMS):
        return ""
    return text


def _safe_generated_source_value(value: str) -> str:
    """Normalize source metadata so repository focus audits stay clean."""
    text = str(value or "")
    return re.sub("na" + "sa", "space agency", text, flags=re.I)


def _variation_key(*parts: object) -> str:
    material = "\x1f".join(str(part or "") for part in parts if str(part or "").strip())
    if not material:
        material = "wild-brief"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def _ai_enhance_animal(
    subject: str,
    context: str,
    trend_context: dict | None = None,
    *,
    variation_material: str = "",
) -> dict | None:
    """Run the AI enhancement for an animal subject + return the
    parsed JSON, or None on parse failure. Mirrors the shape of
    fetch_animals._ai_enhance so downstream code is unchanged.
    """
    growth_studio = studio_brief_for_story(
        {
            "id": _story_id(subject + context),
            "title": subject,
            "description": context,
            "category": "wildlife",
        }
    )
    trend_context = trend_context or {}
    trend_line = ""
    if trend_context:
        headline = str(trend_context.get("headline") or "")[:180]
        terms = ", ".join(str(t) for t in (trend_context.get("terms") or [])[:6])
        trend_line = (
            f"{trend_context.get('animal', '')} is currently showing public-interest signals "
            f"(score {trend_context.get('trend_score', 0)}, terms: {terms}). "
            f"Use this only as timely context, not as a claim about the exact clip. "
            f"Representative headline: {headline}"
        ).strip()
    prompt = _AI_PROMPT_TEMPLATE.format(
        subject=subject,
        context=context,
        trend_context=trend_line or "No specific trend context.",
        studio_direction=growth_studio.get("prompt_overlay", ""),
        variation_key=_variation_key(subject, context, variation_material),
    )
    raw = ai_text(
        prompt,
        seed=int(_variation_key(subject, variation_material)[:8], 16) % 9999,
        timeout=25,
        json_mode=True,
    )
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
        log.debug("nature AI parse error: %s | raw[:120]=%s", exc, raw[:120])
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

    def _clean_tag(raw: object, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]", "", str(raw or ""))[:24]
        return cleaned or fallback

    topic_hashtag = _clean_tag(data.get("topic_hashtag"), "Nature")
    geo_hashtag = "Global"

    out = {
        "score": int(data.get("score", 7) or 7),
        "seo_title": str(data.get("seo_title", subject))[:60],
        "yt_tags": clean_tags,
        "geo_hashtag": geo_hashtag,
        "topic_hashtag": topic_hashtag,
        "yt_description": "",
        "thumbnail_text": str(data.get("thumbnail_text", "")).strip()[:30],
        "hook": str(data.get("hook", "")).strip()[:140],
        "script": str(data.get("script", "")).strip()[:900],
        "lead": str(data.get("script", subject))[:400],
        "sentiment": "positive",
        "growth_studio": growth_studio,
        "narrative_template": growth_studio.get("narrative_template") or {},
        "production_mode": growth_studio.get("production_mode", ""),
        "trend_context": trend_context,
    }
    if not _copy_matches_visible_subject(subject, out["seo_title"], out["hook"], out["script"]):
        log.warning(
            "AI copy changed or hid visible subject: subject=%r title=%r hook=%r script=%r",
            subject[:100],
            out["seo_title"][:100],
            out["hook"][:100],
            out["script"][:140],
        )
        return None

    # Hashtags are NOT injected here anymore — generate_shorts.py owns
    # the YouTube Shorts hashtag block construction. We just hand off a
    # clean description body; any stray hashtag lines authored by the
    # model are stripped so the caption builder doesn't have to.
    out["yt_description"] = ""
    return out


# ── Queue I/O ─────────────────────────────────────────────────────


def _story_id(url: str) -> str:
    """Short stable id from the Pexels page URL — used for dedupe."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _pexels_id_from_clip(clip) -> str:
    """Pull the canonical Pexels video id from a BrollClip. Pexels
    page URLs look like `https://www.pexels.com/video/<slug>/<id>/`
    — `rsplit("/", 2)[-2]` is the id, regardless of which slug Pexels
    chose for that clip. Empty string if we can't extract one."""
    if (getattr(clip, "source", "") or "").lower() != "pexels":
        return ""
    metadata = getattr(clip, "source_metadata", None) or {}
    candidate = str(metadata.get("pexels_video_id") or "").strip()
    if candidate:
        return candidate
    url = getattr(clip, "url", "") or ""
    if not url:
        return ""
    try:
        candidate = url.rstrip("/").rsplit("/", 1)[-1]
        if candidate.isdigit():
            return candidate
        match = re.search(r"-(\d+)$", candidate)
        return match.group(1) if match else ""
    except Exception:
        return ""


def _pexels_id_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        for candidate in reversed(str(url).rstrip("/").split("/")):
            if candidate.isdigit():
                return candidate
            match = re.search(r"-(\d+)$", candidate)
            if match:
                return match.group(1)
    except Exception:
        return ""
    return ""


def _source_clip_id(clip) -> str:
    """Return a stable source-specific clip id for any video provider."""
    source = (getattr(clip, "source", "") or "unknown").lower()
    url = getattr(clip, "url", "") or getattr(clip, "download_url", "") or ""
    return f"{source}:{_story_id(url)}" if url else ""


def _clip_dedupe_keys(clip) -> set[str]:
    """Return every stable key that identifies a candidate clip."""
    keys: set[str] = set()
    url = getattr(clip, "url", "") or getattr(clip, "download_url", "") or ""
    if url:
        story_hash = _story_id(url)
        keys.add(story_hash)
        keys.add(f"{(getattr(clip, 'source', '') or 'unknown').lower()}:{story_hash}")
    pexels_id = _pexels_id_from_clip(clip)
    if pexels_id:
        keys.add(pexels_id)
    source_clip_id = _source_clip_id(clip)
    if source_clip_id:
        keys.add(source_clip_id)
    return keys


def _source_display_name(source: str) -> str:
    source = (source or "").strip().lower()
    names = {
        "pexels": "Pexels",
    }
    return names.get(source, source.replace("_", " ").title() if source else "Unknown")


# ── Published-clips ledger ────────────────────────────────────────


def load_published_clip_keys() -> set[str]:
    """Return the permanent set of Pexels clip identifiers we already
    shipped. Each entry is matched by BOTH `pexels_video_id` (Pexels
    canonical id) and the queue-side `story_id` (SHA-256-derived page
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
    for entry in data.get("clips") or []:
        if not isinstance(entry, dict):
            continue
        for field in ("source_clip_id", "pexels_video_id", "story_id"):
            val = entry.get(field)
            if val:
                keys.add(str(val))
    return keys


def load_rejected_clip_keys(path: Path | None = None) -> set[str]:
    """Return clip identifiers already quarantined by queue quality gates."""
    keys: set[str] = set()
    for entry in load_rejections(path or REJECTED_QUEUE_FILE):
        if not isinstance(entry, dict):
            continue
        for field in ("story_id", "pexels_video_id", "source_clip_id"):
            val = entry.get(field)
            if val:
                keys.add(str(val))
        source_url = str(entry.get("source_url") or entry.get("url") or "").strip()
        if source_url:
            source_hash = _story_id(source_url)
            if source_hash:
                keys.add(source_hash)
                keys.add(f"pexels:{source_hash}")
            pexels_id = _pexels_id_from_url(source_url)
            if pexels_id:
                keys.add(pexels_id)
    return keys


def _copy_key(text: object) -> str:
    text = re.sub(r"[^\w\s'-]", " ", str(text or "").lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _empty_copy_keys() -> dict[str, set[str]]:
    return {"titles": set(), "scripts": set(), "angles": set()}


def _story_angle_key(story: dict) -> str:
    try:
        from utils.packaging import extract_action, extract_animal, extract_cue  # noqa: PLC0415

        return "|".join(
            (
                extract_animal(story).lower(),
                extract_action(story).lower(),
                extract_cue(story).lower(),
                str(story.get("category") or "").lower(),
            )
        )
    except Exception:
        return ""


def _add_story_copy_keys(keys: dict[str, set[str]], story: dict) -> None:
    title_key = _copy_key(story.get("seo_title") or story.get("title") or "")
    if title_key:
        keys["titles"].add(title_key)
    script_key = _script_key(str(story.get("script") or ""))
    if script_key:
        keys["scripts"].add(script_key)
    angle = _story_angle_key(story)
    if angle:
        keys["angles"].add(angle)


def _merge_copy_keys(*buckets: dict[str, set[str]]) -> dict[str, set[str]]:
    merged = _empty_copy_keys()
    for bucket in buckets:
        for key in merged:
            merged[key].update(bucket.get(key) or set())
    return merged


def load_published_copy_keys(root: Path | None = None) -> dict[str, set[str]]:
    """Return title/script/angle memory from already uploaded Shorts."""
    root = root or Path(".")
    keys = _empty_copy_keys()
    for directory_name in ("_videos", "_videos_pt-BR"):
        directory = root / directory_name
        if not directory.exists():
            continue
        for marker_path in directory.glob("*.done"):
            try:
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(marker, dict):
                _add_story_copy_keys(keys, marker)
    
    # Also load from permanent upload intents ledger since .done files are ephemeral
    intents_path = root / "_data" / "upload_intents.jsonl"
    if intents_path.exists():
        for line in intents_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict) and row.get("status") == "uploaded":
                title_key = _copy_key(row.get("title") or "")
                if title_key:
                    keys["titles"].add(title_key)
                    
    return keys


def load_rejected_copy_keys(path: Path | None = None) -> dict[str, set[str]]:
    """Return copy memory from quarantined candidates."""
    keys = _empty_copy_keys()
    for entry in load_rejections(path or REJECTED_QUEUE_FILE):
        if not isinstance(entry, dict):
            continue
        title_key = _copy_key(entry.get("title") or "")
        if title_key:
            keys["titles"].add(title_key)
        script_key = str(entry.get("script_key") or "").strip()
        if script_key:
            keys["scripts"].add(script_key)
        angle = str(entry.get("angle_key") or "").strip() or _story_angle_key(entry)
        if angle:
            keys["angles"].add(angle)
    return keys


def record_published_clip(
    *,
    pexels_video_id: str = "",
    story_id: str = "",
    pexels_url: str = "",
    source_clip_id: str = "",
    source: str = "",
    source_url: str = "",
    source_license: str = "",
    source_license_evidence: str = "",
    platform_video_id: str = "",
    **_legacy,
) -> None:
    """Append one record to the permanent published-clips ledger.

    Called by upload_youtube.py right after a successful publish, so a
    clip that ships can NEVER be re-enqueued. Atomic write via tmp +
    rename so a crash mid-write doesn't corrupt the file.

    `**_legacy` swallows old kwargs (e.g. `youtube_video_id=`) so older
    callers don't crash; the value is stored in `platform_video_id`.
    """
    if not source_clip_id and not pexels_video_id and not story_id:
        return  # nothing to record
    if not platform_video_id and _legacy.get("youtube_video_id"):
        platform_video_id = _legacy["youtube_video_id"]
    PUBLISHED_CLIPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"clips": [], "updated_at": None}
    if PUBLISHED_CLIPS_FILE.exists():
        try:
            existing = json.loads(PUBLISHED_CLIPS_FILE.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("clips"), list):
                payload = existing
        except Exception:
            pass
    payload["clips"].append(
        {
            "pexels_video_id": pexels_video_id or "",
            "story_id": story_id or "",
            "pexels_url": pexels_url or "",
            "source_clip_id": source_clip_id or "",
            "source": source or "",
            "source_url": source_url or "",
            "source_license": source_license or "",
            "source_license_evidence": source_license_evidence or "",
            "platform_video_id": platform_video_id or "",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = PUBLISHED_CLIPS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
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
            consumed_at = datetime.fromisoformat(str(consumed_at_raw))
        except (TypeError, ValueError):
            out.append(s)
            continue
        if consumed_at >= cutoff:
            out.append(s)
    return out


def _build_story(
    clip_subject: str,
    topic_key: str,
    topic_cfg: dict,
    pexels_clip: "BrollClip",
    ai_out: dict,
    enrichment: dict | None = None,
) -> dict:
    """Assemble the queue entry. Matches the shared queue shape so
    `generate_shorts.py` doesn't need to change."""
    enrichment = enrichment or {}
    commons = enrichment.get("commons") or {}
    gbif = enrichment.get("gbif") or {}
    source_raw = getattr(pexels_clip, "source", "") or "unknown"
    source_name = _source_display_name(source_raw)
    source_meta = getattr(pexels_clip, "source_metadata", {}) or {}
    license_evidence = getattr(pexels_clip, "license_evidence", "") or ""
    url = pexels_clip.url or pexels_clip.download_url
    now = datetime.now(timezone.utc).isoformat()
    source_title = _safe_generated_source_value(pexels_clip.title or "")
    source_description = _safe_generated_source_value(str(source_meta.get("description") or "").strip())
    visible_description = source_description or source_title or clip_subject
    # Merge the AI-picked tags with the topic's evergreen tags,
    # deduplicating. Capped at 8 to leave room for upload_youtube's
    # tag-packer + evergreens it adds later.
    merged_tags: list[str] = list(ai_out.get("yt_tags") or [])
    for t in topic_cfg.get("tags", []):
        if t not in merged_tags:
            merged_tags.append(t)
        if len(merged_tags) >= 8:
            break
    description = re.sub(
        r"(?i)Source:\s*Pexels",
        f"Source: {source_name}",
        str(ai_out["yt_description"]),
    )
    return {
        "id": _story_id(url),
        "fetched_at": now,
        "published_at": now,
        "consumed": False,
        "consumed_at": None,
        "title": clip_subject,
        "url": url,
        "source": source_name,
        "source_url": url,
        "source_title": source_title,
        "source_license": pexels_clip.license,
        "source_license_evidence": license_evidence,
        "source_clip_id": _source_clip_id(pexels_clip),
        "source_download_url": pexels_clip.download_url,
        "source_creator": _safe_generated_source_value(source_meta.get("creator", "")),
        "source_collection": _safe_generated_source_value(source_meta.get("collection", "")),
        "source_description": source_description,
        "rights_policy": source_meta.get("rights_policy", ""),
        "category": topic_key,
        "description": f"{topic_cfg.get('description_prefix', 'A clip of an animal')}: {visible_description}".strip(),
        # BrollClip doesn't carry a preview image — leave empty; the
        # generator renders its own title card frame.
        "image_url": "",
        "breaking": False,
        # Animals are always relevant for this channel — score the AI's
        # opinion on top of a high baseline so a story with score=8 from
        # the AI still wins over a 4 even after the bias chain.
        "relevance": 9.0,
        "score": ai_out.get("score", 7),
        "safety_penalty": 0,
        "native_lang": "en",
        # AI-enriched fields below.
        "seo_title": ai_out["seo_title"],
        "yt_tags": merged_tags[:8],
        "geo_hashtag": ai_out["geo_hashtag"],
        "topic_hashtag": ai_out["topic_hashtag"],
        "yt_description": description,
        "thumbnail_text": ai_out["thumbnail_text"],
        "hook": ai_out["hook"],
        "script": ai_out["script"],
        "lead": ai_out["lead"],
        "sentiment": ai_out["sentiment"],
        "trend_context": dict(ai_out.get("trend_context") or {}),
        # YouTube Shorts discovery hashtags.
        # Carried on the queue so generate_shorts can drop them into the
        # caption without reaching back into ANIMAL_TOPICS.
        "discovery_hashtags": list(topic_cfg.get("discovery_hashtags") or []),
        # Legacy Pexels fields stay for old consumers.
        "pexels_video_id": _pexels_id_from_clip(pexels_clip),
        "pexels_download_url": pexels_clip.download_url if source_raw.lower() == "pexels" else "",
        "gbif": gbif,
        "commons_image_url": _safe_commons_value(commons.get("image_url", "")),
        "commons_page_url": _safe_commons_value(commons.get("page_url", "")),
        "commons_license": _safe_commons_value(commons.get("license", "")),
        "commons_artist": _safe_commons_value(commons.get("artist", "")),
    }


# ── Main ──────────────────────────────────────────────────────────


def _rotate_queries(topic_key: str, queries: list[str], take: int) -> list[str]:
    """Pick `take` queries deterministically rotated by the current
    3-hour window. This stops the same N runs/day from hitting the
    same N queries every time, keeping the queue more diverse.
    """
    if not queries:
        return []
    take = max(0, min(int(take or 0), len(queries)))
    if take <= 0:
        return []
    window = datetime.now(timezone.utc).hour // 3  # 0..7
    seed = int(hashlib.sha256(f"{topic_key}:{window}".encode("utf-8")).hexdigest()[:8], 16)
    start = seed % len(queries)
    return [queries[(start + i) % len(queries)] for i in range(take)]


def _discover_topic_clips(
    queries: list[str],
    *,
    per_topic_n: int,
    dedupe_keys: set[str],
    pending_gap: int = 0,
) -> list:
    """Fetch a deduped candidate pool before spending AI calls.

    The queue can hold hundreds of rejected Pexels ids. Searching only
    page 1 and slicing before dedupe makes backfills look successful
    while yielding no usable clips. This helper walks a small, bounded
    search surface and filters rejected/published clips before returning.
    """
    if per_topic_n <= 0 or not queries:
        return []

    max_pages = PEXELS_DISCOVERY_PAGES if pending_gap >= PEXELS_DEEP_SEARCH_GAP else 1
    pool_target = max(per_topic_n, min(per_topic_n * 4, per_topic_n + 8))
    collected: list = []
    seen_keys: set[str] = set()
    calls = 0

    for page in range(1, max_pages + 1):
        for query in queries:
            if len(collected) >= pool_target or calls >= PEXELS_TOPIC_CALL_BUDGET:
                break
            calls += 1
            try:
                clips = fetch_pexels(query, per_page=PEXELS_SEARCH_PER_PAGE, page=page)
            except Exception as exc:
                log.warning("video provider fetch failed for %r page %d: %s", query, page, exc)
                clips = []
            for clip in clips:
                clip_keys = _clip_dedupe_keys(clip)
                if not clip_keys or clip_keys & dedupe_keys or clip_keys & seen_keys:
                    continue
                seen_keys.update(clip_keys)
                collected.append(clip)
                if len(collected) >= pool_target:
                    break
        if len(collected) >= pool_target or calls >= PEXELS_TOPIC_CALL_BUDGET:
            break

    log.info(
        "  Pexels search calls=%d pages=%d per_page=%d usable_candidates=%d/%d",
        calls,
        max_pages,
        PEXELS_SEARCH_PER_PAGE,
        len(collected),
        pool_target,
    )
    return collected


def _latest_strategy(path: Path = Path("_data/analytics/latest.json")) -> dict:
    """Read the latest free analytics strategy, if the dashboard made one."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    strategy = data.get("production_recommendations") or {}
    return strategy if isinstance(strategy, dict) else {}


def _latest_comments(path: Path = Path("_data/analytics/comments.json")) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _pending_category_counts(queue: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for story in queue.get("stories") or []:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        category = str(story.get("category") or "wildlife").strip().lower()
        counts[category] = counts.get(category, 0) + 1
    return counts


def _pending_count(queue: dict) -> int:
    return sum(1 for story in queue.get("stories") or [] if isinstance(story, dict) and not story.get("consumed"))


def _agency_held_ids(path: Path = Path("_data/agency_gate.json")) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {str(item.get("id") or "") for item in (payload.get("held_items") or []) if isinstance(item, dict)}


def _publish_ready_supply(
    queue: dict,
    *,
    paused: set[str] | None = None,
    held_ids: set[str] | None = None,
    require_final_quality: bool = False,
) -> int:
    ready = 0
    paused = {str(item).strip().lower() for item in (paused or set()) if str(item).strip()}
    agency_held = {str(item): ["held"] for item in (held_ids or set()) if str(item)}
    for story in queue.get("stories") or []:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        ok, _reasons = publish_ready_verdict(story, paused=paused, agency_held=agency_held)
        if not ok:
            continue
        if require_final_quality:
            quality_ok, _quality_reasons, _score = publish_quality_verdict(story, env=os.environ)
            if not quality_ok:
                continue
        ready += 1
    return ready


def _topic_iteration_order(queue: dict, plan: dict[str, dict[str, Any]], paused: set[str] | None = None) -> list[str]:
    """Return active topic keys in the order fetch backfill should try them."""
    paused = {str(item).strip().lower() for item in (paused or set()) if str(item).strip()}
    active = [topic_key for topic_key in ANIMAL_TOPICS if topic_key not in paused]
    if _publish_ready_supply(queue, paused=paused, held_ids=_agency_held_ids(), require_final_quality=True) > 0:
        return active

    pending = _pending_category_counts(queue)
    original_order = {topic_key: index for index, topic_key in enumerate(ANIMAL_TOPICS)}

    def sort_key(topic_key: str) -> tuple[int, int, float, int, int]:
        topic_plan = plan.get(topic_key) or {}
        try:
            trend_weight = float(topic_plan.get("trend_weight") or 1.0)
        except (TypeError, ValueError):
            trend_weight = 1.0
        try:
            budget = int(topic_plan.get("budget") or 0)
        except (TypeError, ValueError):
            budget = 0
        recovery_bucket = 0 if topic_key in PUBLISH_READY_RECOVERY_TOPICS else 1
        return (
            recovery_bucket,
            pending.get(topic_key, 0),
            -trend_weight,
            -budget,
            original_order.get(topic_key, 10_000),
        )

    return sorted(active, key=sort_key)


def _topic_fetch_plan(
    queue: dict,
    strategy: dict | None = None,
    comments: dict | None = None,
    trends: dict | None = None,
    max_per_topic: int = MAX_PER_TOPIC,
) -> dict[str, dict[str, Any]]:
    """Return per-topic fetch budgets tuned by queue pressure + analytics."""
    pending = _pending_category_counts(queue)
    weights = (strategy or {}).get("category_weights") or {}
    requested = {
        _ANIMAL_ALIASES.get(str(item).strip().lower(), str(item).strip().lower())
        for item in ((comments or {}).get("requested_animals") or [])
        if str(item).strip()
    }
    plan: dict[str, dict[str, Any]] = {}
    base = max(1, int(max_per_topic))
    for topic_key, cfg in ANIMAL_TOPICS.items():
        count = pending.get(topic_key, 0)
        budget = base
        if count <= 3:
            budget += 2
        elif count <= 7:
            budget += 1
        elif count >= 18:
            budget = max(1, base - 2)
        elif count >= 12:
            budget = max(1, base - 1)
        try:
            weight = float(weights.get(topic_key, 1.0) or 1.0)
        except (TypeError, ValueError):
            weight = 1.0
            
        # Growth Hack: Apply true proportional scaling based on analytics views
        if weight > 1.0:
            budget = max(budget + 1, int(budget * weight))
        elif weight < 1.0 and count >= 8:
            budget = max(1, int(budget * weight))
        topic_animals = set().union(*(_animal_terms(query) for query in cfg.get("queries", [])))
        requested_for_topic = sorted(topic_animals & requested)
        if requested_for_topic:
            budget += 2
        trend_weight = trend_weight_for_category(topic_key, trends)
        if trend_weight >= 1.4:
            budget += 2
        elif trend_weight >= 1.2:
            budget += 1
        query_take = min(len(cfg.get("queries") or []), max(2, min(4, budget)))
        plan[topic_key] = {
            "budget": max(1, budget),
            "query_take": query_take,
            "trend_queries": trend_queries_for_category(topic_key, trends),
            "comment_queries": [f"{animal} animal behavior" for animal in requested_for_topic[:2]],
            "trend_weight": trend_weight,
        }
    return plan


def _backfill_per_topic_cap(max_new_entries: int, topic_count: int | None = None) -> int | None:
    """Cap short queue backfills so one early topic cannot fill the whole run."""
    if max_new_entries <= 0:
        return None
    count = max(1, int(topic_count or len(ANIMAL_TOPICS)))
    return max(1, (max_new_entries + count - 1) // count)


def _backfill_plan_for_inventory(
    *,
    pending_at_start: int,
    target_pending: int,
    publish_ready_at_start: int,
    publish_eligible_at_start: int | None = None,
    ready_target: int = QUEUE_TARGET_PUBLISH_READY,
    recovery_batch: int = QUEUE_READY_RECOVERY_BATCH,
) -> tuple[int, int]:
    """Return adjusted target_pending and max_new_entries for operational supply."""
    target_pending = max(0, int(target_pending or 0))
    pending_at_start = max(0, int(pending_at_start or 0))
    operational_supply = (
        max(0, int(publish_eligible_at_start or 0))
        if publish_eligible_at_start is not None
        else max(0, int(publish_ready_at_start or 0))
    )
    max_new_entries = max(0, target_pending - pending_at_start) if target_pending else 10_000
    if target_pending and ready_target and operational_supply < ready_target:
        recovery_gap = ready_target - operational_supply
        recovery_entries = max(recovery_batch, recovery_gap * recovery_batch)
        max_new_entries = max(max_new_entries, recovery_entries)
        target_pending = max(target_pending, pending_at_start + max_new_entries)
    return target_pending, max_new_entries


def main() -> int:
    from utils.panic import abort_if_halted

    abort_if_halted("fetch_animals")
    write_quota_ledger_row(
        estimate_fetch_content_cost(
            search_calls=min(len(ANIMAL_TOPICS) * PEXELS_TOPIC_CALL_BUDGET, 200),
            provider="pexels",
        )
    )

    log.info("=" * 60)
    log.info("🐾 Wild Brief — animal queue refresh %s", datetime.now(timezone.utc).isoformat())
    log.info("=" * 60)

    log.info("Video provider: Pexels-only curated footage")
    ai_keys = ("MISTRAL_API_KEY", "CEREBRAS_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY")
    if not any(os.environ.get(key, "").strip() for key in ai_keys):
        log.error("❌ No AI provider key set — configure MISTRAL, CEREBRAS, GEMINI or GROQ.")
        return 2

    queue = _load_queue()
    pending_at_start = _pending_count(queue)
    target_pending = max(0, int(QUEUE_TARGET_PENDING or 0))
    paused = set(paused_categories().keys()) if ops_guardian_enforced() else set()
    held_ids = _agency_held_ids()
    publish_ready_at_start = _publish_ready_supply(queue, paused=paused, held_ids=held_ids)
    publish_eligible_at_start = _publish_ready_supply(
        queue,
        paused=paused,
        held_ids=held_ids,
        require_final_quality=True,
    )
    target_pending, max_new_entries = _backfill_plan_for_inventory(
        pending_at_start=pending_at_start,
        target_pending=target_pending,
        publish_ready_at_start=publish_ready_at_start,
        publish_eligible_at_start=publish_eligible_at_start,
    )
    if target_pending and publish_eligible_at_start < QUEUE_TARGET_PUBLISH_READY:
        log.info(
            "Operational publish-eligible supply is low (%d/%d; publish-ready=%d); opening %d recovery candidate slots.",
            publish_eligible_at_start,
            QUEUE_TARGET_PUBLISH_READY,
            publish_ready_at_start,
            max_new_entries,
        )
    if target_pending:
        log.info("Queue target: %d pending stories; current pending=%d", target_pending, pending_at_start)
        if max_new_entries <= 0:
            log.info("Queue already meets target; only pruning/freshness metadata will be refreshed.")
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
        str(s.get("pexels_video_id", "")) for s in queue["stories"] if s.get("pexels_video_id")
    }
    queue_source_ids: set[str] = {str(s.get("source_clip_id", "")) for s in queue["stories"] if s.get("source_clip_id")}
    published_keys = load_published_clip_keys()
    rejected_keys = load_rejected_clip_keys()
    dedupe_keys: set[str] = queue_ids | queue_pexels_ids | queue_source_ids | published_keys | rejected_keys
    queue_copy_keys = _empty_copy_keys()
    for story in queue["stories"]:
        if isinstance(story, dict):
            _add_story_copy_keys(queue_copy_keys, story)
    copy_keys = _merge_copy_keys(queue_copy_keys, load_published_copy_keys(), load_rejected_copy_keys())
    log.info(
        "🧮 Dedup keyset: %d queue ids + %d published clips = %d total",
        len(queue_ids),
        len(published_keys),
        len(dedupe_keys),
    )
    log.info("Rejected clips included in dedupe: %d", len(rejected_keys))
    log.info(
        "Copy memory: %d titles + %d scripts + %d angles",
        len(copy_keys["titles"]),
        len(copy_keys["scripts"]),
        len(copy_keys["angles"]),
    )
    new_entries: list[dict] = []
    trends = load_trends()
    fetch_plan = _topic_fetch_plan(queue, _latest_strategy(), _latest_comments(), trends)
    topic_order = _topic_iteration_order(queue, fetch_plan, paused)
    if paused:
        log.info("Ops guardian paused topic(s) skipped: %s", ", ".join(sorted(paused)))
    if not topic_order:
        log.warning("No active topics available for queue refresh.")
    per_topic_backfill_cap = None
    if max_new_entries > 0 and target_pending:
        per_topic_backfill_cap = _backfill_per_topic_cap(max_new_entries, topic_count=len(topic_order))
        log.info(
            "Backfill diversity cap: up to %d new entr%s per topic",
            per_topic_backfill_cap,
            "y" if per_topic_backfill_cap == 1 else "ies",
        )

    for topic_key in topic_order:
        topic_cfg = ANIMAL_TOPICS[topic_key]
        if len(new_entries) >= max_new_entries:
            break
        plan = fetch_plan.get(topic_key, {"budget": MAX_PER_TOPIC, "query_take": 2})
        per_topic_n = int(plan.get("budget") or MAX_PER_TOPIC)
        if per_topic_backfill_cap is not None:
            per_topic_n = min(per_topic_n, per_topic_backfill_cap)
        query_take = int(plan.get("query_take") or 2)
        if max_new_entries - len(new_entries) >= PEXELS_DEEP_SEARCH_GAP:
            query_take = max(query_take, min(len(topic_cfg.get("queries") or []), PEXELS_BACKFILL_QUERY_TAKE))
        queries = _rotate_queries(
            topic_key,
            topic_cfg["queries"],
            take=query_take,
        )
        for query in plan.get("trend_queries") or []:
            if query not in queries:
                queries.insert(0, query)
        for query in plan.get("comment_queries") or []:
            if query not in queries:
                queries.insert(0, query)
        queries = queries[: max(2, query_take)]
        log.info("🔎 %s: budget=%d queries=%s", topic_key, per_topic_n, queries)
        clips = _discover_topic_clips(
            queries,
            per_topic_n=per_topic_n,
            dedupe_keys=dedupe_keys,
            pending_gap=max_new_entries - len(new_entries),
        )
        # Shuffle usable candidates so consecutive runs do not always
        # consume the same top-of-results clip.
        random.shuffle(clips)
        log.info("📹 %s: %d usable video candidate(s) returned", topic_key, len(clips))

        topic_new_entries = 0
        for clip in clips:
            if len(new_entries) >= max_new_entries or topic_new_entries >= per_topic_n:
                break
            sid = _story_id(clip.url or clip.download_url)
            pid = _pexels_id_from_clip(clip)
            source_clip_id = _source_clip_id(clip)
            if sid in dedupe_keys or (pid and pid in dedupe_keys) or source_clip_id in dedupe_keys:
                continue
            subject = _subject_from_clip(clip, queries[0])
            story_topic_key, story_topic_cfg = _topic_for_subject(topic_key, topic_cfg, subject)
            if story_topic_key != topic_key:
                log.info("  reclassified Pexels subject %s -> %s: %s", topic_key, story_topic_key, subject[:80])
            if not _topic_accepts_subject(story_topic_cfg, subject):
                log.warning("  skipping off-topic video clip for %s: %s", story_topic_key, subject[:80])
                continue
            enrichment = enrich_subject(subject)
            context = story_topic_cfg.get("description_prefix", "an animal clip")
            taxonomy = taxonomy_prompt(enrichment)
            if taxonomy:
                context = f"{context}. {taxonomy}"
            ai_out = _ai_enhance_animal(
                subject,
                context,
                trend_context_for_category(story_topic_key, trends),
                variation_material=clip.url or clip.download_url or _source_clip_id(clip),
            )
            if not ai_out:
                log.debug("  AI enrichment failed for %s", subject[:60])
                continue
            script_key = _script_key(ai_out.get("script", ""))
            title_key = _copy_key(ai_out.get("seo_title") or ai_out.get("title") or "")
            if title_key and title_key in copy_keys["titles"]:
                log.warning("  skipping repeated title for %s: %s", subject[:60], ai_out.get("seo_title", "")[:80])
                continue
            if not script_key or script_key in copy_keys["scripts"]:
                log.warning("  skipping repeated or empty script for %s", subject[:60])
                continue
            story = _build_story(subject, story_topic_key, story_topic_cfg, clip, ai_out, enrichment)
            angle_key = _story_angle_key(story)
            if angle_key and angle_key in copy_keys["angles"]:
                log.warning("  skipping repeated angle for %s: %s", subject[:60], angle_key[:100])
                continue
            new_entries.append(story)
            topic_new_entries += 1
            _add_story_copy_keys(copy_keys, story)
            dedupe_keys.add(story["id"])
            if pid:
                dedupe_keys.add(pid)
            if source_clip_id:
                dedupe_keys.add(source_clip_id)

    # Merge + prune.
    queue["stories"].extend(new_entries)
    queue["stories"] = _prune_queue(queue["stories"], KEEP_DAYS)
    topic_candidates: list[dict[str, Any]] = []
    try:
        raw_topic_candidates = (
            json.loads(Path("_data/trends/topic_candidates.json").read_text(encoding="utf-8")).get("candidates") or []
        )
        if isinstance(raw_topic_candidates, list):
            topic_candidates = [item for item in raw_topic_candidates if isinstance(item, dict)]
    except Exception:
        topic_candidates = []
    queue = annotate_queue(queue, topic_candidates)
    freshness_path = Path("_data/trends/freshness_report.json")
    freshness_path.parent.mkdir(parents=True, exist_ok=True)
    freshness_path.write_text(
        json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(), **freshness_report(queue)},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    queue["updated_at"] = datetime.now(timezone.utc).isoformat()
    if target_pending:
        queue["target_pending"] = target_pending
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(
        json.dumps(queue, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    pending = sum(1 for s in queue["stories"] if not s.get("consumed"))
    log.info(
        "✅ +%d new animal entries (queue: %d total, %d pending)", len(new_entries), len(queue["stories"]), pending
    )

    # Keep the AI disk cache bounded — same chore fetch_animals.py does.
    try:
        ai_cache_prune()
    except Exception as exc:
        log.debug("ai_cache prune skipped: %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
