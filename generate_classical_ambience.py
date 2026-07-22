#!/usr/bin/env python3
"""Generate one long-form "Amber Hours Classical" video: the fixed pinned
anime-style study scene looped under exactly ONE real, licensed classical/
orchestral/piano track from Jamendo -- not a mixed bed, not a synthesized
loop. Fourth content pillar (chat, 2026-07-22), and the only one on this
channel published in English.

Exact spec from the channel owner, followed literally rather than
creatively reinterpreted:
  - One video = one song. The video's runtime is exactly the track's own
    real duration; the track plays through once while the pinned clip
    loops under it (same "bake once, loop cheaply via -stream_loop -c:v
    copy" technique as generate_storm_ambience.py, just driven by the
    track's real length instead of a random target range).
  - The same one pinned clip in every video -- no rotation, no
    illustrated fallback (none exists for this pillar; if the pinned
    file is ever missing, this exits 1 rather than faking a
    placeholder).
  - No Shorts companion for this pillar.
  - Title/description/tags in English.
  - Mandatory, real attribution: every video's description ends with an
    exact, unconditional credit line (real track name, real artist name,
    real CC BY license URL) -- this is a legal requirement of the CC BY
    license, not something the AI-copy path is free to omit, paraphrase,
    or skip. See _mandatory_attribution_line() -- it is appended in code
    after either the AI-generated or template description, every single
    time, regardless of which path ran.

Writes `_videos/classical-*.mp4` + matching `.json` that
upload_youtube.py's `_collect_pending_meta()` picks up (extended to
recognize the "classical-" prefix).
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

from utils.ai_titling import generate_classical_video_copy  # noqa: E402
from utils.classical_branding import HOOK_BY_MOOD, branded_title, playlist_bucket_for_title  # noqa: E402
from utils.ffmpeg_helpers import (  # noqa: E402
    bake_filtered_segment,
    load_sidecar,
    media_duration_s,
    prepare_seamless_loop_clip,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_classical_ambience")

# Backward-compat aliases (tests may import the _-prefixed names from this module).
_load_sidecar = load_sidecar
_media_duration_s = media_duration_s


def _prepare_seamless_loop_clip(clip_path: Path) -> Path:
    return prepare_seamless_loop_clip(clip_path, temp_dir=TEMP_DIR, loop_crossfade_s=LOOP_CROSSFADE_S, logger=log)


def _bake_filtered_segment(clip_path: Path) -> Path | None:
    return bake_filtered_segment(
        clip_path,
        temp_dir=TEMP_DIR,
        target_w=TARGET_W,
        target_h=TARGET_H,
        target_fps=TARGET_FPS,
        gop_size=60,
        logger=log,
    )


# The one fixed, real Pixabay clip the channel owner hand-picked after
# reviewing real preview frames of several candidates (chat, 2026-07-22)
# -- no rotation, no illustrated fallback exists for this pillar.
PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_classical_ambience.mp4"
# A real frame extracted from PINNED_BROLL_CLIP itself, committed once
# (the clip never changes, so there's no reason to re-extract per run --
# same reasoning as the storm pillar's real-frame thumbnails, applied
# from day one here instead of retrofitted later).
BRAND_THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "classical_ambience_thumbnail.jpg"
CLASSICAL_DIR = ROOT / "_assets" / "audio" / "classical"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_classical"

TARGET_W = 1920
TARGET_H = 1080
TARGET_FPS = 30  # 1080p keeps the bake fast enough for GitHub Actions runners

CATEGORY = "classical_ambience"
SERIES_SUFFIX = "Ambience"
YOUTUBE_CATEGORY_ID = "10"  # Music
LOOP_CROSSFADE_S = 1.0  # same value/technique as every other pillar's identical constant

DEFAULT_TAGS = [
    "classical music",
    "classical piano",
    "study music",
    "relaxing classical music",
    "piano music for studying",
    "orchestral music",
    "amber hours classical",
]


def _pick_mood() -> str:
    return random.choice(list(HOOK_BY_MOOD.keys())).title()


def _pick_track() -> Path | None:
    """Least-recently-used pick, not pure random: sort the library by
    file mtime ascending and take the oldest-touched one, then touch it
    (update its mtime to "now") so it goes to the back of the queue.
    With an hourly cadence, pure random.choice would repeat noticeably
    even with a moderately-sized library -- this round-robins through
    the whole library before any track repeats, using each file's own
    mtime as a zero-extra-state "last used" marker (this repo already
    uses mtime this way for library rotation/eviction elsewhere, e.g.
    scripts/sync_classical_music.py's own oldest-first eviction)."""
    tracks = list(CLASSICAL_DIR.glob("jamendo_*.mp3"))
    if not tracks:
        return None
    tracks.sort(key=lambda p: p.stat().st_mtime)
    chosen = tracks[0]
    chosen.touch()
    return chosen


def _compose_classical(filtered_segment: Path, track_path: Path, output_path: Path, duration_s: float) -> bool:
    """Loop the pinned clip via -stream_loop -c:v copy to fill exactly
    the track's own duration; the track itself is NOT looped -- it plays
    through once, start to finish (its own duration IS the -t cutoff, so
    there's nothing left to loop)."""
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(filtered_segment),
        "-i",
        str(track_path),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-t",
        f"{duration_s:.3f}",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "44100",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception as exc:
        log.error("ffmpeg failed to run: %s", exc)
        return False
    if result.returncode != 0:
        log.error("ffmpeg exited %d: %s", result.returncode, result.stderr[-2000:])
        return False
    return output_path.exists() and output_path.stat().st_size > 0


def _mandatory_attribution_line(track_meta: dict) -> str:
    """The legally-required CC BY credit -- track name, artist name, and
    the exact license URL Jamendo reports, verbatim. Appended
    unconditionally in _build_metadata() regardless of which description
    path (AI or template) ran; never optional, never something the AI is
    trusted to have included correctly on its own."""
    track_name = str(track_meta.get("track_name") or "Unknown track").strip()
    artist_name = str(track_meta.get("artist_name") or "Unknown artist").strip()
    license_url = str(track_meta.get("license_ccurl") or "").strip()
    line = f'Music: "{track_name}" by {artist_name}'
    if license_url:
        line += f", licensed under Creative Commons Attribution ({license_url})"
    else:
        line += ", licensed under Creative Commons Attribution (CC BY)"
    return line


def _build_metadata(
    mood: str,
    duration_s: float,
    video_path: Path,
    slug: str,
    *,
    track_meta: dict,
) -> dict:
    track_name = str(track_meta.get("track_name") or "").strip()
    artist_name = str(track_meta.get("artist_name") or "").strip()
    attribution = _mandatory_attribution_line(track_meta)

    minutes = duration_s / 60
    duration_label = f"({minutes:.0f} Min)" if minutes < 60 else f"({duration_s / 3600:.1f} Hours)"
    template_title = branded_title(mood, suffix=duration_label)
    bucket = playlist_bucket_for_title(template_title)

    description_lines = [
        f"{mood} classical ambience -- one real piece, looped visual, no narration.",
        "",
        f"\U0001f3b9 Part of the {bucket} collection on Amber Hours Classical.",
        "",
        attribution,
    ]

    tags = [mood.lower()] if mood.lower() not in {tag.lower() for tag in DEFAULT_TAGS} else []
    tags += DEFAULT_TAGS

    title = template_title
    description = "\n".join(description_lines).strip()

    # Gemini takes over title/description/hashtags when GEMINI_API_KEY is
    # configured -- degrades to the template above on any missing key,
    # provider failure, or bad response. Either way, the mandatory
    # attribution line is appended AFTER whichever description resulted,
    # unconditionally -- see _mandatory_attribution_line()'s docstring
    # for why this is not optional.
    ai_copy = generate_classical_video_copy(
        mood=mood,
        duration_s=duration_s,
        track_name=track_name or "this piece",
        artist_name=artist_name or "the performer",
        fallback_title=template_title,
    )
    if ai_copy:
        title = ai_copy["title"]
        description = f"{ai_copy['description']}\n\n{attribution}".strip()
        tags = ai_copy["hashtags"]
        if "amber hours classical" not in tags:
            tags.append("amber hours classical")

    return {
        "title": title,
        "description": description,
        "category": CATEGORY,
        "series": f"{bucket} {SERIES_SUFFIX}",
        "tags": tags,
        "video": str(video_path),
        "duration_s": duration_s,
        "story_id": slug,
        "is_short": False,
        "youtube_category_id": YOUTUBE_CATEGORY_ID,
        "packaging": {"pinned_comment": "What piece should we feature next? \U0001f3b9"},
        "pre_publish_audit": {"approved": True, "reason": "classical_ambience_no_claims_to_vet"},
        "bgm_track_id": str(track_meta.get("track_id") or ""),
        "bgm_track_name": track_name,
        "bgm_artist_name": artist_name,
        "bgm_license_ccurl": str(track_meta.get("license_ccurl") or ""),
        "publish_slot": f"classical-{time.strftime('%H')}",
        "publish_slot_key": f"classical-{time.strftime('%Y-%m-%d')}-{time.strftime('%H')}",
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if not PINNED_BROLL_CLIP.exists():
        log.error(
            "No pinned classical-ambience clip found at %s -- this pillar has no illustrated fallback.",
            PINNED_BROLL_CLIP,
        )
        return 1

    track_path = _pick_track()
    if track_path is None:
        log.error(
            "No classical track available in %s -- run scripts/sync_classical_music.py first "
            "(needs no secret -- Jamendo's client id is hardcoded in that script).",
            CLASSICAL_DIR,
        )
        return 1

    track_meta = _load_sidecar(track_path)
    duration_s = _media_duration_s(track_path)
    if duration_s <= 0:
        log.error("Could not read a real duration for %s -- refusing to generate a 0-length video.", track_path)
        return 1

    mood = _pick_mood()

    log.info("Stage 1/2: baking filtered segment from %s", PINNED_BROLL_CLIP.name)
    seamless_clip = _prepare_seamless_loop_clip(PINNED_BROLL_CLIP)
    filtered_segment = _bake_filtered_segment(seamless_clip)
    if filtered_segment is None:
        log.error("Could not prepare a loopable video segment from %s", PINNED_BROLL_CLIP.name)
        return 1

    slug = f"ambience-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"classical-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    log.info(
        "Stage 2/2: composing %.0fs classical ambience (%s by %s) at %s",
        duration_s,
        track_meta.get("track_name"),
        track_meta.get("artist_name"),
        video_path.name,
    )
    if not _compose_classical(filtered_segment, track_path, video_path, duration_s):
        log.error("Classical ambience composition failed for %s", slug)
        return 1

    metadata = _build_metadata(mood, duration_s, video_path, slug, track_meta=track_meta)
    if BRAND_THUMBNAIL_IMAGE.exists():
        metadata["thumbnail"] = str(BRAND_THUMBNAIL_IMAGE)
    else:
        log.warning("Brand thumbnail image missing: %s -- YouTube will auto-pick a frame.", BRAND_THUMBNAIL_IMAGE)
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.0fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
