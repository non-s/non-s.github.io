#!/usr/bin/env python3
"""Generate one long-form "real rain & thunder ambience" video: the
animated storm scene looped under a procedurally-synthesized rain/thunder
bed, with an optional quiet Jamendo track mixed underneath. No narration.

New pillar (growth pass, 2026-07-21): picked over another lofi variant
specifically to stop competing on "anime lofi" -- one of YouTube's most
saturated searches -- and instead target the real, much larger "rain
sounds for sleep" / "thunderstorm ambience" search intent (see
utils/storm_branding.py's module docstring). Still published as "Amber
Hours".

Rendering follows generate_lofi_mix.py's exact "bake once, loop cheaply"
approach: the pinned storm clip's scale/zoompan filter chain runs ONCE
against its own short duration, and the *encoded* result is looped via
`-stream_loop -1 -c:v copy` to fill the target runtime, rather than
re-encoding video for the whole length. The rain/thunder bed
(utils/storm_audio.py) is a WAV loop with its own, deliberately
non-matching period, and an optional Jamendo track loops on its own period
too -- three independent cycle lengths mean the combined video is never
audibly/visibly repeating in lockstep, even though each layer loops
individually.

Writes `_videos/storm-*.mp4` + matching `.json` that
upload_youtube.py's `_collect_pending_meta()` picks up (extended to
recognize the "storm-" prefix alongside "short-"/"mix-"/"roundup-").
"""

from __future__ import annotations

import json
import logging
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ai_titling import generate_video_copy  # noqa: E402
from utils.broll import pick_storm_broll_file  # noqa: E402
from utils.storm_audio import generate_rain_bed, write_wav  # noqa: E402
from utils.storm_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_storm_ambience")

# Real Pixabay rain/storm footage (scripts/sync_storm_broll.py) is tried
# first -- picked at random from the synced pool the same way
# generate_lofi_mix.py used to before ADR 0004, just without that ADR's
# concern applying here: is_on_brand_storm_clip() already re-checks tag
# relevance at selection time, same double-gate as the lofi pillar's
# is_on_brand_broll_clip. Falls back to the illustrated pinned clip
# whenever the pool is empty (no PIXABAY_API_KEY configured, or the sync
# step hasn't run yet) so this pipeline never *requires* the real-footage
# path to produce a video.
STORM_BROLL_DIR = ROOT / "_assets" / "video" / "storm_broll"
PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_storm_clip.mp4"
# Used directly as the YouTube thumbnail too, same reasoning as
# generate_lofi_mix.py's BRAND_THUMBNAIL_IMAGE.
BRAND_THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "storm_scene_1920x1080.png"
BGM_DIR = ROOT / "_assets" / "audio" / "bgm"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_storm"

TARGET_W = 1920
TARGET_H = 1080
TARGET_FPS = 20  # matches the pinned clip's own fps -- no reason to upsample a static illustration loop

CATEGORY = "storm_ambience"
SERIES_SUFFIX = "Ambience"
YOUTUBE_CATEGORY_ID = "10"  # Music -- consistent with the rest of the channel's uploads

RAIN_BED_SECONDS = 53.0  # deliberately not a round multiple of the video loop's 14s -- see module docstring
LOOP_CROSSFADE_S = 1.0  # same value/technique as generate_lofi_mix.py's identical constant
MIN_DURATION_MINUTES = float(os.environ.get("STORM_MIN_DURATION_MINUTES", "45"))
MAX_DURATION_MINUTES = float(os.environ.get("STORM_MAX_DURATION_MINUTES", "75"))
MUSIC_LAYER_PROBABILITY = float(os.environ.get("STORM_MUSIC_LAYER_PROBABILITY", "0.35"))
MUSIC_LAYER_VOLUME = 0.16  # quiet enough that rain/thunder stays the actual point

# Real search-intent tags for this niche -- deliberately not the lofi
# pillar's DEFAULT_TAGS (see utils/storm_branding.py's docstring for why
# the two vocabularies must not overlap).
DEFAULT_TAGS = [
    "rain sounds",
    "rain sounds for sleep",
    "thunderstorm sounds",
    "rain and thunder",
    "sleep sounds",
    "relaxing rain",
    "white noise",
    "amber hours",
]


def _load_sidecar(media_path: Path) -> dict:
    meta_path = media_path.with_suffix(".json")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _pick_scene() -> str:
    return random.choice(list(HOOK_BY_SCENE.keys())).title()


def _media_duration_s(path: Path) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _prepare_seamless_loop_clip(clip_path: Path) -> Path:
    """Bake a short crossfade between the clip's tail and head once, so
    looping it via -stream_loop has no visible hard cut/motion-snap at the
    seam. The illustrated pinned clip is already a mathematically seamless
    loop by construction (utils/brand_motion.py), so this is a no-op-ish
    pass for it, but real Pixabay footage (scripts/sync_storm_broll.py)
    has no such guarantee -- its motion (falling rain, drifting clouds)
    would otherwise visibly jump backward every repeat over a 45-75 minute
    video. Exact same technique as generate_lofi_mix.py's identical
    helper (see its docstring for why the concat operand order matters)."""
    out_path = TEMP_DIR / f"seamless_{clip_path.stem}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    duration = _media_duration_s(clip_path)
    fade = min(LOOP_CROSSFADE_S, duration / 6) if duration > 3 else 0.0
    if fade <= 0:
        return clip_path

    filter_complex = (
        f"[0:v]trim=0:{fade:.3f},setpts=PTS-STARTPTS[start];"
        f"[0:v]trim={duration - fade:.3f}:{duration:.3f},setpts=PTS-STARTPTS[end];"
        f"[0:v]trim={fade:.3f}:{duration - fade:.3f},setpts=PTS-STARTPTS[mid];"
        f"[end][start]xfade=transition=fade:duration={fade:.3f}:offset=0[blend];"
        "[mid][blend]concat=n=2:v=1:a=0[out]"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(clip_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        str(out_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as exc:
        log.warning("Failed to bake seamless loop clip, using raw clip instead: %s", exc)
        return clip_path
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        log.warning("ffmpeg seamless-loop bake failed, using raw clip instead: %s", result.stderr[-500:])
        return clip_path
    log.info("Baked seamless loop clip from %s (crossfade=%.2fs).", clip_path.name, fade)
    return out_path


def _bake_filtered_segment(clip_path: Path) -> Path | None:
    """Same approach as generate_lofi_mix.py's identical helper: apply the
    scale/zoompan filter chain ONCE against the pinned clip's own short
    duration, producing a small already-encoded segment the final render
    can loop with -c:v copy."""
    out_path = TEMP_DIR / f"filtered_{clip_path.stem}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    video_filter = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},fps={TARGET_FPS},setsar=1,format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(clip_path),
        "-vf",
        video_filter,
        "-an",
        "-r",
        str(TARGET_FPS),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-profile:v",
        "high",
        "-g",
        "40",
        "-keyint_min",
        "40",
        "-sc_threshold",
        "0",
        "-crf",
        "20",
        str(out_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as exc:
        log.error("Failed to bake filtered segment: %s", exc)
        return None
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        log.error("ffmpeg filtered-segment bake failed: %s", result.stderr[-1500:])
        return None
    return out_path


def _prepare_rain_bed(seed: int) -> Path:
    bed_path = TEMP_DIR / f"rain_bed_{seed}.wav"
    if bed_path.exists() and bed_path.stat().st_size > 0:
        return bed_path
    thunder_count = random.randint(1, 3)
    bed = generate_rain_bed(duration_s=RAIN_BED_SECONDS, seed=seed, thunder_count=thunder_count)
    write_wav(bed, bed_path)
    return bed_path


def _compose_storm(
    filtered_segment: Path,
    rain_bed_path: Path,
    music_path: Path | None,
    output_path: Path,
    duration_s: float,
) -> bool:
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(filtered_segment),
        "-stream_loop",
        "-1",
        "-i",
        str(rain_bed_path),
    ]
    if music_path is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]
        filter_complex = f"[1:a]volume=1.0[rain];[2:a]volume={MUSIC_LAYER_VOLUME}[music];[rain][music]amix=inputs=2:duration=first:dropout_transition=0[a]"
    else:
        filter_complex = "[1:a]volume=1.0[a]"
    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        "0:v",
        "-map",
        "[a]",
        "-t",
        f"{duration_s:.3f}",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
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


_ALWAYS_ON_DISCLOSURE = (
    "The rain and thunder in this video are procedurally synthesized, not a looped recording "
    "-- no sample to run out of, no license to clear."
)


def _music_credit_line(music_meta: dict | None) -> str:
    if not music_meta:
        return ""
    track_name = str(music_meta.get("track_name") or "").strip()
    if not track_name:
        return ""
    artist_name = str(music_meta.get("artist_name") or "").strip()
    license_url = str(music_meta.get("license_ccurl") or "").strip()
    credit = f'Soft music underneath: "{track_name}"'
    if artist_name:
        credit += f" by {artist_name}"
    if license_url:
        credit += f" ({license_url})"
    return credit


def _build_metadata(
    scene: str,
    duration_s: float,
    video_path: Path,
    slug: str,
    *,
    music_meta: dict | None,
    broll_meta: dict,
) -> dict:
    hours = duration_s / 3600
    duration_label = f"({hours:.1f} Hours)" if hours >= 1 else f"({max(1, round(duration_s / 60))} Min)"
    template_title = branded_title(scene, suffix=duration_label)
    bucket = playlist_bucket_for_title(template_title)
    music_credit = _music_credit_line(music_meta)

    description_lines = [
        f"{scene.lower()} rain sounds with distant thunder -- real ambience to help you sleep, "
        "focus, or relax, no narration.",
        "",
        f"\U0001f327️ Part of the {bucket} collection on Amber Hours.",
        "",
        f"\U0001f3a7 {_ALWAYS_ON_DISCLOSURE}",
    ]
    if music_credit:
        description_lines.append(f"\n\U0001f3b5 {music_credit}")

    tags = [scene.lower()] if scene.lower() not in {tag.lower() for tag in DEFAULT_TAGS} else []
    tags += DEFAULT_TAGS

    title = template_title
    description = "\n".join(description_lines).strip()

    # Gemini takes over title/description/hashtags when GEMINI_API_KEY is
    # configured (see utils/ai_titling.py) -- degrades to the template
    # above on any missing key, provider failure, or bad response, so this
    # pipeline still never *requires* an AI key.
    ai_copy = generate_video_copy(
        format_label="long-form rain & thunder ambience",
        scene=scene,
        duration_s=duration_s,
        fallback_title=template_title,
        credits_lines=[music_credit] if music_credit else None,
    )
    if ai_copy:
        title = ai_copy["title"]
        description = f"{ai_copy['description']}\n\n{_ALWAYS_ON_DISCLOSURE}".strip()
        tags = ai_copy["hashtags"]
        if "amber hours" not in tags:
            tags.append("amber hours")

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

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
        "packaging": {"pinned_comment": "What should the next storm sound like? \U0001f327️"},
        "pre_publish_audit": {"approved": True, "reason": "storm_ambience_no_claims_to_vet"},
        "source": str(broll_meta.get("source") or "branding"),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
        "bgm_track_ids": [str(music_meta.get("track_id"))] if music_meta and music_meta.get("track_id") else [],
        # A daily-multiple-slots key, distinct from the Shorts/mix grids --
        # see generate_lofi_mix.py's identical publish_slot comment for why
        # this matters for upload_youtube.py's per-slot idempotency check.
        "publish_slot": f"storm-{now.hour:02d}",
        "publish_slot_key": f"storm-{today}-{now.hour:02d}",
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    broll_path = pick_storm_broll_file(STORM_BROLL_DIR)
    if broll_path is not None:
        log.info("Using real storm b-roll clip: %s", broll_path.name)
    elif PINNED_BROLL_CLIP.exists():
        log.info("No synced real storm b-roll available -- using the illustrated pinned clip.")
        broll_path = PINNED_BROLL_CLIP
    else:
        log.error(
            "No storm b-roll available: %s is empty and %s is missing -- run "
            "scripts/sync_storm_broll.py or scripts/generate_storm_scene.py first.",
            STORM_BROLL_DIR,
            PINNED_BROLL_CLIP,
        )
        return 1

    broll_meta = _load_sidecar(broll_path)
    scene = _pick_scene()
    duration_s = random.uniform(MIN_DURATION_MINUTES * 60, MAX_DURATION_MINUTES * 60)

    log.info("Stage 1/4: baking filtered segment from %s", broll_path.name)
    seamless_clip = _prepare_seamless_loop_clip(broll_path)
    filtered_segment = _bake_filtered_segment(seamless_clip)
    if filtered_segment is None:
        log.error("Could not prepare a loopable video segment from %s", broll_path.name)
        return 1

    log.info("Stage 2/4: synthesizing rain/thunder bed")
    rain_bed_path = _prepare_rain_bed(seed=random.randint(0, 1_000_000))

    music_path: Path | None = None
    music_meta: dict | None = None
    if random.random() < MUSIC_LAYER_PROBABILITY:
        all_bgm_tracks = sorted(BGM_DIR.glob("jamendo_*.mp3"))
        if all_bgm_tracks:
            music_path = random.choice(all_bgm_tracks)
            music_meta = _load_sidecar(music_path)
            log.info("Stage 3/4: layering a quiet music track (%s)", music_path.name)
        else:
            log.info("Stage 3/4: no bgm tracks available, skipping the optional music layer")
    else:
        log.info("Stage 3/4: pure rain/thunder ambience (no music layer this time)")

    slug = f"ambience-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"storm-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    log.info("Stage 4/4: composing %.0fs storm ambience at %s", duration_s, video_path.name)
    if not _compose_storm(filtered_segment, rain_bed_path, music_path, video_path, duration_s):
        log.error("Storm ambience composition failed for %s", slug)
        return 1

    metadata = _build_metadata(scene, duration_s, video_path, slug, music_meta=music_meta, broll_meta=broll_meta)
    if BRAND_THUMBNAIL_IMAGE.exists():
        metadata["thumbnail"] = str(BRAND_THUMBNAIL_IMAGE)
    else:
        log.warning("Brand thumbnail image missing: %s -- YouTube will auto-pick a frame.", BRAND_THUMBNAIL_IMAGE)
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.0fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
