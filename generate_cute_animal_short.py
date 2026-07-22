#!/usr/bin/env python3
"""Generate one vertical cute-animal YouTube Short: a real Pixabay clip
(cat, dog, puppy, kitten, bunny, hamster...) looped under a real jazz
track from Jamendo, no narration. Second, independent content pillar
(chat, 2026-07-22) -- "Pata Jazz" (see utils/animal_branding.py's module
docstring for why this is its own brand, not "Amber Hours").

Deliberately the opposite design from the rain/storm pillar's fixed
pinned clips: this pillar rotates through many different real animal
clips (scripts/sync_animal_broll.py) because variety across uploads is
the whole appeal of cute-animal content, not a single consistent scene.
The jazz layer (scripts/sync_animal_jazz.py) is real, commercially-safe
(CC BY) Jamendo music -- unlike the rain pillar's abandoned Jamendo
experiment, jazz is an actual music genre Jamendo genuinely has, so this
is a legitimate fit, not a repeat of that mistake. Both libraries are
thin at first (Jamendo's commercially-safe yield is low, checked live --
see sync_animal_jazz.py's module docstring) and grow slowly over many
scheduled runs via the GitHub Actions cache, same pattern every other
synced library in this repo uses.

No pinned-clip fallback exists for this pillar (no illustrated art was
drawn for it) -- if either pool is completely empty (fresh checkout, no
PIXABAY_API_KEY/Jamendo sync yet), this generator logs an error and skips
the run rather than silently faking a placeholder graphic. It requires
the animal b-roll pool to have at least one on-topic clip; it degrades
gracefully to silence (with a warning) if the jazz library alone is
empty, since a real animal clip with no jazz still works better than no
video at all.

Writes `_videos/animal-*.mp4` + matching `.json` that
upload_youtube.py's `_collect_pending_meta()` picks up (extended to
recognize the "animal-" prefix alongside "short-"/"mix-"/"roundup-"/
"storm-").
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

from utils.ai_titling import generate_animal_short_copy  # noqa: E402
from utils.animal_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title  # noqa: E402
from utils.broll import pick_animal_broll_file  # noqa: E402
from utils.ffmpeg_helpers import (  # noqa: E402
    compose_short,
    extract_thumbnail_frame,
    load_sidecar,
    media_duration_s,
    prepare_seamless_loop_clip,
)
from utils.title_history import select_title  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_cute_animal_short")

# Backward-compat aliases (tests may import the _-prefixed names from this module).
_load_sidecar = load_sidecar
_media_duration_s = media_duration_s


def _prepare_seamless_loop_clip(clip_path: Path) -> Path:
    return prepare_seamless_loop_clip(clip_path, temp_dir=TEMP_DIR, loop_crossfade_s=LOOP_CROSSFADE_S, logger=log)


def _extract_thumbnail_frame(clip_path: Path, seed: int) -> Path | None:
    return extract_thumbnail_frame(clip_path, seed, temp_dir=TEMP_DIR, logger=log)


def _compose_short(broll_path: Path, jazz_path: Path | None, output_path: Path, duration_s: float) -> bool:
    return compose_short(
        broll_path,
        jazz_path,
        output_path,
        duration_s,
        target_w=TARGET_W,
        target_h=TARGET_H,
        fade_s=FADE_S,
        logger=log,
    )


ANIMAL_BROLL_DIR = ROOT / "_assets" / "video" / "animal_broll"
JAZZ_DIR = ROOT / "_assets" / "audio" / "animal_jazz"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_animal_short"

TARGET_W = 1080
TARGET_H = 1920
MIN_DURATION_S = 30.0
MAX_DURATION_S = 58.0
FADE_S = 1.5
LOOP_CROSSFADE_S = 1.0  # same value/technique as generate_storm_short.py's identical constant

CATEGORY = "cute_animals"
SERIES_SUFFIX = "Shorts"
YOUTUBE_CATEGORY_ID = "15"  # Pets & Animals
DEFAULT_TAGS = [
    "gatinho fofo",
    "cachorro fofo",
    "animais fofos",
    "pet",
    "filhote",
    "shorts de animais",
    "fofura",
    "pata jazz",
]


def _pick_scene() -> str:
    return random.choice(list(HOOK_BY_SCENE.keys())).title()


def _pick_jazz_track() -> Path | None:
    tracks = sorted(JAZZ_DIR.glob("jamendo_*.mp3"))
    if not tracks:
        return None
    return random.choice(tracks)


def _music_credit_line(jazz_meta: dict | None) -> str:
    if not jazz_meta:
        return ""
    track_name = str(jazz_meta.get("track_name") or "").strip()
    if not track_name:
        return ""
    artist_name = str(jazz_meta.get("artist_name") or "").strip()
    license_url = str(jazz_meta.get("license_ccurl") or "").strip()
    credit = f'Jazz: "{track_name}"'
    if artist_name:
        credit += f" por {artist_name}"
    if license_url:
        credit += f" ({license_url})"
    return credit


def _build_metadata(
    scene: str,
    duration_s: float,
    video_path: Path,
    slug: str,
    *,
    broll_meta: dict,
    jazz_meta: dict | None,
) -> dict:
    template_title = branded_title(scene)
    bucket = playlist_bucket_for_title(template_title)
    music_credit = _music_credit_line(jazz_meta)

    description_lines = [
        "Um momento fofo de verdade, com música jazz de verdade por cima. Sem narração, sem enrolação.",
        "",
        f"\U0001f43e Parte da coleção {bucket} no Pata Jazz.",
    ]
    if music_credit:
        description_lines += ["", f"\U0001f3b7 {music_credit}"]
    description_lines += ["", "#Shorts"]

    tags = [scene.lower()] if scene.lower() not in {tag.lower() for tag in DEFAULT_TAGS} else []
    tags += DEFAULT_TAGS

    title = template_title
    description = "\n".join(description_lines).strip()

    ai_copy = generate_animal_short_copy(
        scene=scene,
        duration_s=duration_s,
        fallback_title=template_title,
        music_credit=music_credit or None,
    )
    if ai_copy:
        variants = ai_copy.get("title_variants") or [ai_copy["title"]]
        title = select_title(variants)
        description = f"{ai_copy['description']}\n\n#Shorts".strip()
        tags = ai_copy["hashtags"]
        if "pata jazz" not in tags:
            tags.append("pata jazz")

    return {
        "title": title,
        "description": description,
        "category": CATEGORY,
        "series": f"{bucket} {SERIES_SUFFIX}",
        "tags": tags,
        "video": str(video_path),
        "duration_s": duration_s,
        "story_id": slug,
        "youtube_category_id": YOUTUBE_CATEGORY_ID,
        "packaging": {"pinned_comment": "Qual bichinho a gente mostra no próximo? \U0001f43e"},
        "pre_publish_audit": {"approved": True, "reason": "cute_animals_no_claims_to_vet"},
        "source": str(broll_meta.get("source") or ""),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
        "bgm_track_id": str(jazz_meta.get("track_id")) if jazz_meta and jazz_meta.get("track_id") else "",
        "bgm_license_ccurl": str(jazz_meta.get("license_ccurl") or "") if jazz_meta else "",
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    broll_path = pick_animal_broll_file(ANIMAL_BROLL_DIR)
    if broll_path is None:
        log.error(
            "No cute-animal b-roll available in %s -- run scripts/sync_animal_broll.py first "
            "(needs PIXABAY_API_KEY).",
            ANIMAL_BROLL_DIR,
        )
        return 1

    broll_meta = _load_sidecar(broll_path)
    scene = _pick_scene()
    duration_s = round(random.uniform(MIN_DURATION_S, MAX_DURATION_S), 1)

    jazz_path = _pick_jazz_track()
    jazz_meta = _load_sidecar(jazz_path) if jazz_path else None
    if jazz_path is None:
        log.warning("No jazz track available this run (thin library) -- shipping with silent audio.")

    seamless_clip = _prepare_seamless_loop_clip(broll_path)

    slug = f"animalshort-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"animal-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    if not _compose_short(seamless_clip, jazz_path, video_path, duration_s):
        log.error("Cute-animal Short composition failed for %s", slug)
        return 1

    metadata = _build_metadata(scene, duration_s, video_path, slug, broll_meta=broll_meta, jazz_meta=jazz_meta)
    thumbnail_path = _extract_thumbnail_frame(broll_path, seed=random.randint(0, 1_000_000))
    if thumbnail_path is not None:
        metadata["thumbnail"] = str(thumbnail_path)
    else:
        log.warning("Could not extract a real thumbnail frame -- YouTube will auto-pick one.")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.1fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
