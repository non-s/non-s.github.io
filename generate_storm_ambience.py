#!/usr/bin/env python3
"""Generate one long-form "real rain & thunder ambience" video: the
animated storm scene looped under a procedurally-synthesized rain/thunder
bed. No narration, no music layer -- pure rain and thunder is the whole
point of this niche (chat, 2026-07-22: the channel owner tried Jamendo as
a background-music layer and decided against it -- Jamendo's catalog is
music, not sound effects, so even its best-tagged "rain" results are
ambient/new-age *songs* loosely tagged nature, not rain sound, and the
commercially-safe yield was too thin (~1.5%-6% in live checks) to be
worth the added complexity for a layer that didn't serve the format).

New pillar (growth pass, 2026-07-21): picked over another lofi variant
specifically to stop competing on "anime lofi" -- one of YouTube's most
saturated searches -- and instead target the real, much larger "rain
sounds for sleep" / "thunderstorm ambience" search intent (see
utils/storm_branding.py's module docstring). Still published as "Amber
Hours".

Rendering follows a "bake once, loop cheaply" approach: the pinned storm
clip's scale/zoompan filter chain runs ONCE against its own short
duration, and the *encoded* result is looped via `-stream_loop -1 -c:v
copy` to fill the target runtime, rather than re-encoding video for the
whole length. Renders at real 4K (3840x2160, chat 2026-07-21: the channel
owner explicitly asked for it across every format, accepting the
reliability tradeoff -- see utils/broll.py's fetch_pixabay() comment for
the OOM risk this reintroduces and why it's accepted rather than newly
mitigated). The rain/thunder bed (utils/storm_audio.py) is a WAV loop
with its own, deliberately non-matching period vs. the video loop, so the
combined video is never audibly/visibly repeating in lockstep even
though each layer loops individually.

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
from utils.storm_audio import generate_rain_bed, write_wav  # noqa: E402
from utils.storm_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_storm_ambience")

# One fixed, real Pixabay clip (chat, 2026-07-21: the channel owner picked
# this specific willow-branches-in-the-rain clip by hand and asked for it
# to be the one clip this format always uses -- not a random pick from a
# synced pool) -- see _assets/video/pinned_storm_ambience.json for its
# source/license. Falls back to the illustrated pinned clip only if this
# file is ever missing, so the pipeline never *requires* it to produce a
# video.
PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_storm_ambience.mp4"
FALLBACK_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_storm_clip.mp4"
# A real frame extracted from PINNED_BROLL_CLIP itself (chat, 2026-07-22:
# the illustrated thumbnail below was misleading once the video content
# became real footage -- a viewer searching for real rain sounds saw a
# cartoon-style preview, then real footage on click). Falls back to the
# illustration only if this extracted frame is ever missing.
BRAND_THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "storm_ambience_thumbnail.jpg"
FALLBACK_THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "storm_scene_1920x1080.png"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_storm"

TARGET_W = 3840
TARGET_H = 2160
TARGET_FPS = 20  # matches the illustrated fallback clip's own fps; the pinned real clip is resampled to it too

CATEGORY = "storm_ambience"
SERIES_SUFFIX = "Ambience"
YOUTUBE_CATEGORY_ID = "10"  # Music -- consistent with the rest of the channel's uploads

RAIN_BED_SECONDS = 53.0  # deliberately not a round multiple of the video loop's 14s -- see module docstring
LOOP_CROSSFADE_S = 1.0  # same value/technique as generate_lofi_mix.py's identical constant
MIN_DURATION_MINUTES = float(os.environ.get("STORM_MIN_DURATION_MINUTES", "45"))
MAX_DURATION_MINUTES = float(os.environ.get("STORM_MAX_DURATION_MINUTES", "75"))

# Real pt-BR search-intent tags for this niche (content language pivot,
# chat 2026-07-21) -- actual phrases people search, not machine
# transliterations of the earlier English tag set.
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
        "-filter_complex",
        "[1:a]volume=1.0[a]",
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
    "A chuva e o trovão deste vídeo são sintetizados por computador, não uma gravação em loop "
    "-- nenhuma amostra para se esgotar, nenhuma licença para verificar."
)


def _build_metadata(
    scene: str,
    duration_s: float,
    video_path: Path,
    slug: str,
    *,
    broll_meta: dict,
) -> dict:
    hours = duration_s / 3600
    duration_label = f"({hours:.1f} Horas)" if hours >= 1 else f"({max(1, round(duration_s / 60))} Min)"
    template_title = branded_title(scene, suffix=duration_label)
    bucket = playlist_bucket_for_title(template_title)

    description_lines = [
        "Som real de chuva com trovão ao longe -- ambiência para ajudar você a dormir, "
        "focar ou relaxar, sem narração.",
        "",
        f"\U0001f327️ Parte da coleção {bucket} no Amber Hours.",
        "",
        f"\U0001f3a7 {_ALWAYS_ON_DISCLOSURE}",
    ]

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
        "packaging": {"pinned_comment": "Como deveria ser o próximo som de tempestade? \U0001f327️"},
        "pre_publish_audit": {"approved": True, "reason": "storm_ambience_no_claims_to_vet"},
        "source": str(broll_meta.get("source") or "branding"),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
        # A daily-multiple-slots key, distinct from the Shorts/mix grids --
        # see generate_lofi_mix.py's identical publish_slot comment for why
        # this matters for upload_youtube.py's per-slot idempotency check.
        "publish_slot": f"storm-{now.hour:02d}",
        "publish_slot_key": f"storm-{today}-{now.hour:02d}",
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if PINNED_BROLL_CLIP.exists():
        broll_path = PINNED_BROLL_CLIP
    elif FALLBACK_BROLL_CLIP.exists():
        log.warning("Pinned real ambience clip missing -- using the illustrated fallback.")
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
    duration_s = random.uniform(MIN_DURATION_MINUTES * 60, MAX_DURATION_MINUTES * 60)

    log.info("Stage 1/3: baking filtered segment from %s", broll_path.name)
    seamless_clip = _prepare_seamless_loop_clip(broll_path)
    filtered_segment = _bake_filtered_segment(seamless_clip)
    if filtered_segment is None:
        log.error("Could not prepare a loopable video segment from %s", broll_path.name)
        return 1

    log.info("Stage 2/3: synthesizing rain/thunder bed")
    rain_bed_path = _prepare_rain_bed(seed=random.randint(0, 1_000_000))

    slug = f"ambience-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"storm-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    log.info("Stage 3/3: composing %.0fs storm ambience at %s", duration_s, video_path.name)
    if not _compose_storm(filtered_segment, rain_bed_path, video_path, duration_s):
        log.error("Storm ambience composition failed for %s", slug)
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
    log.info("Generated %s (%.0fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
