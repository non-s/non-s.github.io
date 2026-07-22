#!/usr/bin/env python3
"""Generate one vertical white/pink/brown-noise YouTube Short: a real,
calm Pixabay nursery/night clip looped under procedurally-synthesized
noise-color audio, no narration. Companion to
generate_baby_noise_ambience.py's long-form videos -- see that module's
docstring and utils/noise_audio.py's module docstring for the full
pillar reasoning.

Writes `_videos/noise-*.mp4` + matching `.json` that
upload_youtube.py's `_collect_pending_meta()` picks up (extended to
recognize the "noise-" prefix).
"""

from __future__ import annotations

import json
import logging
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ai_titling import generate_baby_noise_copy  # noqa: E402
from utils.baby_noise_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title  # noqa: E402
from utils.broll import pick_noise_broll_file  # noqa: E402
from utils.ffmpeg_helpers import (  # noqa: E402
    compose_short as _compose_short_impl,
    extract_thumbnail_frame,
    load_sidecar,
    media_duration_s,
    prepare_seamless_loop_clip,
)
from utils.noise_audio import NOISE_COLORS, generate_noise_bed, write_wav  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_baby_noise_short")

# Backward-compat aliases (tests may import the _-prefixed names from this module).
_load_sidecar = load_sidecar
_media_duration_s = media_duration_s


def _prepare_seamless_loop_clip(clip_path: Path) -> Path:
    return prepare_seamless_loop_clip(
        clip_path, temp_dir=TEMP_DIR, loop_crossfade_s=LOOP_CROSSFADE_S, logger=log
    )


def _extract_thumbnail_frame(clip_path: Path, seed: int) -> Path | None:
    return extract_thumbnail_frame(clip_path, seed, temp_dir=TEMP_DIR, logger=log)


def _compose_short(broll_path: Path, noise_bed_path: Path, output_path: Path, duration_s: float) -> bool:
    return _compose_short_impl(
        broll_path,
        noise_bed_path,
        output_path,
        duration_s,
        target_w=TARGET_W,
        target_h=TARGET_H,
        fade_s=FADE_S,
        logger=log,
    )

NOISE_BROLL_DIR = ROOT / "_assets" / "video" / "noise_broll"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_baby_noise_short"

TARGET_W = 2160
TARGET_H = 3840
MIN_DURATION_S = 30.0
MAX_DURATION_S = 58.0
FADE_S = 1.5
LOOP_CROSSFADE_S = 1.0
NOISE_BED_SECONDS = 29.0  # short + non-matching period, same reasoning as generate_storm_short.py's identical constant

CATEGORY = "baby_noise_ambience"
SERIES_SUFFIX = "Shorts"
DEFAULT_TAGS = [
    "ruído branco",
    "ruído branco bebê",
    "ruído marrom",
    "ruído rosa",
    "som para bebê dormir",
    "ruído branco para dormir",
    "ruído branco para estudar",
    "amber hours",
]


def _pick_scene() -> str:
    return random.choice(list(HOOK_BY_SCENE.keys())).title()


def _pick_color() -> str:
    return random.choice(sorted(NOISE_COLORS))


def _prepare_noise_bed(seed: int, color: str) -> Path:
    bed_path = TEMP_DIR / f"noise_bed_short_{color}_{seed}.wav"
    if bed_path.exists() and bed_path.stat().st_size > 0:
        return bed_path
    bed = generate_noise_bed(duration_s=NOISE_BED_SECONDS, seed=seed, color=color)
    write_wav(bed, bed_path)
    return bed_path


def _build_metadata(
    scene: str, color: str, duration_s: float, video_path: Path, slug: str, *, broll_meta: dict
) -> dict:
    template_title = branded_title(scene)
    bucket = playlist_bucket_for_title(template_title)

    color_label = {"white": "branco", "pink": "rosa", "brown": "marrom"}[color]
    disclosure = (
        f"O ruído {color_label} deste vídeo é sintetizado por computador, não uma gravação em loop "
        "-- nenhuma amostra para se esgotar, nenhuma licença para verificar."
    )
    description_lines = [
        f"Ruído {color_label} real -- uma pausa rápida de som constante para relaxar, focar ou acalmar.",
        "",
        f"\U0001f50a Parte da coleção {bucket} no Amber Hours.",
        "",
        f"\U0001f3a7 {disclosure}",
        "",
        "#Shorts",
    ]

    tags = [scene.lower()] if scene.lower() not in {tag.lower() for tag in DEFAULT_TAGS} else []
    tags += DEFAULT_TAGS

    title = template_title
    description = "\n".join(description_lines).strip()

    ai_copy = generate_baby_noise_copy(
        scene=scene,
        color=color,
        duration_s=duration_s,
        fallback_title=template_title,
    )
    if ai_copy:
        title = ai_copy["title"]
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
        "packaging": {
            "pinned_comment": "Qual cor de ruído funciona melhor pra você: branco, rosa ou marrom? \U0001f50a"
        },
        "pre_publish_audit": {"approved": True, "reason": "baby_noise_no_claims_to_vet"},
        "source": str(broll_meta.get("source") or ""),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    broll_path = pick_noise_broll_file(NOISE_BROLL_DIR)
    if broll_path is None:
        log.error(
            "No calm nursery/night b-roll available in %s -- run scripts/sync_noise_broll.py first "
            "(needs PIXABAY_API_KEY).",
            NOISE_BROLL_DIR,
        )
        return 1

    broll_meta = _load_sidecar(broll_path)
    scene = _pick_scene()
    color = _pick_color()
    duration_s = round(random.uniform(MIN_DURATION_S, MAX_DURATION_S), 1)
    noise_bed_path = _prepare_noise_bed(seed=random.randint(0, 1_000_000), color=color)
    seamless_clip = _prepare_seamless_loop_clip(broll_path)

    slug = f"noiseshort-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"noise-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    if not _compose_short(seamless_clip, noise_bed_path, video_path, duration_s):
        log.error("Baby-noise Short composition failed for %s", slug)
        return 1

    metadata = _build_metadata(scene, color, duration_s, video_path, slug, broll_meta=broll_meta)
    thumbnail_path = _extract_thumbnail_frame(broll_path, seed=random.randint(0, 1_000_000))
    if thumbnail_path is not None:
        metadata["thumbnail"] = str(thumbnail_path)
    else:
        log.warning("Could not extract a real thumbnail frame -- YouTube will auto-pick one.")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.1fs, %s): %s", video_path.name, duration_s, color, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
