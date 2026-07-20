#!/usr/bin/env python3
"""Generate one lofi YouTube Short: a looping b-roll clip + music, no narration.

Picks a random clip from scripts/sync_lofi_broll.py's on-disk library and a
random track from scripts/sync_jamendo_music.py's on-disk library, loops
both to a fixed target duration with a short fade in/out, and writes the
`_videos/short-*.mp4` + matching `.json` pair that upload_youtube.py's
_collect_pending_meta() already picks up -- no changes needed there.

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

from utils.broll import pick_weighted_broll_file  # noqa: E402
from utils.lofi_branding import bgm_speeds_for_mood, branded_title, playlist_bucket_for_title  # noqa: E402
from utils.thumbnail_branding import brand_short_thumbnail  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_lofi_short")

BROLL_DIR = ROOT / "_assets" / "video" / "lofi_broll"
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


def _pick_file(directory: Path, pattern: str) -> Path | None:
    candidates = sorted(directory.glob(pattern))
    if not candidates:
        return None
    return random.choice(candidates)


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


def _pick_broll_file(directory: Path, pattern: str) -> Path | None:
    """Like _pick_file, but only among on-brand clips, weighted toward the
    rainy-night/cozy sub-niche -- see utils.broll.pick_weighted_broll_file.
    """
    return pick_weighted_broll_file(directory, pattern)


def _load_sidecar(media_path: Path) -> dict:
    meta_path = media_path.with_suffix(".json")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _mood_label(query: str) -> str:
    # LOFI_QUERIES in sync_lofi_broll.py all start with "anime"; skip it so
    # the mood doesn't collide with the "Anime Lofi" wording branded_title()
    # already adds (e.g. "anime lofi girl study" -> "Lofi Girl", not the
    # redundant "Lofi Girl Anime Lofi").
    words = [w for w in (query or "").split() if w]
    if words and words[0].lower() == "anime":
        words = words[1:]
    words = words[:2]
    return " ".join(word.capitalize() for word in words) or "Cozy"


def _build_metadata(broll_meta: dict, bgm_meta: dict, duration_s: float, video_path: Path, story_id: str = "") -> dict:
    mood = _mood_label(str(broll_meta.get("query") or ""))
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
        "source": "pixabay",
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

    broll_path = _pick_broll_file(BROLL_DIR, "pixabay_*.mp4")
    if broll_path is None:
        log.error(
            "No on-brand lofi b-roll clips found in %s -- run scripts/sync_lofi_broll.py first, "
            "or scripts/prune_offbrand_broll.py if the library only has off-brand clips.",
            BROLL_DIR,
        )
        return 1

    broll_meta = _load_sidecar(broll_path)
    mood = _mood_label(str(broll_meta.get("query") or ""))

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

    metadata = _build_metadata(broll_meta, bgm_meta, duration_s, video_path, story_id=slug)
    thumb_path = VIDEOS_DIR / f"short-{slug}_thumb.jpg"
    if _extract_thumbnail(video_path, thumb_path):
        try:
            brand_short_thumbnail(thumb_path, _mood_label(str(broll_meta.get("query") or "")))
        except Exception as exc:
            log.warning("thumbnail branding failed for %s, keeping raw frame: %s", slug, exc)
        metadata["thumbnail"] = str(thumb_path)
    else:
        log.warning("No custom thumbnail for %s -- YouTube will auto-pick a frame.", slug)
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.1fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
