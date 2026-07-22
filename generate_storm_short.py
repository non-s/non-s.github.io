#!/usr/bin/env python3
"""Generate one vertical rain/thunder YouTube Short: the animated storm
short scene looped under a procedurally-synthesized rain/thunder bed, no
narration. Companion to generate_storm_ambience.py's long-form videos --
same storm pillar, same "rain sounds for sleep" search intent (see
utils/storm_branding.py's module docstring), short vertical format
instead.

Writes `_videos/storm-*.mp4` + matching `.json` that
upload_youtube.py's `_collect_pending_meta()` already picks up (extended
for generate_storm_ambience.py's own storm-prefixed markers).
"""

from __future__ import annotations

import json
import logging
import random
import subprocess  # noqa: F401  # re-exported for test monkeypatch
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ai_titling import generate_video_copy  # noqa: E402
from utils.ffmpeg_helpers import (  # noqa: E402
    compose_short,
    load_sidecar,
    media_duration_s,
    prepare_seamless_loop_clip,
)
from utils.storm_audio import generate_rain_bed, write_wav  # noqa: E402
from utils.storm_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title  # noqa: E402
from utils.title_history import select_title  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_storm_short")

# Backward-compat aliases (tests may import the _-prefixed names from this module).
_load_sidecar = load_sidecar
_media_duration_s = media_duration_s


def _prepare_seamless_loop_clip(clip_path: Path) -> Path:
    return prepare_seamless_loop_clip(clip_path, temp_dir=TEMP_DIR, loop_crossfade_s=LOOP_CROSSFADE_S, logger=log)


def _compose_short(broll_path: Path, rain_bed_path: Path, output_path: Path, duration_s: float) -> bool:
    return compose_short(
        broll_path,
        rain_bed_path,
        output_path,
        duration_s,
        target_w=TARGET_W,
        target_h=TARGET_H,
        fade_s=FADE_S,
        logger=log,
    )


# One fixed, real Pixabay clip (chat, 2026-07-21: the channel owner picked
# this specific rainy-porch-with-lantern clip by hand and asked for it to
# be the one clip this format always uses -- not a random pick from a
# pool) -- see _assets/video/pinned_storm_short_real.json for its
# source/license. Falls back to the illustrated pinned clip only if this
# file is ever missing.
PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_storm_short_real.mp4"
FALLBACK_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_storm_short_clip.mp4"
# A real frame extracted from PINNED_BROLL_CLIP itself (chat, 2026-07-22:
# see generate_storm_ambience.py's identical constant for the reasoning).
BRAND_THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "storm_short_thumbnail.jpg"
FALLBACK_THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "storm_short_scene_1080x1920.png"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_storm_short"

TARGET_W = 2160
TARGET_H = 3840
MIN_DURATION_S = 30.0
MAX_DURATION_S = 58.0
FADE_S = 1.5
LOOP_CROSSFADE_S = 1.0  # same value/technique as generate_storm_ambience.py's identical constant
RAIN_BED_SECONDS = 37.0  # short + non-matching period vs. the 14s video loop and the ambience pillar's 53s bed

CATEGORY = "storm_ambience"
SERIES_SUFFIX = "Shorts"
DEFAULT_TAGS = [
    "som de chuva",
    "chuva para dormir",
    "som de chuva para dormir",
    "trovão e chuva",
    "chuva forte",
    "chuva relaxante",
    "ruído branco",
    "amber hours",
]


def _pick_scene() -> str:
    return random.choice(list(HOOK_BY_SCENE.keys())).title()


def _prepare_rain_bed(seed: int) -> Path:
    bed_path = TEMP_DIR / f"rain_bed_short_{seed}.wav"
    if bed_path.exists() and bed_path.stat().st_size > 0:
        return bed_path
    bed = generate_rain_bed(duration_s=RAIN_BED_SECONDS, seed=seed, thunder_count=random.randint(0, 1))
    write_wav(bed, bed_path)
    return bed_path


def _build_metadata(scene: str, duration_s: float, video_path: Path, slug: str, *, broll_meta: dict) -> dict:
    template_title = branded_title(scene)
    bucket = playlist_bucket_for_title(template_title)

    disclosure = (
        "A chuva e o trovão deste vídeo são sintetizados por computador, não uma gravação em loop "
        "-- nenhuma amostra para se esgotar, nenhuma licença para verificar."
    )
    description_lines = [
        "Som real de chuva com trovão ao longe -- uma pausa rápida de chuva para relaxar.",
        "",
        f"\U0001f327️ Parte da coleção {bucket} no Amber Hours.",
        "",
        f"\U0001f3a7 {disclosure}",
        "",
        "#Shorts",
    ]

    tags = [scene.lower()] if scene.lower() not in {tag.lower() for tag in DEFAULT_TAGS} else []
    tags += DEFAULT_TAGS

    title = template_title
    description = "\n".join(description_lines).strip()

    ai_copy = generate_video_copy(
        format_label="vertical rain/thunder Short",
        scene=scene,
        duration_s=duration_s,
        fallback_title=template_title,
    )
    if ai_copy:
        variants = ai_copy.get("title_variants") or [ai_copy["title"]]
        title = select_title(variants)
        description = f"{ai_copy['description']}\n\n{disclosure}\n\n#Shorts".strip()
        tags = ai_copy["hashtags"]
        if "amber hours" not in tags:
            tags.append("amber hours")

    return {
        "title": title,
        "description": description,
        "category": CATEGORY,
        "series": f"{bucket} {SERIES_SUFFIX}",
        "tags": tags,
        "video": str(video_path),
        "duration_s": duration_s,
        "story_id": slug,
        "packaging": {"pinned_comment": "Como deveria ser o próximo Short de chuva? \U0001f327️"},
        "pre_publish_audit": {"approved": True, "reason": "storm_ambience_no_claims_to_vet"},
        "source": str(broll_meta.get("source") or "branding"),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
        "bgm_track_id": "",
        "bgm_license_ccurl": "",
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if PINNED_BROLL_CLIP.exists():
        broll_path = PINNED_BROLL_CLIP
    elif FALLBACK_BROLL_CLIP.exists():
        log.warning("Pinned real Short clip missing -- using the illustrated fallback.")
        broll_path = FALLBACK_BROLL_CLIP
    else:
        log.error(
            "No storm b-roll available: both %s and %s are missing.",
            PINNED_BROLL_CLIP,
            FALLBACK_BROLL_CLIP,
        )
        return 1

    broll_meta = _load_sidecar(broll_path)
    scene = _pick_scene()
    duration_s = round(random.uniform(MIN_DURATION_S, MAX_DURATION_S), 1)
    rain_bed_path = _prepare_rain_bed(seed=random.randint(0, 1_000_000))
    seamless_clip = _prepare_seamless_loop_clip(broll_path)

    slug = f"stormshort-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"storm-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    if not _compose_short(seamless_clip, rain_bed_path, video_path, duration_s):
        log.error("Storm Short composition failed for %s", slug)
        return 1

    metadata = _build_metadata(scene, duration_s, video_path, slug, broll_meta=broll_meta)
    if BRAND_THUMBNAIL_IMAGE.exists():
        metadata["thumbnail"] = str(BRAND_THUMBNAIL_IMAGE)
    elif FALLBACK_THUMBNAIL_IMAGE.exists():
        log.warning("Real thumbnail frame missing -- using the illustrated fallback.")
        metadata["thumbnail"] = str(FALLBACK_THUMBNAIL_IMAGE)
    else:
        log.warning("No thumbnail image available -- YouTube will auto-pick a frame.")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.1fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
