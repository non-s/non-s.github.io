#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_shorts.py — Gera videos verticais curtos para o YouTube Shorts
================================================================================
Formato: vídeo vertical 1080x1920, 25-35 segundos, uma história por vídeo.
Máximo 3 vídeos por execução para respeitar limites de API.

Estrutura de cada video (YouTube Shorts):
  Hook        ~3s    Surprising fact, starts immediately
  Fato 1     ~8s    Primeira surpresa
  Fato 2     ~8s    Segunda surpresa
  Fato 3     ~8s    Terceira surpresa (opcional)
  CTA         ~2s    "Follow for more wild nature facts."

Total alvo: ~25-35 segundos. YouTube Shorts premia completion rate
muito mais que duração — videos de 30s com 85% completion batem
videos de 55s com 50% completion. We clip at 35s hard.
"""

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# fcntl is POSIX-only; we use it to serialise queue access against
# fetch_animals.py. Guarded for local Windows dev — the CI runner is Linux.
try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from utils.agency_gate import filter_candidates, is_soft_agency_hold
from utils.animal_enrichment import download_commons_image
from utils.audience_expansion import global_strategy, merge_hashtags, merge_search_tags
from utils.broll import BrollClip, download_clip, fetch_broll_clips
from utils.captions import (
    group_words_into_phrases,
    write_ass,
)
from utils.captions import (
    transcribe as captions_transcribe,
)
from utils.claim_risk import evaluate_claim_risk
from utils.content_agency import rank_for_agency
from utils.digest import load_blocked_slugs
from utils.editorial import rank_candidates
from utils.editorial import review as editorial_review
from utils.editorial_guard import editorial_verdict
from utils.experiments import assign_all_for_production, assign_variant, record_variant_assignments
from utils.first_frame_audit import audit_opening_frames
from utils.frame_zero_packaging import score_frame_zero
from utils.growth_engine import analyze_retention, detect_weak_content, load_format_memory, score_topic
from utils.growth_strategy import load_strategy, ops_guardian_enforced, paused_categories, rank_for_growth
from utils.growth_studio import studio_brief_for_story
from utils.hook_library import choose_hook_template, score_hook
from utils.human_voice import score_text as score_human_voice
from utils.humanity_engine import polish_story
from utils.humanity_engine import score_story as score_humanity_story
from utils.intro_outro import wrap_with_intro_outro
from utils.local_rewriter import rescue_story
from utils.loop_semantics import score_loop_semantics
from utils.monetization_audit import audit as audit_monetization
from utils.music_bed import add_music_bed
from utils.nature_strategy import NATURE_BROLL_QUERIES
from utils.opening_gate_v2 import evaluate_opening_gate
from utils.originality_pack import build_originality_pack, write_originality_pack
from utils.packaging import package_story
from utils.payoff_controller import score_payoff
from utils.pre_publish_audit import audit_package as audit_publish_package
from utils.publish_priority import publish_priority_key
from utils.publish_score import score_metadata
from utils.publish_score import score_story as publish_score_story
from utils.queue_pruner import (
    EDITORIAL_COOLDOWN_SUPPLY_FALLBACK,
    PUBLISH_READY_SUPPLY_RESERVE_FALLBACK,
    RESERVE_ALLOWED_OPPORTUNITY_REASONS,
    RESERVE_MIN_PUBLISH_SCORE,
    production_quality_issues,
    prune_queue,
)
from utils.rejected_queue import record_rejection
from utils.retention_surgeon import diagnose as diagnose_retention
from utils.rights_audit import audit_rights
from utils.rights_guard import evaluate_rights_guard, write_source_provenance
from utils.script_quality import evaluate as evaluate_script
from utils.script_quality import should_block as quality_should_block
from utils.search_enrichment import enrich_search_terms
from utils.seo_optimizer import lint_metadata, optimise_story, seo_score
from utils.story_intelligence import audit_hook, audit_title, classify_format
from utils.story_patterns import classify_story_pattern
from utils.studio_rewrite import rewrite_if_needed
from utils.text import humanize_for_tts
from utils.time_semantics import temporal_fields
from utils.translation import SUPPORTED_LANGUAGES, translate_story
from utils.tts_fallback import synthesize_with_coqui
from utils.video_common import draw_rounded_rect, get_font, wrap_text
from utils.video_compose import build_broll_short, build_static_short
from utils.visual_ctr import select_best_frame
from utils.visual_qa import evaluate_frame, evaluate_local_frame
from utils.youtube_brain import creator_premortem, publish_brain

# ── Config ────────────────────────────────────────────────────────
# Language axis. "en" is the default channel; setting LANGUAGE=pt-BR
# (or es-ES, es-MX, fr-FR) flips this run into the sibling-channel
# pipeline:
#   • every story passes through utils.translation.translate_story
#   • outputs land in `_videos_<lang>/` to avoid colliding with English
#   • shorts_done bookkeeping is per-language
# All of the rest of the rendering (b-roll, captions, thumbnail) is
# language-agnostic — only the script and metadata change.
LANGUAGE = os.environ.get("LANGUAGE", "en").strip() or "en"
if LANGUAGE != "en" and LANGUAGE not in SUPPORTED_LANGUAGES:
    raise RuntimeError(f"LANGUAGE={LANGUAGE!r} is not supported. " f"Pick one of: en, {', '.join(SUPPORTED_LANGUAGES)}")

VIDEOS_DIR = Path("_videos") if LANGUAGE == "en" else Path(f"_videos_{LANGUAGE}")
SHORTS_DONE_FILE = VIDEOS_DIR / "shorts_done.json"
LOG_FILE = f"generate_shorts{'' if LANGUAGE == 'en' else '_' + LANGUAGE}.log"
# Cap of shorts produced per run. Overridable via env var so the
# workflow can tune it without editing this file. Defaults to 3 —
# matches youtube-bot.yml schedule.
MAX_SHORTS_PER_RUN = int(os.environ.get("MAX_SHORTS_PER_RUN", "3"))
SHORT_W, SHORT_H = 1080, 1920  # vertical 9:16
PUBLISH_WINDOW_TOP_CANDIDATE_ID = os.environ.get("PUBLISH_WINDOW_TOP_CANDIDATE_ID", "").strip()


def _env_enabled(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


QUALITY_REQUIRE_MOTION_BROLL = _env_enabled("QUALITY_REQUIRE_MOTION_BROLL")
QUALITY_REQUIRE_CAPTIONS = _env_enabled("QUALITY_REQUIRE_CAPTIONS")
QUALITY_MIN_VISUAL_QA_SCORE = int(os.environ.get("QUALITY_MIN_VISUAL_QA_SCORE", "1"))
REQUIRE_SHORT_ON_PUBLISH = _env_enabled("REQUIRE_SHORT_ON_PUBLISH")
PUBLISH_WINDOW_SELECTED_ONLY = _env_enabled("PUBLISH_WINDOW_SELECTED_ONLY", "1")

# Paleta de cores — identidade Wild Brief
BG_DARK = (8, 8, 18)
ACCENT_BLUE = (0, 195, 255)
ACCENT_CYAN = (0, 240, 200)
RED_LIVE = (220, 50, 50)
TEXT_WHITE = (245, 245, 255)
TEXT_GRAY = (160, 165, 190)

# Cores por categoria
CATEGORY_COLORS = {
    # Wild Brief animal categories.
    "CATS": (255, 140, 90),  # warm orange (tabby tone)
    "DOGS": (255, 195, 90),  # golden retriever yellow
    "OCEAN": (0, 140, 220),  # deep marine blue
    "WILDLIFE": (180, 130, 60),  # savanna ochre
    "BIRDS": (90, 200, 255),  # sky blue
    "FARM": (140, 180, 90),  # field green
    "REPTILES": (90, 185, 115),  # scale green
    "INSECTS": (245, 185, 60),  # amber macro
    "PRIMATES": (210, 145, 95),  # warm forest
    "NOCTURNAL": (120, 120, 210),  # night violet-blue
    "ARCTIC": (150, 220, 245),  # ice blue
    # Generic animal fallback — used when a queue entry slips through
    # without a recognised category, so the gradient renders something
    # warm and on-brand instead of a default blue.
    "ANIMAL": (200, 150, 90),
    "ANIMALS": (200, 150, 90),
    "PLANTS": (70, 205, 120),
    "TREES": (45, 145, 95),
    "FUNGI": (190, 150, 245),
    "RIVERS": (35, 190, 230),
    "MOUNTAINS": (160, 170, 185),
    "FORESTS": (40, 170, 110),
    "VOLCANOES": (245, 95, 45),
    "WEATHER": (110, 190, 255),
    "RARE_PHENOMENA": (255, 210, 80),
    "GEOLOGY": (195, 165, 125),
    "ECOSYSTEMS": (95, 210, 155),
    "EARTH_FROM_SPACE": (80, 170, 255),
    "CONSERVATION": (80, 200, 110),
    "DISCOVERIES": (255, 185, 85),
}

ANIMAL_BROLL_QUERIES = {
    "CATS": "cat animal",
    "DOGS": "dog animal",
    "OCEAN": "marine animal underwater",
    "WILDLIFE": "wild animal nature",
    "BIRDS": "bird animal",
    "FARM": "farm animal",
    "REPTILES": "reptile animal",
    "INSECTS": "insect macro nature",
    "PRIMATES": "monkey primate wildlife",
    "NOCTURNAL": "nocturnal animal night",
    "ARCTIC": "arctic animal snow",
}
NATURE_BROLL_QUERY_MAP = {**ANIMAL_BROLL_QUERIES, **NATURE_BROLL_QUERIES}

# ── TTS voice rotation ────────────────────────────────────────────
#
# Channel grew on Jenny's voice originally, but a single voice across
# every Short flattens audience appetite. Shorts viewers notice when
# consecutive videos sound identical and skip the second
# (the "session homogeneity" signal). Rotating between a small panel
# of high-quality edge-tts voices keeps things fresh without dropping
# the channel's recognisable animal-facts tone.
#
# We pick the voice deterministically from the story's title hash so a
# given story always renders with the same voice (idempotent reruns)
# and there's roughly-even distribution across the panel.
# SIGNATURE VOICE — committed to a single host identity.
#
# The audit data is clear: automated channels that monetize have ONE
# recognizable voice. Six-voice rotation reads as randomness, not
# editorial choice. The Wild Brief narrator now speaks in
# en-US-ChristopherNeural: an authoritative English news/novel voice
# that lands closer to documentary and tech-explainer narration than
# the previous assistant-like Aria/Jenny/Guy panel.
#
# The second voice (Roger) is only a contingency: when Christopher's
# edge-tts CDN blips on a particular Short, Roger takes over for that
# render. Listeners on the channel should hear Christopher 99 % of the
# time.
HOST_VOICE_PRIMARY = "en-US-ChristopherNeural"
HOST_VOICE_BACKUP = "en-US-RogerNeural"
HOST_VOICE_VARIANTS = {
    "documentary": HOST_VOICE_PRIMARY,
    "authority": HOST_VOICE_PRIMARY,
    "refugio": HOST_VOICE_PRIMARY,
    "techzone": HOST_VOICE_PRIMARY,
    # Legacy experiment labels kept so queued stories stamped before
    # the voice change do not leak the old narrator panel.
    "aria": HOST_VOICE_PRIMARY,
    "jenny": HOST_VOICE_PRIMARY,
    "guy": HOST_VOICE_PRIMARY,
}

VOICE_PANEL = [HOST_VOICE_PRIMARY, HOST_VOICE_BACKUP]
# Backwards-compat alias — kept for any caller still importing it.
VOICE_SHORT = HOST_VOICE_PRIMARY

# Per-locale signature voices. Each locale picks ONE host voice +
# ONE backup, matching the English channel's "one recognizable
# host" commitment.
VOICE_PANEL_BY_LOCALE: dict[str, list[str]] = {
    "en": VOICE_PANEL,
    "pt-BR": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"],
    "es-ES": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural"],
    "es-MX": ["es-MX-DaliaNeural", "es-MX-JorgeNeural"],
    "fr-FR": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"],
}


def pick_voice(seed_text: str, category: str = "", voice_tag: str = "", narrator_variant: str = "") -> str:
    """Pick the host's signature voice for this Short.

    With the post-May-2026 humanization shift, the channel is committed
    to a SINGLE recognizable host voice per locale. We return the
    primary voice for the chosen locale on every call — `seed_text`
    and `category` are kept in the signature for API compatibility
    with the older rotation logic but are no longer used to scatter
    voices.

    The backup voice (index 1 of the panel) is reserved for the case
    where the primary voice's edge-tts CDN errors on a particular
    render — caller handles that fallback explicitly via VOICE_SHORT.
    """
    voice_tag = (voice_tag or "").strip()
    panel = VOICE_PANEL_BY_LOCALE.get(
        voice_tag if voice_tag and voice_tag != "en" else "en",
        VOICE_PANEL,
    )
    if not voice_tag or voice_tag == "en":
        variant = narrator_variant or assign_variant("narrator_voice", seed_text or category or "wildbrief")
        return HOST_VOICE_VARIANTS.get(variant, HOST_VOICE_PRIMARY)
    return panel[0] if panel else HOST_VOICE_PRIMARY


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def clean_text(text: str, max_chars: int = 500) -> str:
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_chars]


def _normalise_editorial_text(text: str) -> str:
    """Clean encoding scars and repeated spaces without changing meaning."""
    out = str(text or "")
    replacements = {
        "â€™": "'",
        "â€”": "-",
        "â€“": "-",
        "ðŸ„": "",
        "ðŸ”": "",
        "ðŸ¦†": "",
        "ðŸ": "",
        "ðŸ»": "",
    }
    for bad, good in replacements.items():
        out = out.replace(bad, good)
    out = re.sub(r"\s+", " ", out).strip()
    return out


_THUMB_STOP_WORDS = {
    "A",
    "AN",
    "AND",
    "ANOTHER",
    "ARE",
    "AT",
    "BECAUSE",
    "CLUE",
    "DO",
    "DOES",
    "FOR",
    "HAVE",
    "HAS",
    "HIDING",
    "IN",
    "IS",
    "IT",
    "ITS",
    "LOOK",
    "ON",
    "PLAIN",
    "REALLY",
    "RELY",
    "SECRET",
    "SIGNAL",
    "SIGHT",
    "THE",
    "THEIR",
    "THEY",
    "THIS",
    "TO",
    "USE",
    "USES",
    "WATCH",
    "WHEN",
    "WHY",
}

_THUMB_ANIMAL_WORDS = {
    "ANTS",
    "BEARS",
    "BEES",
    "BIRDS",
    "BUTTERFLIES",
    "CATS",
    "CHICKENS",
    "COWS",
    "DEER",
    "DOGS",
    "DOLPHINS",
    "DUCKS",
    "DUCKLINGS",
    "ELEPHANTS",
    "GOATS",
    "HORSES",
    "LIONS",
    "MONKEYS",
    "ORANGUTANS",
    "OWLS",
    "PENGUINS",
    "SHARKS",
    "SHEEP",
    "SNAKES",
    "TIGERS",
    "WHALES",
    "WOLVES",
}

_THUMB_CUE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bFAKE\s+INJUR(?:Y|IES)\b|\bBROKEN\s+WING\b", "FAKE INJURY"),
    (r"\bAIR\s+BUBBLES?\b", "AIR BUBBLES"),
    (r"\bBOTTLE\s+MEMORY\b", "BOTTLE MEMORY"),
    (r"\bDANCE\s+MAP\b", "DANCE MAP"),
    (r"\bEAR\s+MARKS?\b", "EAR MARKS"),
    (r"\bELECTRIC\s+SENSE\b", "ELECTRIC SENSE"),
    (r"\bFLOCK\s+MEMORY\b", "FLOCK MEMORY"),
    (r"\bGROUND\s+SIGNAL\b", "GROUND SIGNAL"),
    (r"\bHEAT\s+VISION\b", "HEAT VISION"),
    (r"\bHUMAN\s+SIGNAL\b", "HUMAN SIGNAL"),
    (r"\bMAGNETIC\s+MAP\b", "MAGNETIC MAP"),
    (r"\bMOTION\s+LOCK\b", "MOTION LOCK"),
    (r"\bSCENT\s+(?:MAP|POST|ROAD)\b", "SCENT MAP"),
    (r"\bSILENT\s+WINGS?\b", "SILENT WINGS"),
    (r"\bSTAR\s+COMPASS\b", "STAR COMPASS"),
    (r"\bSTEADY\s+EYES?\b", "STEADY EYES"),
    (r"\bTASTE\s+ARMS\b", "TASTE ARMS"),
    (r"\bTASTE\s+FEET\b", "TASTE FEET"),
    (r"\bTINY\s+MATH\b", "TINY MATH"),
    (r"\bTONGUE\s+SMELL\b", "TONGUE SMELL"),
    (r"\bUV\s+VISION\b", "UV VISION"),
    (r"\bWIDE\s+VISION\b", "WIDE VISION"),
    (r"\bWING\s+SCALES?\b", "WING SCALES"),
    (r"\bSTRAW(?:-LIKE)?\s+TONGUE\b|\bNECTAR\b", "NECTAR STRAW"),
    (r"\bHEAD\s+MOVEMENT\b|\bHEAD\s+TILT\w*\b", "HEAD TILT"),
    (r"\bWING\s+MOVEMENT\b|\bWING\s+ANGLE\b|\bWINGS?\b", "WING FLASH"),
    (r"\bTAIL\s+POSITION\b|\bTAIL\s+LIFT\b|\bTAILS?\b", "TAIL LIFT"),
    (r"\bEAR\s+POSITION\b|\bEAR\s+MOVEMENT\b|\bEARS?\b", "EAR SHIFT"),
    (r"\bEYES?\b|\bFACE\b|\bFACES\b", "FACE MEMORY"),
    (r"\bFEET\b|\bFOOT\b|\bHOOF\b|\bHOOVES\b|\bPAWS?\b", "FOOT GRIP"),
    (r"\bBODY\s+CUE\b|\bBODY\s+POSTURE\b|\bBODY\b", "BODY MOVE"),
    (r"\bCALL\b|\bSOUND\b", "ALARM CALL"),
    (r"\bNOSE\b|\bSCENT\b", "SCENT TRICK"),
    (r"\bFIN\s+MOVEMENT\b|\bFINS?\b", "FIN SHIFT"),
    (r"\bBEAK\s+MOVEMENT\b|\bBEAK\b", "BEAK CLUE"),
    (r"\bCOLOR\b|\bCOLOUR\b", "COLOR CHANGE"),
    (r"\bWARNING\b|\bWARN\b", "WARNING SIGN"),
)


def _compact_thumbnail_candidate(value: str) -> str:
    raw = _normalise_editorial_text(value).upper()
    raw = re.sub(r"[^A-Z0-9\s'-]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip(" -'")
    if not raw:
        return ""
    for pattern, replacement in _THUMB_CUE_PATTERNS:
        if re.search(pattern, raw):
            return replacement
    words = [word.strip("'-") for word in raw.split()]
    useful = [word for word in words if word and word not in _THUMB_STOP_WORDS]
    if len(useful) > 3:
        without_animals = [word for word in useful if word not in _THUMB_ANIMAL_WORDS]
        if len(without_animals) >= 2:
            useful = without_animals
    useful = useful[:3]
    return " ".join(useful)


def _clean_thumbnail_text(text: str, *, title: str = "", hook: str = "") -> str:
    """Make the cover text read like a fast visual cue, not generated prose."""
    for candidate in (text, hook, title, f"{title} {hook}"):
        compact = _compact_thumbnail_candidate(candidate)
        if compact:
            return compact[:24].strip() or "NATURE MOMENT"
    return "NATURE MOMENT"


def _queue_story_quality_issues(qs: dict, *, seen_scripts: set[str]) -> list[str]:
    """Hard reject queue entries that would make the channel look automated."""
    try:
        return production_quality_issues(qs, seen_scripts=seen_scripts)
    except Exception as exc:  # pragma: no cover - import is stable in CI
        return [f"validator_unavailable:{exc}"]


# ── Extrai 3 bullet points da descrição ───────────────────────────
def extract_key_points(description: str) -> list[str]:
    """Extract 3 concise key points from a story description."""
    desc = clean_text(description, 800)
    sentences = re.split(r"(?<=[.!?])\s+", desc)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    points = []
    for s in sentences[:6]:
        # Truncate long sentences to keep them punchy
        if len(s) > 100:
            s = s[:97] + "..."
        points.append(s)
        if len(points) == 3:
            break

    # Don't pad with boilerplate — empty slots are better than literal
    # "Stay tuned for more updates on this story." on the thumbnail.
    return points[:3]


# ── TTS ───────────────────────────────────────────────────────────
TTS_TIMEOUT_S = float(os.environ.get("TTS_TIMEOUT_S", "45"))


# Per-voice TTS rate. edge-tts voices have noticeably different
# baseline tempos: British voices read slower (Sonia/Ryan), Brazilian
# Portuguese voices faster than US English. A single global +3% nudge
# (the old default) made Sonia sound stately and Antonio panicked.
# These offsets are tuned by ear to land each voice in the 30-45s
# range for a 100-word script. Missing entries fall through to +3%.
VOICE_RATE_OFFSETS = {
    # English
    "en-US-JennyNeural": "+3%",  # baseline
    "en-US-AriaNeural": "+4%",
    "en-US-GuyNeural": "+2%",
    "en-US-ChristopherNeural": "+1%",
    "en-US-RogerNeural": "+1%",
    "en-US-SteffanNeural": "+2%",
    "en-GB-SoniaNeural": "+6%",  # British — naturally slower
    "en-GB-RyanNeural": "+6%",
    "en-AU-NatashaNeural": "+3%",
    # Portuguese (Brazil) — already brisk; we slow down slightly
    "pt-BR-FranciscaNeural": "+0%",
    "pt-BR-AntonioNeural": "-2%",  # the calmest of the three
    "pt-BR-ThalitaNeural": "+0%",
    # Spanish + French
    "es-ES-ElviraNeural": "+2%",
    "es-ES-AlvaroNeural": "+2%",
    "es-MX-DaliaNeural": "+2%",
    "es-MX-JorgeNeural": "+2%",
    "fr-FR-DeniseNeural": "+4%",
    "fr-FR-HenriNeural": "+4%",
}

VOICE_PITCH_OFFSETS = {
    "en-US-ChristopherNeural": "-2Hz",
    "en-US-RogerNeural": "-1Hz",
}


def _locale_from_voice(voice: str) -> str:
    match = re.match(r"^([a-z]{2}-[A-Z]{2})-", str(voice or ""))
    return match.group(1) if match else LANGUAGE


async def text_to_speech(text: str, output_path: Path, voice: str = VOICE_SHORT, rate_override: str | None = None):
    """
    Render `text` to `output_path` (MP3) via Microsoft Edge-TTS.

    Wrapped in asyncio.wait_for so a hung WebSocket can't pin the whole
    Short generation. The previous version (no timeout) would silently
    hang for up to the workflow's full 30-min budget if edge-tts's CDN
    blipped — that meant zero Shorts shipped that day. We raise on
    timeout so the caller logs the failure and moves on to the next
    story.

    Each voice gets its own rate offset (see VOICE_RATE_OFFSETS) — a
    single global nudge made British voices sound stately and Brazilian
    voices panicked. `rate_override` lets the caller (the hook-slow
    path) inject a specific rate without rebuilding the panel.
    """
    import edge_tts

    rate = rate_override or VOICE_RATE_OFFSETS.get(voice, "+3%")
    pitch = VOICE_PITCH_OFFSETS.get(voice, "+0Hz")
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    try:
        await asyncio.wait_for(
            communicate.save(str(output_path)),
            timeout=TTS_TIMEOUT_S,
        )
    except Exception:
        fallback = synthesize_with_coqui(text, output_path, _locale_from_voice(voice))
        if fallback:
            log.info("  TTS recovered with local Coqui-compatible fallback")
            return
        raise


async def text_to_speech_hook_then_body(
    hook: str, body: str, output_path: Path, voice: str = VOICE_SHORT, tmp_dir: Path | None = None
) -> bool:
    """Render the hook at the voice's "calm" baseline rate (4 % slower
    than the body), then the body at the voice's regular rate. The
    two MP3 segments are FFmpeg-concatenated into `output_path`.

    Why: the first 3 s decide whether a viewer swipes or stays. A
    rushed hook is the single biggest "swiped before they understood"
    failure mode. Reading the hook ~4 % slower than the body gives
    viewers time to comprehend the lead without making the whole
    Short feel slow.

    Returns True on success. False = caller should fall back to the
    one-shot text_to_speech with the full script.
    """
    if not hook or not body or not tmp_dir:
        return False
    body_rate = VOICE_RATE_OFFSETS.get(voice, "+3%")
    # Compute a "calm" rate ~4 percentage points below body_rate.
    try:
        body_pp = int(body_rate.rstrip("%"))
    except ValueError:
        body_pp = 3
    hook_pp = body_pp - 4
    hook_rate = f"{hook_pp:+d}%" if hook_pp != 0 else "+0%"

    hook_mp3 = tmp_dir / "_hook.mp3"
    body_mp3 = tmp_dir / "_body.mp3"
    try:
        await text_to_speech(hook, hook_mp3, voice, rate_override=hook_rate)
        await text_to_speech(body, body_mp3, voice, rate_override=body_rate)
    except Exception as exc:
        log.warning("hook/body TTS split failed: %s", exc)
        return False
    if not (hook_mp3.exists() and body_mp3.exists()):
        return False
    # Concat with FFmpeg's concat demuxer (lossless for MP3).
    list_file = tmp_dir / "_concat.txt"
    list_file.write_text(
        f"file '{hook_mp3.resolve()}'\nfile '{body_mp3.resolve()}'\n",
        encoding="utf-8",
    )
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False
    if r.returncode != 0:
        log.warning("hook/body MP3 concat failed: %s", r.stderr[-200:].decode("utf-8", errors="replace"))
        return False
    log.info("  🎤 Hook @ %s, body @ %s (split-rate)", hook_rate, body_rate)
    return True


# ── Legacy AI metadata + script builders removed ─────────────────
#
# `_ai_shorts_meta`, `_ai_shorts_hook`, and `build_short_script` used
# to round-trip Mistral for title/hook/script generation, but every
# pending story in the queue is now pre-enriched by fetch_animals.py with
# `seo_title`, `hook`, `script`, `thumbnail_text`, `yt_tags`, etc.
# Keeping the legacy paths would burn extra free-tier tokens and create
# divergent metadata between the queue and the upload sidecar. Removed
# May 2026 as part of the b-roll + captions pivot.


def _render_solid_color_background(category: str, dest: Path) -> bool:
    """Synthesise a category-coloured vertical gradient as the
    background-of-last-resort. The b-roll path is the actual visual
    content; this just backs the thumbnail and the static-frame
    compose when every image source above failed.

    Returns True iff the file was written and is larger than the 5KB
    sanity floor downstream checks. Single-file PIL draw — no network,
    no external command, so this never fails except on totally broken
    Python installs (in which case the whole pipeline is dead anyway).
    """
    base = CATEGORY_COLORS.get((category or "").upper(), ACCENT_BLUE)
    bg = Image.new("RGB", (SHORT_W, SHORT_H), (12, 14, 22))
    draw = ImageDraw.Draw(bg)
    # Linear gradient: dark navy at top → category color at bottom.
    # Keeps the title-card text band readable while signalling the
    # topic visually. One horizontal line per row is ~2000× faster
    # than a per-pixel loop and finishes in ~30 ms at 1080×1920.
    for y in range(SHORT_H):
        t = y / max(1, SHORT_H - 1)
        r = int(12 * (1 - t) + base[0] * t * 0.45)
        g = int(14 * (1 - t) + base[1] * t * 0.45)
        b = int(22 * (1 - t) + base[2] * t * 0.45)
        draw.line([(0, y), (SHORT_W, y)], fill=(r, g, b))
    bg.save(str(dest), "JPEG", quality=88, optimize=True)
    return dest.exists() and dest.stat().st_size > 5 * 1024


# ── Frame vertical do Short ───────────────────────────────────────
def _legacy_title_card_frame(
    title: str, category: str, points: list[str], source: str, bg_path: Path | None
) -> Image.Image:
    """
    Create a single 1080x1920 vertical frame for a YouTube Short.
    Layout (top to bottom):
      - AI background + dark overlay
      - Category badge (top ~10%)
      - Story title (center, ~25-55%)
      - 3 bullet points (middle, ~55-80%)
      - Wild Brief branding (bottom ~85-95%)
    """
    img = Image.new("RGB", (SHORT_W, SHORT_H), BG_DARK)

    # ── Background ───────────────────────────────────────────────
    if bg_path and bg_path.exists():
        try:
            bg = Image.open(bg_path).convert("RGB")
            bw, bh = bg.size
            # Crop to 9:16 vertical ratio
            target_ratio = SHORT_W / SHORT_H
            img_ratio = bw / bh
            if img_ratio > target_ratio:
                # Too wide: crop sides
                new_w = int(bh * target_ratio)
                off = (bw - new_w) // 2
                bg = bg.crop((off, 0, off + new_w, bh))
            else:
                # Too tall: crop top/bottom
                new_h = int(bw / target_ratio)
                off = (bh - new_h) // 2
                bg = bg.crop((0, off, bw, off + new_h))
            bg = bg.resize((SHORT_W, SHORT_H), Image.LANCZOS)
            img.paste(bg)
        except Exception:
            pass

    # ── Dark overlay for readability ─────────────────────────────
    overlay = Image.new("RGBA", (SHORT_W, SHORT_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Gradient: lighter at top, darker in text zones
    for i in range(SHORT_H):
        t = i / SHORT_H
        # Top 15%: moderate overlay
        # Middle 60%: heavy overlay for text
        # Bottom 20%: heavy overlay for branding
        if t < 0.15:
            alpha = 120
        elif t < 0.75:
            alpha = int(160 + 50 * ((t - 0.15) / 0.60))
        else:
            alpha = 210
        od.line([(0, i), (SHORT_W, i)], fill=(0, 0, 10, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    cat_color = CATEGORY_COLORS.get(category.upper(), ACCENT_BLUE)
    padding = 48

    # ── Category badge (top area) ─────────────────────────────────
    cat_text = category.upper()
    cat_font = get_font(52, bold=True)
    cbbox = draw.textbbox((0, 0), cat_text, font=cat_font)
    badge_w = cbbox[2] + 48
    badge_h = cbbox[3] + 24
    badge_x = (SHORT_W - badge_w) // 2
    badge_y = 120
    draw_rounded_rect(draw, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), radius=14, fill=(*cat_color, 230))
    draw.text((badge_x + 24, badge_y + 12), cat_text, font=cat_font, fill=(0, 0, 0))

    # ── LIVE dot ─────────────────────────────────────────────────
    live_font = get_font(38, bold=True)
    live_y = badge_y + badge_h + 28
    live_text = "NATURE BRIEF"
    lbbox = draw.textbbox((0, 0), live_text, font=live_font)
    lx = (SHORT_W - lbbox[2]) // 2
    draw.text((lx, live_y), live_text, font=live_font, fill=RED_LIVE)

    # ── Story title (large, centered) ────────────────────────────
    title_start_y = int(SHORT_H * 0.22)
    title_font = get_font(72, bold=True)
    title_max_w = SHORT_W - padding * 2
    title_lines = wrap_text(draw, title, title_font, title_max_w)

    # If title too long, use smaller font
    if len(title_lines) > 4:
        title_font = get_font(58, bold=True)
        title_lines = wrap_text(draw, title, title_font, title_max_w)

    line_height = 88
    ty = title_start_y
    for line in title_lines[:4]:
        lbbox = draw.textbbox((0, 0), line, font=title_font)
        lx = (SHORT_W - lbbox[2]) // 2
        # Shadow
        draw.text((lx + 3, ty + 3), line, font=title_font, fill=(0, 0, 0))
        # Text
        draw.text((lx, ty), line, font=title_font, fill=TEXT_WHITE)
        ty += line_height

    # ── Divider line ─────────────────────────────────────────────
    div_y = ty + 24
    draw.line([(padding, div_y), (SHORT_W - padding, div_y)], fill=(*cat_color, 150), width=3)

    # ── 3 bullet points ───────────────────────────────────────────
    bullet_start_y = div_y + 36
    bullet_font = get_font(46)
    bullet_max_w = SHORT_W - padding * 2 - 60  # 60 for bullet icon
    bullet_labels = ["01", "02", "03"]
    bullet_spacing = 16  # vertical gap between bullets

    by = bullet_start_y
    for idx, point in enumerate(points[:3]):
        # Bullet number badge
        num_font = get_font(36, bold=True)
        num_text = bullet_labels[idx]
        nbbox = draw.textbbox((0, 0), num_text, font=num_font)
        num_w = nbbox[2] + 16
        num_h = nbbox[3] + 10
        draw_rounded_rect(draw, (padding, by, padding + num_w, by + num_h), radius=8, fill=cat_color)
        draw.text((padding + 8, by + 5), num_text, font=num_font, fill=(0, 0, 0))

        # Bullet text
        blines = wrap_text(draw, point, bullet_font, bullet_max_w)
        text_x = padding + num_w + 16
        text_y = by
        for bline in blines[:3]:
            draw.text((text_x, text_y), bline, font=bullet_font, fill=TEXT_WHITE)
            text_y += 52

        by = max(by + num_h + bullet_spacing, text_y + bullet_spacing)

    # ── Bottom branding ───────────────────────────────────────────
    brand_y = int(SHORT_H * 0.88)

    # Horizontal line
    draw.line([(padding, brand_y), (SHORT_W - padding, brand_y)], fill=(*ACCENT_BLUE, 80), width=2)

    # Logo text — channel name lockup on the title card.
    logo_font = get_font(54, bold=True)
    brand_y2 = brand_y + 24
    draw.text((padding, brand_y2), "WILD", font=logo_font, fill=ACCENT_BLUE)
    gbbox = draw.textbbox((0, 0), "WILD", font=logo_font)
    sep_x = padding + gbbox[2] + 12
    draw.rectangle([(sep_x, brand_y2 + 4), (sep_x + 4, brand_y2 + gbbox[3] - 4)], fill=(*ACCENT_BLUE, 180))
    draw.text((sep_x + 16, brand_y2), "BRIEF", font=logo_font, fill=TEXT_WHITE)

    # Source
    src_font = get_font(36)
    src_y = brand_y2 + 68
    draw.text((padding, src_y), f"Source: {source}", font=src_font, fill=TEXT_GRAY)

    # CTA
    cta_font = get_font(38, bold=True)
    cta_text = "FOLLOW FOR ONE ANIMAL SIGNAL A DAY"
    cta_y = src_y + 48
    ctabbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    ctx = (SHORT_W - ctabbox[2]) // 2
    draw.text((ctx, cta_y), cta_text, font=cta_font, fill=ACCENT_CYAN)

    # Date stamp
    date_font = get_font(32)
    date_str = datetime.now().strftime("%b %d, %Y")
    dbbox = draw.textbbox((0, 0), date_str, font=date_font)
    dx = SHORT_W - dbbox[2] - padding
    draw.text((dx, brand_y + 8), date_str, font=date_font, fill=TEXT_GRAY)

    return img.convert("RGB")


def create_short_frame(title: str, category: str, points: list[str], source: str, bg_path: Path | None) -> Image.Image:
    """
    Create a first frame that works as a Shorts cover: visible animal,
    compact visual cue, and small brand lockup.
    """
    img = Image.new("RGB", (SHORT_W, SHORT_H), BG_DARK)
    if bg_path and bg_path.exists():
        try:
            bg = Image.open(bg_path).convert("RGB")
            bw, bh = bg.size
            target_ratio = SHORT_W / SHORT_H
            img_ratio = bw / bh
            if img_ratio > target_ratio:
                new_w = int(bh * target_ratio)
                off = (bw - new_w) // 2
                bg = bg.crop((off, 0, off + new_w, bh))
            else:
                new_h = int(bw / target_ratio)
                off = (bh - new_h) // 2
                bg = bg.crop((0, off, bw, off + new_h))
            bg = bg.resize((SHORT_W, SHORT_H), Image.LANCZOS)
            bg = ImageEnhance.Brightness(bg).enhance(1.08)
            bg = ImageEnhance.Contrast(bg).enhance(1.12)
            bg = ImageEnhance.Color(bg).enhance(1.10)
            img.paste(bg)
        except Exception:
            pass

    overlay = Image.new("RGBA", (SHORT_W, SHORT_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    side_w = int(SHORT_W * 0.48)
    for x in range(side_w):
        t = x / max(1, side_w - 1)
        alpha = int(186 * (1 - t) + 16 * t)
        od.line([(x, 0), (x, SHORT_H)], fill=(0, 0, 0, alpha))
    for y in range(SHORT_H):
        t = y / max(1, SHORT_H - 1)
        alpha = int(18 + 132 * max(0.0, (t - 0.42) / 0.58))
        od.line([(0, y), (SHORT_W, y)], fill=(0, 0, 0, alpha))
    od.rectangle((0, 0, SHORT_W, 210), fill=(0, 0, 0, 36))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img, "RGBA")
    cat_color = CATEGORY_COLORS.get(category.upper(), ACCENT_BLUE)
    padding = 70

    brand_font = get_font(38, bold=True)
    draw.text(
        (padding, 92),
        "WILD BRIEF",
        font=brand_font,
        fill=(*TEXT_WHITE, 235),
        stroke_width=3,
        stroke_fill=(0, 0, 0, 190),
    )
    cat_text = (category or "nature").replace("_", " ").upper()[:18]
    cat_font = get_font(30, bold=True)
    cat_box = draw.textbbox((0, 0), cat_text, font=cat_font)
    draw.text(
        (SHORT_W - cat_box[2] - padding, 102),
        cat_text,
        font=cat_font,
        fill=(*cat_color, 245),
        stroke_width=2,
        stroke_fill=(0, 0, 0, 180),
    )

    cue = _clean_thumbnail_text("", title=title, hook=points[0] if points else "")
    title_font = get_font(150, bold=True)
    title_lines = _side_caption_lines(draw, cue, title_font, int(SHORT_W * 0.48) - 112)
    if any((draw.textbbox((0, 0), line, font=title_font)[2] > int(SHORT_W * 0.48) - 112) for line in title_lines):
        title_font = get_font(130, bold=True)
        title_lines = _side_caption_lines(draw, cue, title_font, int(SHORT_W * 0.48) - 112)
    title_lines = title_lines[:3]
    line_h = 144 if len(title_lines) >= 3 else 164
    y = int(SHORT_H * 0.42) - (len(title_lines) * line_h // 2)
    for line in title_lines:
        draw.text(
            (padding, y),
            line,
            font=title_font,
            fill=(*TEXT_WHITE, 255),
            stroke_width=9,
            stroke_fill=(0, 0, 0, 220),
        )
        y += line_h

    tagline = _normalise_editorial_text(title)[:74].rstrip(" -.,")
    if tagline and tagline.upper() != cue:
        small_font = get_font(36, bold=True)
        sy = min(int(SHORT_H * 0.70), y + 26)
        for line in wrap_text(draw, tagline, small_font, int(SHORT_W * 0.48) - 112)[:3]:
            draw.text(
                (padding, sy),
                line,
                font=small_font,
                fill=(245, 248, 250, 235),
                stroke_width=4,
                stroke_fill=(0, 0, 0, 190),
            )
            sy += 54

    brand_y = SHORT_H - 196
    draw.rectangle((padding, brand_y, padding + 230, brand_y + 12), fill=(*cat_color, 255))
    lock_font = get_font(54, bold=True)
    draw.text(
        (padding, brand_y + 34),
        "WILD BRIEF",
        font=lock_font,
        fill=(*TEXT_WHITE, 250),
        stroke_width=3,
        stroke_fill=(0, 0, 0, 180),
    )
    src = (source or "").strip()
    if src:
        draw.text((padding, brand_y + 104), f"source: {src[:42]}", font=get_font(28), fill=(224, 230, 235, 185))

    return img.convert("RGB")


# ── Thumbnail do Short (frame-first side caption) ─────────────────
#
# Every new Short uses the format selected by the operator: a real still
# from the source footage whenever b-roll exists, one large scannable cue,
# and small Wild Brief branding. Static brand cards and solid color slabs
# are intentionally out of the production path.
THUMBNAIL_STYLE_VERSION = "frame_first_side_caption_v1"


# ── Video assembly (b-roll + captions + hook overlay) ────────────
#
# The composition itself moved to utils/video_compose.py so the two
# render paths (multi-clip motion or static-frame fallback) can be
# unit-tested in isolation. This wrapper is what `generate_short()`
# calls; it picks the right pipeline based on whether we actually
# acquired b-roll clips.


def _thumbnail_copy(thumbnail_text: str, fallback: str = "NATURE SIGNAL") -> str:
    """Return compact, readable thumbnail copy for a vertical preview tile."""
    return _clean_thumbnail_text(thumbnail_text, title=fallback)


def _side_caption_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = [word for word in text.split() if word]
    if not words:
        return []
    if len(words) <= 3:
        return words
    return wrap_text(draw, " ".join(words), font, max_width)[:3]


def create_short_thumbnail(frame_img: Image.Image, output: Path, thumbnail_text: str = "", category: str = "") -> None:
    """Render a frame-first thumbnail with a large side caption."""
    if frame_img is None:
        return
    thumb = frame_img.copy().convert("RGB").resize((SHORT_W, SHORT_H), Image.LANCZOS)
    thumb = ImageEnhance.Brightness(thumb).enhance(1.10)
    thumb = ImageEnhance.Contrast(thumb).enhance(1.14)
    thumb = ImageEnhance.Color(thumb).enhance(1.10)
    cat_color = CATEGORY_COLORS.get((category or "").upper(), ACCENT_BLUE)

    overlay = Image.new("RGBA", (SHORT_W, SHORT_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    side_w = int(SHORT_W * 0.48)
    for x in range(side_w):
        t = x / max(1, side_w - 1)
        alpha = int(192 * (1 - t) + 24 * t)
        od.line([(x, 0), (x, SHORT_H)], fill=(0, 0, 0, alpha))
    for y in range(SHORT_H):
        t = y / max(1, SHORT_H - 1)
        alpha = int(12 + 98 * max(0.0, (t - 0.58) / 0.42))
        od.line([(0, y), (SHORT_W, y)], fill=(0, 0, 0, alpha))
    thumb = Image.alpha_composite(thumb.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(thumb, "RGBA")

    copy = _thumbnail_copy(thumbnail_text)
    max_text_w = side_w - 112
    title_font = get_font(152, bold=True)
    lines = _side_caption_lines(draw, copy, title_font, max_text_w)
    if any((draw.textbbox((0, 0), line, font=title_font)[2] > max_text_w) for line in lines):
        title_font = get_font(132, bold=True)
        lines = _side_caption_lines(draw, copy, title_font, max_text_w)
    lines = lines[:3]
    line_h = 146 if len(lines) >= 3 else 166
    y = int(SHORT_H * 0.42) - (len(lines) * line_h // 2)
    for line in lines:
        draw.text(
            (64, y),
            line,
            font=title_font,
            fill=(*TEXT_WHITE, 255),
            stroke_width=10,
            stroke_fill=(0, 0, 0, 225),
        )
        y += line_h

    brand_x = 64
    brand_y = SHORT_H - 250
    draw.rectangle((brand_x, brand_y, brand_x + 214, brand_y + 12), fill=(*cat_color, 255))
    brand_font = get_font(50, bold=True)
    draw.text(
        (brand_x, brand_y + 34),
        "WILD BRIEF",
        font=brand_font,
        fill=(*TEXT_WHITE, 245),
        stroke_width=3,
        stroke_fill=(0, 0, 0, 175),
    )
    sub = (category or "nature science").replace("_", " ").upper()[:20]
    draw.text((brand_x, brand_y + 94), sub, font=get_font(30, bold=True), fill=(*cat_color, 250))

    thumb.save(str(output), "JPEG", quality=95, optimize=True)
    log.info("  Thumbnail (frame-first side caption): %s", output.name)


def _nature_broll_query(story: dict) -> str:
    """Build a conservative visual query for Wild Brief nature footage."""
    category = str(story.get("category", "")).strip().upper()
    category_query = NATURE_BROLL_QUERY_MAP.get(category, "nature science")
    tags = story.get("yt_tags") or []
    if isinstance(tags, str):
        tags = [tags]
    for tag in tags:
        clean = re.sub(r"[^A-Za-z -]", "", str(tag)).strip().lower()
        if clean and len(clean.split()) <= 3:
            return f"{clean} {category_query}"[:120]
    return category_query


def _animal_broll_query(story: dict) -> str:
    """Backward-compatible alias for the generic nature b-roll query."""
    return _nature_broll_query(story)


def _extract_broll_thumbnail(video_path: Path, dest: Path) -> bool:
    """Extract a still from the actual source footage for the thumbnail."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                "0.5",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(dest),
            ],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0 and dest.exists() and dest.stat().st_size >= 5 * 1024
    except Exception as exc:
        log.debug("broll thumbnail extraction failed: %s", exc)
        return False


def acquire_broll_clips(story: dict, tmp_dir: Path, want_n: int = 3) -> list[Path]:
    """
    Pull `want_n` b-roll MP4s into `tmp_dir`. Returns local paths.
    Empty list = the caller falls back to a static frame.

    The primary clip is the exact source clip stored with the story.
    Supplemental discovery is conservative and category-aligned.
    """
    if want_n <= 0:
        return []
    query = _nature_broll_query(story)
    if not query:
        return []
    category = story.get("category", "")
    animal_only = str(category).strip().lower() in {
        "cats",
        "dogs",
        "ocean",
        "wildlife",
        "birds",
        "farm",
        "reptiles",
        "insects",
        "primates",
        "nocturnal",
        "arctic",
    }
    try:
        candidates = fetch_broll_clips(
            query,
            want_n=want_n * 2,
            category=category,
            animal_only=animal_only,
        )
    except Exception as exc:
        log.debug("broll discovery failed: %s", exc)
        return []
    log.info("  🎬 B-roll candidates: %d (query=%r)", len(candidates), query[:80])

    preferred_url = (story.get("source_download_url") or story.get("pexels_download_url") or "").strip()
    if preferred_url:
        candidates.insert(
            0,
            BrollClip(
                source=(story.get("source") or "pexels").strip().lower(),
                url=(story.get("source_url") or "").strip(),
                download_url=preferred_url,
                width=1080,
                height=1920,
                duration_s=10.0,
                title=(story.get("title") or "").strip(),
                license=(story.get("source_license") or "Reusable source clip").strip(),
            ),
        )

    paths: list[Path] = []
    seen_urls: set[str] = set()
    for i, clip in enumerate(candidates):
        if len(paths) >= want_n:
            break
        if clip.download_url in seen_urls:
            continue
        seen_urls.add(clip.download_url)
        dest = tmp_dir / f"broll_{i}.mp4"
        if download_clip(clip, dest):
            paths.append(dest)
    log.info(
        "  🎬 B-roll downloaded: %d/%d (sources: %s)", len(paths), want_n, {c.source for c in candidates[: len(paths)]}
    )
    return paths


def generate_captions(audio_path: Path, tmp_dir: Path) -> Path | None:
    """Transcribe `audio_path` and emit an ASS subtitle file. None if both
    Whisper providers fail; callers should still ship the Short."""
    try:
        words = captions_transcribe(audio_path)
    except Exception as exc:
        log.warning("caption transcribe crashed: %s", exc)
        return None
    if not words:
        return None
    phrases = group_words_into_phrases(words, max_words=3, max_gap_s=0.45, max_duration_s=1.8)
    ass_path = tmp_dir / "captions.ass"
    if not write_ass(phrases, ass_path):
        return None
    return ass_path


# ── Tracking: quais posts já foram transformados em Short ────────
def load_shorts_done() -> set:
    VIDEOS_DIR.mkdir(exist_ok=True)
    if SHORTS_DONE_FILE.exists():
        try:
            data = json.loads(SHORTS_DONE_FILE.read_text(encoding="utf-8"))
            return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()
    return set()


def save_shorts_done(done: set):
    SHORTS_DONE_FILE.write_text(
        json.dumps(sorted(done), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Metadata for upload_youtube.py ───────────────────────────────
def build_short_metadata(story: dict, video_path: Path, thumb_path: Path) -> dict:
    """
    Build the JSON metadata payload that upload_youtube.py consumes.
    Required keys downstream: title, description, video.

    SEO inputs (already authored by fetch_animals.py's prompt and carried
    on the queue entry):

      story["title"]          — seo_title, 40-55 chars, front-loaded
      story["yt_tags"]        — 5 lowercase tags (kept name for queue
                                schema back-compat; we render them inline
                                as hashtags below)
      story["yt_description"] — 2-3 sentences ending with hashtag block

    YouTube limits we respect:
      - title: 100 characters
      - description: 5,000 characters
      - tags: a focused list for YouTube search and Shorts discovery
    """
    base_title = _normalise_editorial_text(story.get("title") or "")
    category = story.get("category", "wildlife")
    source = story.get("source", "Pexels")

    if not base_title:
        base_title = "Animal fact of the day"

    if len(base_title) > 100:
        base_title = base_title[:97].rstrip(" .,;:-") + "..."

    # ── YouTube Shorts hashtag block.
    # Keep the block focused: YouTube primarily needs #Shorts plus a
    # small set of topic tags.
    discovery = list(story.get("discovery_hashtags") or [])
    if not discovery:
        # Fallback for queue entries written before discovery_hashtags
        # landed: synthesise a reasonable set from category + topic.
        cat = (category or "nature").lower()
        topic_tag = (story.get("topic_hashtag") or category or "nature").lower()
        topic_tag = "".join(ch for ch in topic_tag if ch.isalnum())
        discovery = [cat, topic_tag, "naturefacts", "earthscience", "science"]
    final_tags = merge_hashtags(discovery)
    hashtag_block = " ".join(f"#{t}" for t in final_tags)

    raw_desc = (story.get("yt_description") or "").strip()
    # Rebuild the hashtag line to avoid carrying stale queue tags.
    cleaned = []
    for line in raw_desc.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and all(p.startswith("#") for p in stripped.split()):
            continue  # drop pure hashtag lines authored for YouTube
        cleaned.append(line)
    body = "\n".join(cleaned).rstrip()
    if not body:
        lead = story.get("description") or story.get("script") or ""
        body = f"{base_title}. {lead}".strip()[:380] + f"\n\nSource: {source}"

    caption = f"{body}\n\n{hashtag_block}"[:5000]

    # Tag list kept for analytics back-compat (the digest + dashboard
    # both read `meta['tags']`).
    queue_tags = [t for t in (story.get("yt_tags") or []) if isinstance(t, str)]
    all_tags = merge_search_tags(queue_tags, category)

    seo = seo_score(base_title, subject=str(story.get("subject") or ""), category=category)
    created_at = datetime.now(timezone.utc)
    temporal = temporal_fields(now=created_at)
    metadata = {
        "title": base_title,
        "description": caption,
        "tags": all_tags,
        "youtube_privacy": "public",
        "youtube_category_id": "28",
        "thumbnail": str(thumb_path),
        "video": str(video_path),
        "story_slug": story.get("slug", ""),
        "created_at": created_at.isoformat(),
        "publish_ts_utc": temporal["publish_ts_utc"],
        "publish_day_pt": temporal["publish_day_pt"],
        "quota_day_pt": temporal["quota_day_pt"],
        "views_regime": temporal["views_regime"],
        "script": story.get("script", "").strip(),
        "thumbnail_text": story.get("thumbnail_text", "").strip(),
        "thumbnail_hook": story.get("thumbnail_text", "").strip(),
        "hook": story.get("hook", "").strip(),
        "story_format": story.get("story_format")
        or classify_format(f"{base_title} {story.get('hook', '')} {story.get('script', '')}", category=category),
        "hook_audit": audit_hook(story.get("hook", "")).to_dict(),
        "title_audit": audit_title(base_title).to_dict(),
        "seo_score": seo,
        "human_voice": score_human_voice(story.get("script", "")).to_dict(),
        "humanity": score_humanity_story(story).to_dict(),
        "studio_polish": dict(story.get("studio_polish") or {}),
        "ai_rewrite": dict(story.get("ai_rewrite") or {}),
        "seo_optimisation": dict(story.get("seo_optimisation") or {}),
        "narrator_voice": story.get("narrator_voice", ""),
        "narrator_profile": dict(((story.get("growth_studio") or {}).get("narrator")) or {}),
        "narrative_template": dict(story.get("narrative_template") or {}),
        "growth_studio": dict(story.get("growth_studio") or {}),
        "production_mode": story.get("production_mode", ""),
        "youtube_brain": dict(story.get("youtube_brain") or {}),
        "packaging": dict(story.get("packaging") or {}),
        "curiosity_gap": dict((story.get("packaging") or {}).get("curiosity_gap") or {}),
        "swipe_risk": dict((story.get("packaging") or {}).get("swipe_risk") or {}),
        "loop_plan": dict((story.get("packaging") or {}).get("loop_plan") or {}),
        "loop_score": (story.get("packaging") or {}).get("loop_score", 0),
        "loop_render_applied": dict(story.get("loop_render_applied") or {}),
        "end_card_text": story.get("end_card_text", ""),
        "editorial_rulebook": dict((story.get("packaging") or {}).get("editorial_rulebook") or {}),
        "opportunity_score": dict(story.get("opportunity_score") or {}),
        "retention_score": dict(story.get("retention_score") or {}),
        "weak_content": dict(story.get("weak_content") or {}),
        "subscriber_conversion": dict(story.get("subscriber_conversion") or {}),
        "pinned_comment": (story.get("packaging") or {}).get("pinned_comment", ""),
        "cta_prompt": story.get("cta_prompt") or (story.get("packaging") or {}).get("cta_prompt", ""),
        "replay_prompt": story.get("replay_prompt") or (story.get("packaging") or {}).get("replay_prompt", ""),
        "trend_context": dict(story.get("trend_context") or {}),
        "agency": dict(story.get("agency") or {}),
        "agency_gate": dict(story.get("agency_gate") or {}),
        "audience_strategy": global_strategy(),
        "retention_surgery": diagnose_retention(story),
        # Vertical 9:16 + short duration = a YouTube Short.
        "is_short": True,
        # Pexels source-clip identity. Propagated so upload_youtube can
        # append it to the permanent dedup ledger
        # (`_data/published_clips.json`) on a successful upload.
        "pexels_video_id": story.get("pexels_video_id", ""),
        "pexels_download_url": story.get("pexels_download_url", ""),
        "source_clip_id": story.get("source_clip_id", ""),
        "source_download_url": story.get("source_download_url", ""),
        "source_license": story.get("source_license", ""),
        "source_license_evidence": story.get("source_license_evidence", ""),
        "source_creator": story.get("source_creator", ""),
        "source_collection": story.get("source_collection", ""),
        "rights_policy": story.get("rights_policy", ""),
        "commons_page_url": story.get("commons_page_url", ""),
        "commons_license": story.get("commons_license", ""),
        "commons_artist": story.get("commons_artist", ""),
        "gbif": dict(story.get("gbif") or {}),
        # Queue entry id (SHA-256-derived Pexels page URL). Second dedup
        # key after pexels_video_id; whichever the recorder has is fine.
        "story_id": story.get("id", ""),
        # Source metadata (kept for analytics / dashboard).
        "source": source,
        "source_url": story.get("source_url", ""),
        "geo_hashtag": story.get("geo_hashtag", "Global"),
        "category": category,
        # channel_handle is kept on the metadata for the .done sidecar /
        # analytics joins even when the on-frame watermark is disabled.
        "channel_handle": (os.environ.get("CHANNEL_WATERMARK", "").strip() or "@wildbrief"),
        # A/B variant tags ride along all the way to the .done sidecar
        # after upload so analytics can correlate them with engagement.
        "experiments": dict(story.get("experiments") or {}),
        "music_bed_variant": story.get("music_bed_variant", ""),
        "music_bed_track": dict(story.get("music_bed_track") or {}),
        "autonomy": dict(story.get("autonomy") or {}),
        "editorial": dict(story.get("editorial") or {}),
        "queue_prune": dict(story.get("queue_prune") or {}),
        "publish_score": dict(story.get("publish_score") or {}),
        "studio_state": story.get("studio_state") or (story.get("editorial") or {}).get("state", ""),
        "series": story.get("series", ""),
    }
    metadata["story_pattern"] = classify_story_pattern(metadata)
    metadata["hook_library"] = choose_hook_template(metadata)
    metadata["hook_library_score"] = score_hook(metadata.get("hook", ""), metadata)
    metadata["payoff_control"] = score_payoff(metadata.get("script", ""), metadata.get("hook", ""))
    metadata["payoff_second"] = metadata["payoff_control"].get("payoff_second", 0)
    metadata["loop_semantics"] = score_loop_semantics(metadata.get("script", ""), metadata.get("hook", ""))
    metadata["loop_density"] = metadata["loop_semantics"].get("loop_density", 0)
    metadata["callback_keyword_overlap"] = metadata["loop_semantics"].get("callback_keyword_overlap", 0)
    metadata["claim_risk"] = evaluate_claim_risk(metadata)
    metadata["rights_guard"] = evaluate_rights_guard(metadata)
    metadata["search_enrichment"] = enrich_search_terms(metadata)
    metadata["seo_lint"] = lint_metadata(metadata)
    metadata["editorial_guard"] = editorial_verdict(metadata)
    return metadata


# ── Parse posts ──────────────────────────────────────────────────
QUEUE_FILE = Path("_data/stories_queue.json")


@contextlib.contextmanager
def _queue_file_lock():
    """
    Cross-process advisory lock on the queue file. Held while we
    read-modify-write to mark a story consumed, so a concurrent
    fetch_animals.py append doesn't clobber the consumed flag (or vice
    versa). Mirror of fetch_animals.py::_file_lock.
    """
    if fcntl is None:
        yield
        return
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = QUEUE_FILE.with_suffix(".json.lock")
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
    """Read _data/stories_queue.json — schema written by fetch_animals.py."""
    if not QUEUE_FILE.exists():
        return {"stories": []}
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning(f"Failed to parse {QUEUE_FILE}: {exc}")
        return {"stories": []}


def _save_queue(queue: dict) -> None:
    """Atomic write — temp file + rename."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(QUEUE_FILE)


def _candidate_identity_values(story: dict) -> set[str]:
    return {
        str(value).strip()
        for value in (
            story.get("id"),
            story.get("_queue_id"),
            story.get("slug"),
            story.get("source_clip_id"),
        )
        if str(value or "").strip()
    }


def _matches_publish_window_candidate(story: dict, target_id: str | None = None) -> bool:
    target = (target_id or PUBLISH_WINDOW_TOP_CANDIDATE_ID).strip()
    return bool(target) and target in _candidate_identity_values(story)


def _prioritize_publish_window_candidate(candidates: list[dict], target_id: str | None = None) -> list[dict]:
    target = (target_id or PUBLISH_WINDOW_TOP_CANDIDATE_ID).strip()
    if not target:
        return candidates
    selected = [item for item in candidates if _matches_publish_window_candidate(item, target)]
    if not selected:
        log.error("Publish window selected %s, but no matching candidate survived generator gates.", target)
        return [] if PUBLISH_WINDOW_SELECTED_ONLY else candidates
    if PUBLISH_WINDOW_SELECTED_ONLY:
        log.info("  Publish window selected candidate enforced: %s", target)
        return selected[:1]
    return selected + [item for item in candidates if not _matches_publish_window_candidate(item, target)]


def _loop_enhanced_script(story: dict, script: str) -> str:
    """Apply LoopGenerator's final callback line to the rendered narration."""
    text = (script or "").strip()
    plan = (story.get("packaging") or {}).get("loop_plan") or {}
    final_line = _normalise_editorial_text(plan.get("final_line") or "")
    if not text or not final_line:
        return text
    tail = _normalise_editorial_text(text[-220:]).lower()
    if final_line.lower() in tail:
        return text
    if len(final_line.split()) > 14:
        return text
    story["loop_render_applied"] = {
        "final_line": final_line,
        "callback_keyword": plan.get("callback_keyword", ""),
        "source": "loop_plan",
    }
    return f"{text.rstrip()} {final_line}"


def _end_card_text_for_story(story: dict) -> str:
    """Choose the visual CTA/end-card copy from measured experiment axes."""
    experiments = story.get("experiments") or {}
    cta_pattern = experiments.get("cta_pattern", "identity_follow")
    end_card_style = experiments.get("end_card_style", "subscribe_clean")
    loop_plan = (story.get("packaging") or {}).get("loop_plan") or {}
    callback = _normalise_editorial_text(loop_plan.get("callback_keyword") or "").upper()
    if end_card_style == "loop_callback" and callback and callback != "CUE":
        return f"WATCH THE {callback} AGAIN"[:34]
    if end_card_style == "series_tease" or cta_pattern == "sequel_tease":
        return "NEXT WILD SIGNAL"
    if cta_pattern == "question_tease":
        return "COMMENT THE NEXT QUESTION"
    return "FOLLOW FOR WILD NATURE"


def _queue_to_story(qs: dict) -> dict:
    """
    Map a queue entry to the dict shape `generate_short()` expects.
    Falls back to source-feed metadata when the AI fields are missing.
    """
    title = _normalise_editorial_text(qs.get("seo_title") or qs.get("title", ""))
    thumbnail_text = _clean_thumbnail_text(
        qs.get("thumbnail_text", ""),
        title=title,
        hook=qs.get("hook", ""),
    )
    experiments = assign_all_for_production(qs["id"])
    experiments.update(dict(qs.get("experiments") or {}))
    story = {
        "slug": f'{(qs.get("published_at") or qs.get("fetched_at",""))[:10]}-{qs["id"]}',
        "title": title,
        "description": qs.get("description", ""),
        "lead": qs.get("lead", ""),
        "raw_title": qs.get("title", ""),
        "source": qs.get("source", "Pexels"),
        "source_url": qs.get("source_url") or qs.get("url", ""),
        "image_url": qs.get("image_url", ""),
        "tags": [qs.get("category", "wildlife")],
        "category": qs.get("category", "wildlife"),
        "date": (qs.get("published_at") or qs.get("fetched_at", ""))[:10],
        "hook": qs.get("hook", ""),
        # `script` is the full opinionated voice-over (~30-45 s) authored
        # by fetch_animals.py's AI prompt. generate_short() will TTS this
        # directly instead of rebuilding from key_points.
        "script": qs.get("script", ""),
        "thumbnail_text": thumbnail_text,
        "key_points": qs.get("key_points", []),
        # SEO fields authored by fetch_animals.py — used as-is by
        # build_short_metadata. Each is allowed to be empty; the
        # metadata builder falls back to safe defaults.
        "yt_tags": qs.get("yt_tags", []),
        "yt_description": qs.get("yt_description", ""),
        "geo_hashtag": qs.get("geo_hashtag", ""),
        "topic_hashtag": qs.get("topic_hashtag", ""),
        "discovery_hashtags": list(qs.get("discovery_hashtags") or []),
        "score": qs.get("score", 0),
        "autonomy": dict(qs.get("autonomy") or {}),
        "experiments": experiments,
        "pexels_download_url": qs.get("pexels_download_url", ""),
        "pexels_video_id": qs.get("pexels_video_id", ""),
        "source_clip_id": qs.get("source_clip_id", ""),
        "source_download_url": qs.get("source_download_url", ""),
        "source_license": qs.get("source_license", ""),
        "publish_score": dict(qs.get("publish_score") or {}),
        "queue_prune": dict(qs.get("queue_prune") or {}),
        "editorial": dict(qs.get("editorial") or {}),
        "rights_audit": dict(qs.get("rights_audit") or {}),
        "local_rewrite": dict(qs.get("local_rewrite") or {}),
        "trend_context": dict(qs.get("trend_context") or {}),
        "commons_image_url": qs.get("commons_image_url", ""),
        "commons_page_url": qs.get("commons_page_url", ""),
        "commons_license": qs.get("commons_license", ""),
        "commons_artist": qs.get("commons_artist", ""),
        "gbif": dict(qs.get("gbif") or {}),
        "id": qs["id"],
        "_queue_id": qs["id"],  # used to mark consumed after success
    }
    story = package_story(story)
    growth_studio = studio_brief_for_story(story)
    narrator_variant = (growth_studio.get("narrator") or {}).get("variant", "")
    if narrator_variant:
        story["experiments"]["narrator_voice"] = narrator_variant
    story["growth_studio"] = growth_studio
    story["narrative_template"] = growth_studio.get("narrative_template") or {}
    story["production_mode"] = growth_studio.get("production_mode", "")
    story["youtube_brain"] = creator_premortem(story)
    # Keep queue adaptation deterministic and cheap. AI rescue happens
    # only when a candidate is actually attempted for production.
    return optimise_story(polish_story(story))


def _has_publish_ready_supply_reserve(story: dict) -> bool:
    queue_prune = story.get("queue_prune") or {}
    objective_reasons = {str(reason) for reason in (queue_prune.get("objective_reasons") or [])}
    publish = story.get("publish_score") or {}
    reserve = publish.get("reserve_override") or {}
    return (
        PUBLISH_READY_SUPPLY_RESERVE_FALLBACK in objective_reasons
        or reserve.get("reason") == PUBLISH_READY_SUPPLY_RESERVE_FALLBACK
    )


def _opportunity_allowed_for_reserve(opportunity: dict | None) -> bool:
    if not opportunity:
        return True
    reasons = {str(reason) for reason in (opportunity.get("reasons") or [])}
    return not (reasons - RESERVE_ALLOWED_OPPORTUNITY_REASONS)


def _apply_publish_ready_supply_reserve_score(story: dict, score: dict) -> dict:
    out = dict(score)
    out["reserve_override"] = {
        "reason": PUBLISH_READY_SUPPLY_RESERVE_FALLBACK,
        "original_approved": score.get("approved"),
        "original_state": score.get("state"),
        "original_opportunity_reasons": list((score.get("opportunity") or {}).get("reasons") or []),
    }
    out["approved"] = True
    out["state"] = "publish_ready"
    story["publish_score"] = out
    return out


def _can_apply_publish_ready_supply_reserve(
    story: dict,
    *,
    score: dict | None = None,
    opportunity: dict | None = None,
    weak: dict | None = None,
    brain: dict | None = None,
    packaging: dict | None = None,
) -> bool:
    if not _has_publish_ready_supply_reserve(story):
        return False
    if production_quality_issues(story):
        return False
    editorial = story.get("editorial") or {}
    if editorial and editorial.get("approved") is not True and not _has_editorial_cooldown_supply_fallback(story):
        return False
    rights = story.get("rights_audit") or {}
    if rights and (rights.get("approved") is False or rights.get("warnings")):
        return False
    if opportunity and not _opportunity_allowed_for_reserve(opportunity):
        return False
    if weak and weak.get("state") == "block":
        return False
    if score:
        if score.get("state") == "reject":
            return False
        if float(score.get("score", 0) or 0) < RESERVE_MIN_PUBLISH_SCORE:
            return False
    if brain and (brain.get("state") != "publish_minded" or brain.get("risks")):
        return False
    if packaging and (packaging.get("state") == "rewrite_packaging" or packaging.get("risks")):
        return False
    return True


def load_pending_stories() -> tuple[list[dict], dict]:
    """
    Return (pending_stories, raw_queue). Pending = not yet consumed AND
    not already shipped to YouTube (`shorts_done` tracks the latter,
    handled by the caller). Stories sorted by AI quality score desc.
    """
    queue = _load_queue()
    pruned_queue, pruned_rejections, prune_summary = prune_queue(queue, analytics_strategy=load_strategy())
    if pruned_queue != queue:
        queue = pruned_queue
        _save_queue(queue)
    if pruned_rejections:
        for item in pruned_rejections:
            record_rejection(item["story"], item["reasons"], stage=item.get("stage", "queue_prune"))
        log.info(
            "  Queue pruned: %d -> %d pending (%d rejected)",
            prune_summary["pending_before"],
            prune_summary["pending_after"],
            prune_summary["rejected"],
        )
    stories = queue.get("stories", [])
    pending = [s for s in stories if not s.get("consumed")]
    seen_scripts: set[str] = set()
    clean_pending: list[dict] = []
    held_reasons: dict[str, int] = {}
    rescued_pending: list[dict] = []
    for story in pending:
        issues = _queue_story_quality_issues(story, seen_scripts=seen_scripts)
        if issues:
            rescued, applied = rescue_story(story, issues)
            if applied:
                retry_issues = _queue_story_quality_issues(rescued, seen_scripts=seen_scripts)
                if not retry_issues:
                    rescued_pending.append(rescued)
                    clean_pending.append(rescued)
                    continue
                issues = retry_issues
            for issue in issues:
                held_reasons[issue] = held_reasons.get(issue, 0) + 1
            log.warning(
                "  Holding queue story %s - %s",
                story.get("id") or story.get("title", "")[:60],
                ", ".join(issues),
            )
            record_rejection(story, issues)
            continue
        queue_prune = story.get("queue_prune") or {}
        if queue_prune and queue_prune.get("state") != "publish_ready":
            held_reasons["queue_prune_not_publish_ready"] = held_reasons.get("queue_prune_not_publish_ready", 0) + 1
            continue
        clean_pending.append(story)
    if held_reasons:
        log.info(
            "  Queue quality held %d candidate(s): %s",
            len(pending) - len(clean_pending),
            ", ".join(f"{k}={v}" for k, v in sorted(held_reasons.items())),
        )
    if rescued_pending:
        log.info("  Queue quality rescued %d candidate(s) with local rewrites", len(rescued_pending))
    pending = clean_pending
    pending.sort(
        key=lambda s: (
            float((s.get("autonomy") or {}).get("priority", 0) or 0),
            bool(s.get("breaking", False)),
            int(s.get("score", 0) or 0),
            s.get("fetched_at", ""),
        ),
        reverse=True,
    )
    candidates = [_queue_to_story(s) for s in pending]
    strategy = load_strategy()
    format_memory = load_format_memory()
    scored_candidates: list[dict] = []
    for candidate in candidates:
        opportunity = score_topic(candidate, memory=format_memory)
        if opportunity["verdict"] == "discard" and not _can_apply_publish_ready_supply_reserve(
            candidate, opportunity=opportunity
        ):
            record_rejection(
                candidate, opportunity.get("reasons") or ["low_opportunity_score"], stage="opportunity_score"
            )
            continue
        weak = detect_weak_content(candidate, memory=format_memory)
        if weak["state"] == "block":
            record_rejection(candidate, weak.get("reasons") or ["weak_content"], stage="weak_content")
            continue
        retention = analyze_retention(candidate)
        if retention["verdict"] == "discard":
            rescued, applied = rescue_story(candidate, retention.get("reasons") or ["retention_discard"])
            if applied:
                candidate = rescued
                retention = analyze_retention(candidate)
            if retention["verdict"] == "discard":
                record_rejection(
                    candidate, retention.get("reasons") or ["low_retention_score"], stage="retention_score"
                )
                continue
        score = publish_score_story(candidate, analytics_strategy=strategy)
        if _can_apply_publish_ready_supply_reserve(candidate, score=score, opportunity=opportunity, weak=weak):
            score = _apply_publish_ready_supply_reserve_score(candidate, score)
        if score["state"] == "reject":
            record_rejection(candidate, [f"publish_score_{score['state']}"], stage="publish_score")
            continue
        item = dict(candidate)
        item["opportunity_score"] = opportunity
        item["retention_score"] = retention
        item["weak_content"] = weak
        item["publish_score"] = score
        item = package_story(item)
        brain = creator_premortem(item)
        packaging = item.get("packaging") or {}
        if brain["state"] == "do_not_publish":
            record_rejection(item, brain.get("risks") or [], stage="youtube_brain")
            continue
        brain_risks = list(brain.get("risks") or [])
        packaging_risks = list(packaging.get("risks") or [])
        if (
            brain["state"] == "rewrite_before_publish"
            or packaging.get("state") == "rewrite_packaging"
            or brain_risks
            or packaging_risks
        ):
            reasons = list(
                dict.fromkeys(
                    brain_risks
                    + packaging_risks
                    + (["rewrite_packaging"] if packaging.get("state") == "rewrite_packaging" else [])
                )
            )
            rescued, applied = rescue_story(item, reasons)
            if applied:
                item = package_story(rescued)
                brain = creator_premortem(item)
                packaging = item.get("packaging") or {}
            if brain["state"] != "publish_minded" or brain.get("risks") or packaging.get("state") == "rewrite_packaging" or packaging.get("risks"):
                record_rejection(item, reasons, stage="youtube_brain_rewrite")
                continue
        if _can_apply_publish_ready_supply_reserve(
            item,
            score=item.get("publish_score") or {},
            opportunity=opportunity,
            weak=weak,
            brain=brain,
            packaging=packaging,
        ):
            item["publish_score"] = _apply_publish_ready_supply_reserve_score(item, item.get("publish_score") or {})
        item["youtube_brain"] = brain
        scored_candidates.append(item)
    candidates = scored_candidates
    if ops_guardian_enforced():
        paused = set(paused_categories().keys())
        if paused:
            before = len(candidates)
            candidates = [story for story in candidates if str(story.get("category") or "").lower() not in paused]
            log.info("  Ops guardian enforcement removed %d paused-category candidate(s)", before - len(candidates))
    publish_window_target = PUBLISH_WINDOW_TOP_CANDIDATE_ID
    candidates, held = filter_candidates(candidates)
    if publish_window_target:
        selected_soft_holds = [
            item
            for item in held
            if _matches_publish_window_candidate(item, publish_window_target)
            and is_soft_agency_hold((item.get("agency_gate") or {}).get("reasons") or [])
        ]
        selected_hard_holds = [
            item
            for item in held
            if _matches_publish_window_candidate(item, publish_window_target)
            and not is_soft_agency_hold((item.get("agency_gate") or {}).get("reasons") or [])
        ]
        if selected_soft_holds:
            reasons = sorted(
                {
                    str(reason)
                    for item in selected_soft_holds
                    for reason in (item.get("agency_gate") or {}).get("reasons", [])
                }
            )
            log.info(
                "  Publish window recovered soft agency hold for %s: %s",
                publish_window_target,
                ", ".join(reasons),
            )
            candidates.extend(selected_soft_holds)
        elif selected_hard_holds:
            reasons = sorted(
                {
                    str(reason)
                    for item in selected_hard_holds
                    for reason in (item.get("agency_gate") or {}).get("reasons", [])
                }
            )
            log.error(
                "Publish window selected %s, but agency gate held it for hard reasons: %s",
                publish_window_target,
                ", ".join(reasons),
            )
            if PUBLISH_WINDOW_SELECTED_ONLY:
                return [], queue
    if held:
        log.info(
            "  Agency gate held %d candidate(s): %s",
            len(held),
            ", ".join(
                sorted({reason for item in held for reason in (item.get("agency_gate") or {}).get("reasons", [])})
            )[:160],
        )
    growth_ranked = rank_for_growth(rank_candidates(candidates), strategy)
    agency_ranked = rank_for_agency(growth_ranked, strategy)
    agency_ranked.sort(key=lambda item: publish_priority_key(item), reverse=True)
    agency_ranked = _prioritize_publish_window_candidate(agency_ranked, publish_window_target)
    return agency_ranked, queue


def diversify_candidates(candidates: list[dict]) -> list[dict]:
    """Round-robin categories while preserving quality order within each one."""
    buckets: dict[str, list[dict]] = {}
    order: list[str] = []
    for candidate in candidates:
        category = candidate.get("category") or "wildlife"
        if category not in buckets:
            buckets[category] = []
            order.append(category)
        buckets[category].append(candidate)
    diversified: list[dict] = []
    while any(buckets.values()):
        for category in order:
            if buckets[category]:
                diversified.append(buckets[category].pop(0))
    return diversified


def mark_consumed(queue: dict, queue_id: str) -> None:
    """Mutate queue: flag the matching story as consumed=true (in memory)."""
    if not queue_id:
        log.warning("mark_consumed called with empty queue_id — skipping")
        return
    for s in queue.get("stories", []):
        if s.get("id") == queue_id:
            s["consumed"] = True
            s["consumed_at"] = datetime.now(timezone.utc).isoformat()
            return
    log.warning(f"mark_consumed: story id {queue_id} not found in queue (lost?)")


def mark_rejected(queue: dict, queue_id: str, reasons: list[str], *, stage: str) -> None:
    """Mutate queue: flag a blocked story as consumed with rejection metadata."""
    if not queue_id:
        log.warning("mark_rejected called with empty queue_id - skipping")
        return
    stamp = datetime.now(timezone.utc).isoformat()
    for story in queue.get("stories", []):
        if story.get("id") == queue_id:
            story["consumed"] = True
            story["consumed_at"] = stamp
            story["rejected_at"] = stamp
            story["rejection_stage"] = stage
            story["rejection_reasons"] = list(dict.fromkeys(str(reason) for reason in reasons))
            return
    log.warning("mark_rejected: story id %s not found in queue", queue_id)


def commit_consumed(queue_id: str) -> None:
    """
    Atomic read-mark-write: under the cross-process lock, reload the
    queue from disk (a concurrent fetch_animals.py may have appended new
    stories since we loaded it), mark this story consumed, save.
    This is the only safe way to persist `consumed: true` when
    fetch_animals.py and generate_shorts.py can interleave.
    """
    with _queue_file_lock():
        disk_queue = _load_queue()
        mark_consumed(disk_queue, queue_id)
        _save_queue(disk_queue)


def commit_rejected(queue_id: str, reasons: list[str], *, stage: str) -> None:
    """Atomic read-mark-write for candidates blocked during generation."""
    with _queue_file_lock():
        disk_queue = _load_queue()
        mark_rejected(disk_queue, queue_id, reasons, stage=stage)
        _save_queue(disk_queue)


# ── Gera um único Short ───────────────────────────────────────────
def _has_editorial_cooldown_supply_fallback(story: dict) -> bool:
    queue_prune = story.get("queue_prune") or {}
    objective_reasons = {str(reason) for reason in (queue_prune.get("objective_reasons") or [])}
    editorial = story.get("editorial") or {}
    return (
        EDITORIAL_COOLDOWN_SUPPLY_FALLBACK in objective_reasons
        or editorial.get("override") == EDITORIAL_COOLDOWN_SUPPLY_FALLBACK
    )


def generate_short(story: dict, tmp_dir: Path) -> tuple[Path, Path, dict] | None:
    """
    Generate one Short for a story.

    Pipeline (preferred path):
      1. TTS audio from the queue's `script` field
      2. b-roll: up to 3 related animal clips from Pexels
      3. captions: Groq Whisper → ASS file with word-level phrases
      4. compose: FFmpeg concats b-roll, burns captions + hook overlay
      5. thumbnail: dynamic, using AI-authored `thumbnail_text`
      6. metadata: from queue's seo_title / yt_tags / yt_description

    Fallback (b-roll unavailable):
      • Render a category-coloured static background with no unrelated
        or generated imagery.
      • Compose with a static-frame FFmpeg pipeline; captions still burn.

    Returns (video_path, thumb_path, metadata) or None on failure.
    """
    # Defensive .get()s on the story dict — a queue entry with a bad
    # schema would crash the whole run otherwise.
    slug = story.get("slug") or f"unknown-{int(time.time())}"
    date_str = story.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = story.get("title") or "Animal fact of the day"
    category = story.get("category", "wildlife")

    log.info(f"  Generating Short for: [{category}] {title[:60]}")

    # English channel ignores stories from PT-BR-native feeds — they're
    # enriched in Portuguese by fetch_animals.py and would need a costly
    # back-translation. Cleaner to skip and let the PT-BR pipeline
    # render them natively.
    native = (story.get("native_lang") or "en").lower()
    if LANGUAGE == "en" and native != "en":
        log.info("  ⏭  Skipping for English channel — story is native %s", native)
        return None

    # Sibling-language channel: translate the AI-authored fields first.
    # The translation already runs through ai_cache so repeat runs of
    # the same story don't double the Mistral burn.
    if LANGUAGE != "en":
        # NATIVE-LANGUAGE FAST PATH: when the story originated from a
        # PT-BR feed (G1, UOL, Folha, etc.) tagged native_lang=pt-BR,
        # fetch_animals.py already enriched it in Portuguese. Skipping
        # translate_story here means zero extra AI calls AND higher
        # editorial quality (no round-trip translation artefacts).
        native = (story.get("native_lang") or "en").lower()
        if native == LANGUAGE.lower():
            log.info("  🇧🇷 Native %s source — no translation needed", LANGUAGE)
            # Still stamp voice_tag so pick_voice walks the locale panel.
            story = dict(
                story,
                language=LANGUAGE,
                voice_tag=SUPPORTED_LANGUAGES[LANGUAGE]["voice_tag"],
                lang_hashtag=SUPPORTED_LANGUAGES[LANGUAGE]["hashtag"],
            )
        else:
            translated = translate_story(story, LANGUAGE)
            if not translated:
                log.warning("  ⏭  Skipping Short — translation to %s failed for %s", LANGUAGE, title[:60])
                return None
            story = translated
            log.info("  🌍 Translated to %s — voice=%s", LANGUAGE, story.get("voice_tag"))
        title = story.get("title") or story.get("seo_title") or title
        slug = f"{slug}-{LANGUAGE.lower().replace('-', '')}"

    # Queue carries pre-enriched fields when fetch_animals.py is up to date.
    # We require `script` (the full opinionated voice-over) to proceed —
    # backlog stories that predate the schema get rejected here.
    queue_script = (story.get("script") or "").strip()
    if not queue_script:
        log.warning("  ⏭  Skipping Short — no AI script on queue entry: %s", title[:80])
        return None

    story = optimise_story(rewrite_if_needed(story))
    queue_script = _loop_enhanced_script(story, story.get("script") or queue_script)
    story["script"] = queue_script

    # The editor-in-chief is stricter than the script linter: it also
    # considers thumbnail readability, source footage and recent channel
    # memory before spending free-tier resources on rendering.
    editorial_override = _has_editorial_cooldown_supply_fallback(story)
    editorial = editorial_review(story)
    story["series"] = editorial.series
    if not editorial.approved and editorial_override and editorial.state == "cooldown_subject":
        story["editorial"] = {
            **editorial.to_dict(),
            "approved": True,
            "state": "publish_now",
            "override": EDITORIAL_COOLDOWN_SUPPLY_FALLBACK,
            "original_approved": editorial.approved,
            "original_state": editorial.state,
            "original_reasons": list(editorial.reasons),
        }
    else:
        story["editorial"] = editorial.to_dict()
    if not story["editorial"].get("approved"):
        log.warning(
            "  Skipping Short - editor-in-chief rejected score=%d subject=%s reasons=%s",
            editorial.score,
            editorial.subject,
            "; ".join(editorial.reasons),
        )
        record_rejection(story, editorial.reasons, stage="editor_in_chief")
        commit_rejected(story.get("_queue_id", ""), editorial.reasons, stage="editor_in_chief")
        return None

    # ── Pre-flight quality gate ──────────────────────────────────
    # Catch AI-tell phrases, weak hooks, and wire-copy rewrites
    # BEFORE we burn TTS / b-roll / FFmpeg time. The case-study
    # research is unanimous: shipping unchecked LLM output is what
    # got the terminated channels terminated. Skipping a bad Short
    # is always cheaper than getting flagged.
    grade, issues = evaluate_script(story)
    if issues:
        log.info("  📋 Script quality grade=%d/10 — %d issue(s):", grade, len(issues))
        for issue in issues:
            log.info("     [%s/%s] %s", issue.severity, issue.code, issue.message)
    if quality_should_block(issues):
        log.warning(
            "  ⏭  Skipping Short — quality gate blocks: %s (grade=%d, blocks=%d, warns=%d)",
            title[:60],
            grade,
            sum(1 for i in issues if i.severity == "block"),
            sum(1 for i in issues if i.severity == "warn"),
        )
        return None
    hook_text = _normalise_editorial_text(story.get("hook") or "")
    display_title = _normalise_editorial_text(story.get("title") or "")  # already seo_title from queue
    thumbnail_text = _clean_thumbnail_text(
        story.get("thumbnail_text") or "",
        title=display_title,
        hook=hook_text,
    )
    story["hook"] = hook_text
    story["title"] = display_title
    story["thumbnail_text"] = thumbnail_text

    # ── 1. TTS narration ──────────────────────────────────────────
    script = humanize_for_tts(queue_script)
    audio_path = tmp_dir / f"audio_{slug}.mp3"
    # Translated stories carry a `voice_tag` (e.g. "pt-BR") set by
    # utils.translation.translate_story. English stories don't set it,
    # so pick_voice falls through to the default panel.
    voice_tag = story.get("voice_tag", "")
    narrator_variant = ((story.get("growth_studio") or {}).get("narrator") or {}).get("variant") or (
        story.get("experiments") or {}
    ).get("narrator_voice", "")
    voice = pick_voice(
        seed_text=title,
        category=category,
        voice_tag=voice_tag,
        narrator_variant=narrator_variant,
    )
    story["narrator_voice"] = voice
    story["story_format"] = story.get("story_format") or classify_format(
        f"{display_title} {hook_text} {queue_script}", category=category
    )
    log.info(f"  🎤 Voice: {voice}{' [' + voice_tag + ']' if voice_tag else ''}")

    # Split-rate TTS: render the hook at a calmer rate (≈ 4 pp slower)
    # then the rest of the script at the voice's regular rate. The
    # script always opens with the hook verbatim (fetch_animals.py's
    # prompt enforces this), so we can split on the hook itself.
    split_rendered = False
    if hook_text and queue_script.lstrip().lower().startswith(hook_text.lower()):
        body_after = queue_script[len(hook_text) :].lstrip(" .!?")
        body_humanised = humanize_for_tts(body_after)
        if body_humanised:
            try:
                split_rendered = asyncio.run(
                    text_to_speech_hook_then_body(
                        hook=humanize_for_tts(hook_text),
                        body=body_humanised,
                        output_path=audio_path,
                        voice=voice,
                        tmp_dir=tmp_dir,
                    )
                )
            except Exception as exc:
                log.warning("hook/body split TTS errored: %s — falling back", exc)
                split_rendered = False

    if not split_rendered:
        try:
            asyncio.run(text_to_speech(script, audio_path, voice))
            size_kb = audio_path.stat().st_size / 1024
            log.info(f"  TTS generated ({size_kb:.0f} KB)")
        except Exception as e:
            log.error(f"  TTS failed: {e}")
            if voice != VOICE_SHORT:
                try:
                    log.info("  Retrying TTS with default voice…")
                    asyncio.run(text_to_speech(script, audio_path, VOICE_SHORT))
                    log.info(f"  TTS recovered with {VOICE_SHORT}")
                except Exception as e2:
                    log.error(f"  TTS retry failed: {e2}")
                    return None
            else:
                return None

    # ── 1.4. Intro / outro wrap with the host's recurring lines. ─
    # Pre-rendered once per voice and cached under
    # `_data/intro_outro_cache/`. Wild Brief skips a spoken intro so
    # the hook starts immediately, then adds the subscribe sign-off.
    audio_path = wrap_with_intro_outro(
        body_audio=audio_path,
        voice=voice,
        tmp_dir=tmp_dir,
        text_to_speech_fn=text_to_speech,
        outro_line=story.get("cta_prompt") or None,
    )

    # ── 1.5. Music bed (background, ducked under narration). ─
    # Music is opt-in for the Pexels-only restart. The helper is a no-op
    # when disabled or when no safe asset can be downloaded, so generation
    # never fails just because music is absent.
    before_music = audio_path
    audio_path = add_music_bed(audio_path, story, tmp_dir)
    story["music_bed_variant"] = "light_bed" if audio_path != before_music else "off"

    # ── 2. Captions (word-level) — biggest single retention lever. ─
    ass_path = generate_captions(audio_path, tmp_dir)
    if not ass_path and QUALITY_REQUIRE_CAPTIONS:
        log.warning("  Skipping Short - production quality requires captions")
        return None
    if ass_path:
        log.info("  📝 Captions ready: %s", ass_path.name)
    else:
        log.info("  ⚠ Captions skipped — Whisper providers unavailable")

    # ── 3. B-roll discovery + download ────────────────────────────
    # Four short, tightly-related clips beat a slow three-shot montage
    # for nature/science Shorts: there is a new visual beat roughly
    # every 3-5 seconds while the exact source clip still leads.
    broll_paths = acquire_broll_clips(story, tmp_dir, want_n=4)
    if not broll_paths and QUALITY_REQUIRE_MOTION_BROLL:
        log.warning("  Skipping Short - production quality requires motion b-roll")
        return None

    # ── 4. Output paths ───────────────────────────────────────────
    VIDEOS_DIR.mkdir(exist_ok=True)
    video_path = VIDEOS_DIR / f"short-{slug}-{date_str}.mp4"
    thumb_path = VIDEOS_DIR / f"short-{slug}-{date_str}_thumb.jpg"

    # ── 5. Background image (always needed for thumbnail; sometimes
    # also for the static-frame video pipeline fallback). The b-roll
    # path doesn't use this for video but we still need a still for
    # the thumbnail composition.
    bg_path = tmp_dir / f"bg_{slug}.jpg"
    visual_ctr = {
        "checked": False,
        "approved": True,
        "score": 0,
        "reason": "no_broll_for_ctr_frame_selection",
    }
    img_ok = False
    if broll_paths:
        visual_ctr = select_best_frame(broll_paths[0], tmp_dir)
        best_frame = str(visual_ctr.get("best_frame") or "")
        if best_frame and Path(best_frame).exists():
            try:
                shutil.copyfile(best_frame, bg_path)
                img_ok = bg_path.exists() and bg_path.stat().st_size >= 5 * 1024
            except Exception as exc:
                log.debug("best CTR frame copy failed: %s", exc)
                img_ok = False
        if not img_ok:
            img_ok = _extract_broll_thumbnail(
                broll_paths[0],
                bg_path,
            )
    if not img_ok:
        img_ok = download_commons_image(story, bg_path)

    # Final-fallback: synthesise a category-coloured gradient so a story
    # without usable animal footage NEVER introduces a random person,
    # object, or generated scene. This background only backs the
    # thumbnail and static-frame fallback compose.
    if not img_ok or not bg_path.exists() or bg_path.stat().st_size < 5 * 1024:
        try:
            img_ok = _render_solid_color_background(category, bg_path)
        except Exception as exc:
            log.warning("  ⚠ solid-colour bg fallback failed: %s", exc)
            img_ok = False

    if not img_ok or not bg_path.exists() or bg_path.stat().st_size < 5 * 1024:
        log.warning(
            "  ⏭  Skipping Short — every background source failed, "
            "including the solid-colour fallback (PIL not importable?): %s",
            title[:80],
        )
        return None

    local_visual_qa = evaluate_local_frame(bg_path)
    if local_visual_qa.get("checked") and not local_visual_qa.get("approved"):
        log.warning(
            "  Local visual QA warning score=%s reason=%s", local_visual_qa.get("score"), local_visual_qa.get("reason")
        )
    visual_qa = evaluate_frame(bg_path, story.get("title") or display_title)
    if visual_qa.get("checked") and not visual_qa.get("approved"):
        log.warning(
            "  Skipping Short - Gemini visual QA rejected frame: %s", visual_qa.get("reason", "subject mismatch")
        )
        return None
    if visual_qa.get("checked") and int(visual_qa.get("thumbnail_quality", 0) or 0) < QUALITY_MIN_VISUAL_QA_SCORE:
        log.warning(
            "  Skipping Short - Gemini visual QA score %s is below %s",
            visual_qa.get("thumbnail_quality"),
            QUALITY_MIN_VISUAL_QA_SCORE,
        )
        return None

    # Render the still frame used for (a) the static-video fallback,
    # and (b) the dynamic thumbnail base.
    points = extract_key_points(story.get("description", ""))
    frame = create_short_frame(
        title=display_title,
        category=category,
        points=points,
        source=story.get("source", "Pexels"),
        bg_path=bg_path,
    )
    frame_path = tmp_dir / f"frame_{slug}.png"
    frame.save(str(frame_path))

    # ── 6. Thumbnail: frame-first side caption ────────────────────
    # This is now a production standard, not an A/B bucket. A/B tests may
    # tune the cue text later, but the visual format stays locked.
    experiments = dict(story.get("experiments") or {})
    experiments["thumbnail_style"] = "frame_first_side_caption"
    story["experiments"] = experiments
    try:
        thumb_base = Image.open(bg_path).convert("RGB")
    except Exception:
        thumb_base = frame
    create_short_thumbnail(thumb_base, thumb_path, thumbnail_text=thumbnail_text, category=category)
    if not thumb_path.exists() or thumb_path.stat().st_size < 5 * 1024:
        log.warning("  ⏭  Skipping Short — thumbnail too small: %s", title[:80])
        return None

    # ── 7. Compose video (b-roll preferred, static fallback) ──────
    # Every Short closes with one unambiguous channel-growth action.
    cta_text = _end_card_text_for_story(story)
    story["end_card_text"] = cta_text
    # Brand-bug watermark. Disabled by default because a second channel
    # mark adds visual noise to a compact Shorts frame.
    # Set CHANNEL_WATERMARK=@yourhandle to opt back in (useful if you're
    # cross-posting the raw MP4 elsewhere).
    watermark_text = os.environ.get("CHANNEL_WATERMARK", "")
    if broll_paths:
        ok = build_broll_short(
            broll_paths=broll_paths,
            audio_path=audio_path,
            output_path=video_path,
            ass_subtitle_path=ass_path,
            hook_text=hook_text or display_title,
            cover_text=thumbnail_text,
            cta_text=cta_text,
            watermark_text=watermark_text,
        )
        if not ok and QUALITY_REQUIRE_MOTION_BROLL:
            log.warning("  Skipping Short - b-roll compose failed in strict production mode")
            return None
        if not ok:
            log.info("  ⤵ B-roll compose failed — falling back to static frame.")
            ok = build_static_short(
                frame_path=frame_path,
                audio_path=audio_path,
                output_path=video_path,
                ass_subtitle_path=ass_path,
                hook_text=hook_text or display_title,
                cover_text=thumbnail_text,
                cta_text=cta_text,
                watermark_text=watermark_text,
            )
    else:
        ok = build_static_short(
            frame_path=frame_path,
            audio_path=audio_path,
            output_path=video_path,
            ass_subtitle_path=ass_path,
            hook_text=hook_text or display_title,
            cover_text=thumbnail_text,
            cta_text=cta_text,
            watermark_text=watermark_text,
        )
    if not ok:
        return None

    # NOTE: the thumbnail was written earlier by `create_short_thumbnail`
    # using the branded Wild Brief placeholder. We deliberately do NOT
    # overwrite it with a frame from the composed video — the operator
    # prefers a consistent branded preview tile across the channel.

    # ── 8. Metadata JSON ──────────────────────────────────────────
    metadata = build_short_metadata(story, video_path, thumb_path)
    metadata["seo_lint"] = lint_metadata(metadata)
    if metadata["seo_lint"].get("strict") and not metadata["seo_lint"].get("approved"):
        log.warning(
            "  Skipping Short - SEO metadata lint rejected score=%s errors=%s",
            metadata["seo_lint"].get("score"),
            "; ".join(metadata["seo_lint"].get("errors") or []),
        )
        record_rejection(metadata, metadata["seo_lint"].get("errors") or [], stage="seo_metadata_lint")
        return None
    # Tag metadata as synthetic content for downstream disclosure tools.
    metadata["altered_content"] = True
    metadata["has_broll"] = bool(broll_paths)
    metadata["has_captions"] = bool(ass_path)
    metadata["local_visual_qa"] = local_visual_qa
    metadata["visual_qa"] = visual_qa
    metadata["visual_ctr"] = visual_ctr
    metadata["script_quality_grade"] = grade
    metadata["production_quality"] = {
        "motion_broll_required": QUALITY_REQUIRE_MOTION_BROLL,
        "captions_required": QUALITY_REQUIRE_CAPTIONS,
        "min_visual_qa_score": QUALITY_MIN_VISUAL_QA_SCORE,
    }
    effective_editorial = story.get("editorial") or editorial.to_dict()
    metadata["editorial"] = effective_editorial
    metadata["humanity"] = effective_editorial.get("humanity") or editorial.humanity
    metadata["studio_state"] = effective_editorial.get("state") or editorial.state
    metadata["series"] = effective_editorial.get("series") or editorial.series
    metadata["opening_audit"] = audit_opening_frames(
        {
            **metadata,
            "thumbnail_text": metadata.get("thumbnail_text") or story.get("thumbnail_text"),
            "has_broll": bool(broll_paths),
        }
    )
    metadata["opening_gate_v2"] = evaluate_opening_gate(
        {
            **metadata,
            "thumbnail_text": metadata.get("thumbnail_text") or story.get("thumbnail_text"),
            "has_broll": bool(broll_paths),
        }
    )
    if not metadata["opening_gate_v2"].get("approved", True):
        log.warning(
            "  Skipping Short - opening gate v2 blocked score=%s reasons=%s",
            metadata["opening_gate_v2"].get("score"),
            "; ".join(metadata["opening_gate_v2"].get("reasons") or []),
        )
        record_rejection(metadata, metadata["opening_gate_v2"].get("reasons") or [], stage="opening_gate_v2")
        return None
    if not metadata["opening_audit"].get("approved", True):
        log.warning(
            "  Skipping Short - opening audit rejected score=%s reasons=%s",
            metadata["opening_audit"].get("score"),
            "; ".join(metadata["opening_audit"].get("reasons") or []),
        )
        record_rejection(metadata, metadata["opening_audit"].get("reasons") or [], stage="opening_audit")
        return None
    metadata["monetization_audit"] = audit_monetization(metadata)
    metadata["rights_audit"] = audit_rights(metadata)
    metadata["rights_guard"] = evaluate_rights_guard(metadata)
    write_source_provenance(metadata)
    if metadata["rights_guard"].get("state") == "block" or (
        os.environ.get("RIGHTS_GUARD_MODE", "block").strip().lower() == "block"
        and metadata["rights_guard"].get("state") == "manual_review"
    ):
        log.warning(
            "  Skipping Short - rights guard blocked: %s",
            "; ".join(metadata["rights_guard"].get("reasons") or []),
        )
        record_rejection(metadata, metadata["rights_guard"].get("reasons") or [], stage="rights_guard")
        return None
    if not metadata["rights_audit"].get("approved"):
        log.warning(
            "  Skipping Short - rights audit rejected: %s",
            "; ".join(metadata["rights_audit"].get("reasons") or []),
        )
        record_rejection(metadata, metadata["rights_audit"].get("reasons") or [], stage="rights_audit")
        return None
    metadata["claim_risk"] = evaluate_claim_risk(metadata)
    metadata["editorial_guard"] = editorial_verdict(metadata)
    if not metadata["editorial_guard"].get("approved", True):
        log.warning(
            "  Skipping Short - editorial guard held copy: %s",
            "; ".join(metadata["editorial_guard"].get("issues") or []),
        )
        record_rejection(metadata, metadata["editorial_guard"].get("issues") or [], stage="editorial_guard")
        return None
    if metadata["claim_risk"].get("level") == "block" and os.environ.get("FACT_GUARD_MODE", "block").lower() == "block":
        log.warning("  Skipping Short - fact guard blocked unsupported claims")
        record_rejection(metadata, metadata["claim_risk"].get("high_risk_claims") or [], stage="fact_guard")
        return None
    metadata["frame_zero_packaging"] = score_frame_zero(metadata)
    metadata["originality_pack"] = build_originality_pack(metadata)
    if (
        not metadata["originality_pack"].get("complete")
        and os.environ.get("ORIGINALITY_PACK_MODE", "warn").lower() == "block"
    ):
        log.warning("  Skipping Short - originality pack incomplete")
        record_rejection(metadata, ["originality_pack_incomplete"], stage="originality_pack")
        return None
    write_originality_pack(metadata)
    metadata["pre_publish_audit"] = audit_publish_package(metadata)
    metadata["publish_score"] = score_metadata(metadata)
    metadata["youtube_brain"] = publish_brain(metadata)
    if _can_apply_publish_ready_supply_reserve(
        metadata,
        score=metadata["publish_score"],
        opportunity=metadata.get("opportunity_score") or {},
        weak=metadata.get("weak_content") or {},
        brain=metadata.get("youtube_brain") or {},
        packaging=metadata.get("packaging") or {},
    ):
        metadata["publish_score"] = _apply_publish_ready_supply_reserve_score(metadata, metadata["publish_score"])
    if metadata["youtube_brain"].get("state") in {"hold", "rewrite"}:
        log.warning(
            "  Skipping Short - YouTube brain held score=%s risks=%s",
            metadata["youtube_brain"].get("score"),
            "; ".join(metadata["youtube_brain"].get("risks") or []),
        )
        record_rejection(metadata, metadata["youtube_brain"].get("risks") or [], stage="youtube_brain")
        return None
    if not metadata["publish_score"].get("approved"):
        log.warning(
            "  Skipping Short - publish score rejected score=%s state=%s",
            metadata["publish_score"].get("score"),
            metadata["publish_score"].get("state"),
        )
        record_rejection(
            metadata, [f"publish_score_{metadata['publish_score'].get('state')}"], stage="final_publish_score"
        )
        return None
    if not metadata["pre_publish_audit"].get("approved"):
        log.warning(
            "  Skipping Short - final pre-publish audit rejected score=%s reasons=%s",
            metadata["pre_publish_audit"].get("score"),
            "; ".join(metadata["pre_publish_audit"].get("reasons") or []),
        )
        return None
    metadata["variant_assignment_log"] = record_variant_assignments(
        metadata.get("experiments") or {},
        story_id=metadata.get("story_id") or metadata.get("story_slug") or slug,
        video_id=metadata.get("video_id", ""),
        context={
            "category": metadata.get("category", ""),
            "series": metadata.get("series", ""),
            "story_format": metadata.get("story_format", ""),
        },
    )
    meta_path = video_path.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"  Metadata saved: {meta_path.name}")

    # ── 9. Channel memory: log this Short so future stories can
    # callback to it ("I covered this two weeks ago — here's the update").
    try:
        from utils.channel_memory import remember as _remember_story

        _remember_story(story)
    except Exception as exc:
        log.debug("channel_memory remember skipped: %s", exc)

    return video_path, thumb_path, metadata


# ── Principal ────────────────────────────────────────────────────
def main():
    # generate_shorts.py no longer calls the LLM at the top level —
    # `seo_title`, `script`, `hook`, `yt_tags`, `thumbnail_text` all
    # come from fetch_animals.py's queue. We DO still call Whisper for
    # captions and edge-tts for narration, but those happen inside
    # generate_short() on a per-story basis. The fail-fast checks
    # below catch the cases where the queue file itself is missing.
    from utils.panic import abort_if_halted

    abort_if_halted("generate_shorts")
    VIDEOS_DIR.mkdir(exist_ok=True)

    if not QUEUE_FILE.exists():
        log.error(f"{QUEUE_FILE} not found — run fetch_animals.py first.")
        sys.exit(2)

    shorts_done = load_shorts_done()
    log.info(f"Shorts already done: {len(shorts_done)}")

    candidates, queue = load_pending_stories()
    # Belt-and-braces: queue dedup already excludes consumed stories,
    # but shorts_done covers the case where a story was published to
    # YouTube but the workflow died before marking it consumed.
    candidates = [c for c in candidates if c["slug"] not in shorts_done]

    # Honour the operator's `/block <slug>` decisions from the daily
    # digest issue. utils/digest.py harvest_block_commands writes the
    # list to _data/blocked_slugs.json; we filter against it here so a
    # blocked story is silently dropped before any AI/render work.
    blocked = load_blocked_slugs()
    if blocked:
        before = len(candidates)
        candidates = [c for c in candidates if c["slug"] not in blocked and c.get("_queue_id", "") not in blocked]
        if before != len(candidates):
            log.info("🚫 Filtered out %d blocked stories (operator /block)", before - len(candidates))

    candidates = diversify_candidates(candidates)
    log.info(f"Queue has {len(candidates)} pending stor{'y' if len(candidates)==1 else 'ies'}.")
    if not candidates:
        log.info("Nothing to do.")
        if REQUIRE_SHORT_ON_PUBLISH:
            log.error(
                "Publish window required a Short, but no production-ready queue candidate survived quality gates."
            )
            sys.exit(1)
        return

    # Walk MORE candidates than we need so a single quality-gate
    # rejection or a transient generation failure (TTS hiccup, b-roll
    # download timeout, etc.) doesn't take the whole run to zero
    # published. We aim to PRODUCE `MAX_SHORTS_PER_RUN` successes and
    # we'll burn up to 5× that many candidates trying. With ~20+
    # pending stories in the queue at any given moment, 5 retries is
    # well under queue depth and worst-case adds maybe 30 seconds of
    # wasted AI work — far better than skipping the slot entirely.
    pool = candidates[: MAX_SHORTS_PER_RUN * 5]
    log.info(f"Aiming for {MAX_SHORTS_PER_RUN} Short(s) this run " f"(pool of {len(pool)} candidate(s) available):")
    for i, s in enumerate(pool[:MAX_SHORTS_PER_RUN], 1):
        log.info(f"  {i}. [{s['category']}] {s['title'][:70]}")

    tmp = Path(tempfile.mkdtemp(prefix="yt_shorts_"))

    created = 0
    attempted = 0
    for story in pool:
        if created >= MAX_SHORTS_PER_RUN:
            break
        attempted += 1
        result = generate_short(story, tmp)
        if result:
            video_path, thumb_path, metadata = result
            shorts_done.add(story["slug"])
            save_shorts_done(shorts_done)
            # Persist consumption back to the queue under the
            # cross-process lock so a concurrent fetch_animals.py append
            # can't undo it. We pass through commit_consumed() instead
            # of the bare _save_queue(queue) — that one would write our
            # stale in-memory copy and overwrite any fetch_animals flush.
            commit_consumed(story.get("_queue_id", ""))
            created += 1
            log.info(f"  Short ready: {video_path.name}")
            log.info(f"  YT title: {metadata['title'][:80]}")
        else:
            log.warning(f"  ⏭ Candidate skipped, trying next: {story.get('slug', '?')}")

    shutil.rmtree(tmp, ignore_errors=True)
    log.info(
        f"\nDone: {created}/{MAX_SHORTS_PER_RUN} Short(s) created "
        f"in {VIDEOS_DIR}/ ({attempted} candidate(s) attempted)."
    )

    # Observable failure signal: if we were asked to make Shorts and
    # produced zero, exit non-zero so the workflow turns red. Beats
    # "✅ success" on a day where no Short actually shipped.
    if pool and created == 0:
        log.error("❌ All Short generations failed. Exiting non-zero.")
        sys.exit(1)


if __name__ == "__main__":
    main()
