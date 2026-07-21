#!/usr/bin/env python3
"""Generate one lofi YouTube Short: a looping b-roll clip + music, no narration.

Loops scripts/pinned b-roll clip (PINNED_BROLL_CLIP, one fixed committed
asset -- see its own comment) plus a random track from
scripts/sync_jamendo_music.py's on-disk library to a fixed target
duration with a short fade in/out, and writes the `_videos/short-*.mp4` +
matching `.json` pair that upload_youtube.py's _collect_pending_meta()
already picks up -- no changes needed there.

Deliberately does not go through generate_shorts.py's nature-content
pipeline (fact_guard, editorial_guard, hook_library, script_quality, ...):
those gates exist to vet a narrated factual claim, and a lofi Short carries
neither narration nor a claim to vet.
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

from utils.lofi_branding import (  # noqa: E402
    HOOK_BY_MOOD,
    bgm_speeds_for_mood,
    branded_title,
    playlist_bucket_for_title,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_lofi_short")

# Every Short loops this one committed clip (chat, 2026-07-20: the rotating
# Pixabay-synced BROLL_DIR pool this used to pick from occasionally let an
# off-brand clip through despite the anime-style tag filter -- a stock 3D
# "man with a stack of books" render published as "Late Night Library Lofi"
# was the one that triggered this). It's now an original branding
# illustration rendered to video -- a rainy-window scene drawn specifically
# for this format (chat, 2026-07-21), distinct from generate_lofi_mix.py's
# and scripts/live_stream_dynamic.py's own so the three formats don't look
# identical on a channel page -- which removes tag-based curation from the
# loop entirely: only the mood (title/tags/bgm pairing, still varied per
# video) and the music actually change now.
PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_short_clip.mp4"
# Used directly as the YouTube thumbnail too (instead of extracting +
# re-branding a video frame) so the video and its cover image show the
# exact same picture PINNED_BROLL_CLIP was rendered from. Its own scene
# (rainy window, native 9:16 -- chat, 2026-07-21), distinct from the
# live's and generate_lofi_mix.py's so the three formats don't all look
# identical on a channel page.
BRAND_THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "shorts_scene_1080x1920.png"
BGM_DIR = ROOT / "_assets" / "audio" / "bgm"
VIDEOS_DIR = ROOT / "_videos"

TARGET_W = 1080
TARGET_H = 1920
TARGET_FPS = 30
MIN_DURATION_S = 30.0
MAX_DURATION_S = 58.0
FADE_S = 1.5

CATEGORY = "lofi"
# A fixed named series per mood bucket ("Rainy Night Lofi Shorts", "Cozy
# Cat Lofi Shorts", ...) instead of one static "Lofi Beats" label on every
# Short regardless of mood -- the old constant carried no thematic
# information at all (every video had the exact same "series"), so it
# never gave a viewer a real recurring thing to follow. Suffixed with
# "Shorts" (matching generate_lofi_mix.py's "Mix" suffix) so the Shorts and
# horizontal-mix side of a given theme stay two distinct series/playlists,
# not one merged bucket.
SERIES_SUFFIX = "Shorts"
# Niche-first (chat, 2026-07-19): "lofi"/"chillhop" alone are unwinnable
# head terms for a small channel (Lofi Girl etc. already own them) -- lead
# with the rainy-night/cozy-anime sub-niche instead, same reasoning as
# utils/lofi_branding.py's titles.
DEFAULT_TAGS = [
    "lofi",
    "anime lofi",
    "rainy night lofi",
    "cozy anime lofi",
    "midnight lofi",
    "sleep lofi",
    "chillhop",
    "amber hours",
]


def _pick_bgm_file_for_mood(directory: Path, mood: str) -> Path | None:
    """Prefer a track whose sidecar "speed" matches the b-roll mood's energy
    (utils.lofi_branding.bgm_speeds_for_mood) so a busier scene doesn't get
    paired with a half-asleep track or vice versa. Falls back to the full
    library when no track matches -- an older/unsynced sidecar without a
    "speed" field, or a still-small library, shouldn't ever leave a Short
    without music."""
    candidates = sorted(directory.glob("jamendo_*.mp3"))
    if not candidates:
        return None
    wanted_speeds = bgm_speeds_for_mood(mood)
    matches = [p for p in candidates if _load_sidecar(p).get("speed") in wanted_speeds]
    return random.choice(matches or candidates)


def _load_sidecar(media_path: Path) -> dict:
    meta_path = media_path.with_suffix(".json")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _pick_mood() -> str:
    """The pinned b-roll clip no longer varies per video (see
    PINNED_BROLL_CLIP), so mood -- title/tags/thumbnail-hook/bgm-energy --
    is now picked independently from utils.lofi_branding.HOOK_BY_MOOD's
    vocabulary instead of being derived from the clip's own search query."""
    return random.choice(list(HOOK_BY_MOOD.keys())).title()


def _build_metadata(
    mood: str, broll_meta: dict, bgm_meta: dict, duration_s: float, video_path: Path, story_id: str = ""
) -> dict:
    title = branded_title(mood)
    track_name = str(bgm_meta.get("track_name") or "")
    artist_name = str(bgm_meta.get("artist_name") or "")
    license_url = str(bgm_meta.get("license_ccurl") or "")
    photographer = str(broll_meta.get("photographer") or "")

    bucket = playlist_bucket_for_title(title)
    description_lines = [
        f"{mood.lower()} lofi beats -- chill music to relax, study or unwind to.",
        "",
        f"\U0001f319 Part of the {bucket} collection on Amber Hours -- rainy night "
        "anime lofi, cozy beats for late nights, playing 24/7 on the channel live stream.",
        "",
    ]
    if track_name:
        credit = f'\U0001f3b5 Music: "{track_name}"'
        if artist_name:
            credit += f" by {artist_name}"
        if license_url:
            credit += f" ({license_url})"
        description_lines.append(credit)
    if photographer:
        description_lines.append(f"\U0001f3ac Visual: Pixabay / {photographer}")

    # Mood tag leads (not trails) DEFAULT_TAGS on purpose: it's the only
    # per-video-specific tag, both for SEO (most specific term first) and
    # because upload_youtube.py's title-collision dedup tries tag values in
    # list order for a detail to append -- with the mood last, every fixed
    # DEFAULT_TAGS entry got a chance to win first, so unrelated videos
    # kept landing on the exact same dedup suffix ("| Rainy Night Lofi")
    # regardless of their own mood.
    tags = [mood.lower()] if mood.lower() not in {tag.lower() for tag in DEFAULT_TAGS} else []
    tags += DEFAULT_TAGS

    return {
        "title": title,
        "description": "\n".join(description_lines).strip(),
        "category": CATEGORY,
        "series": f"{bucket} {SERIES_SUFFIX}",
        "tags": tags,
        "video": str(video_path),
        "duration_s": duration_s,
        "story_id": story_id,
        "packaging": {"pinned_comment": "What mood should the next loop be? \U0001f31a"},
        "pre_publish_audit": {"approved": True, "reason": "lofi_no_claims_to_vet"},
        "source": str(broll_meta.get("source") or "branding"),
        # upload_youtube.py's ledger field is named after the original
        # Pexels-only pipeline but is provider-agnostic in practice (it
        # just needs *a* source clip id); keeping the key avoids touching
        # that already-tested allowlist/ledger contract for a rename.
        "pexels_video_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
        "bgm_track_id": str(bgm_meta.get("track_id") or ""),
        "bgm_license_ccurl": license_url,
    }


def _compose_short(broll_path: Path, bgm_path: Path, output_path: Path, duration_s: float) -> bool:
    fade_out_start = max(duration_s - FADE_S, 0.0)
    video_filter = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},fps={TARGET_FPS},"
        f"zoompan=z='min(zoom+0.0007,1.12)':d=1:s={TARGET_W}x{TARGET_H}:fps={TARGET_FPS},"
        f"setsar=1,fade=t=in:st=0:d={FADE_S},fade=t=out:st={fade_out_start:.3f}:d={FADE_S}[v]"
    )
    audio_filter = f"afade=t=in:st=0:d={FADE_S},afade=t=out:st={fade_out_start:.3f}:d={FADE_S},volume=0.9[a]"
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(broll_path),
        "-stream_loop",
        "-1",
        "-i",
        str(bgm_path),
        "-filter_complex",
        f"[0:v]{video_filter};[1:a]{audio_filter}",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        f"{duration_s:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as exc:
        log.error("ffmpeg failed to run: %s", exc)
        return False
    if result.returncode != 0:
        log.error("ffmpeg exited %d: %s", result.returncode, result.stderr[-2000:])
        return False
    return output_path.exists() and output_path.stat().st_size > 0


def _extract_thumbnail(video_path: Path, thumb_path: Path, timestamp_s: float = 2.0) -> bool:
    """Grab a single frame as the upload thumbnail instead of letting YouTube auto-pick one."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp_s:.2f}",
        "-i",
        str(video_path),
        "-vframes",
        "1",
        "-q:v",
        "2",
        str(thumb_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        log.warning("thumbnail extraction failed to run: %s", exc)
        return False
    if result.returncode != 0:
        log.warning("thumbnail extraction exited %d: %s", result.returncode, result.stderr[-500:])
        return False
    return thumb_path.exists() and thumb_path.stat().st_size > 0


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    if not PINNED_BROLL_CLIP.exists():
        log.error("Pinned Shorts b-roll clip missing: %s", PINNED_BROLL_CLIP)
        return 1
    broll_path = PINNED_BROLL_CLIP

    broll_meta = _load_sidecar(broll_path)
    mood = _pick_mood()

    bgm_path = _pick_bgm_file_for_mood(BGM_DIR, mood)
    if bgm_path is None:
        log.error("No bgm tracks found in %s -- run scripts/sync_jamendo_music.py first.", BGM_DIR)
        return 1

    bgm_meta = _load_sidecar(bgm_path)
    duration_s = round(random.uniform(MIN_DURATION_S, MAX_DURATION_S), 1)

    slug = f"lofi-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"short-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    if not _compose_short(broll_path, bgm_path, video_path, duration_s):
        log.error("Short composition failed for %s", slug)
        return 1

    metadata = _build_metadata(mood, broll_meta, bgm_meta, duration_s, video_path, story_id=slug)
    if BRAND_THUMBNAIL_IMAGE.exists():
        metadata["thumbnail"] = str(BRAND_THUMBNAIL_IMAGE)
    else:
        log.warning("Brand thumbnail image missing: %s -- YouTube will auto-pick a frame.", BRAND_THUMBNAIL_IMAGE)
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.1fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
