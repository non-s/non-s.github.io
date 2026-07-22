#!/usr/bin/env python3
"""Generate one long-form white/pink/brown-noise ambience video: a real,
calm Pixabay nursery/night clip looped under procedurally-synthesized
noise-color audio (utils/noise_audio.py). No narration, no music layer --
plain noise-color sound is the actual product this audience (parents
settling a baby, people studying/focusing, tinnitus maskers) searches
for, distinct from the rain pillar's rain/thunder texture. Third content
pillar (acting-founder growth pass, 2026-07-22) -- see
utils/noise_audio.py's module docstring for the full reasoning and why it
carries the same "Amber Hours" brand as the rain pillar.

Duration/timeout arithmetic (why 3-5 hours is safe here): the rain
pillar's own real run today rendered a 3417s (~57min) video -- baking the
filtered segment + synthesizing the audio bed took under 90s combined,
and the final `-c:v copy` compose step (the only part of the pipeline
whose cost scales with target duration, since the baked video segment is
stream-copied, not re-encoded, and AAC audio encoding is fast relative to
realtime) took roughly 2.5 minutes for that ~57-minute target. Scaling
that same rate linearly to a 300-minute (5-hour) target predicts roughly
13 minutes of compose time -- comfortable under the 60-minute job timeout
this script's workflow uses, with real margin left for checkout/ffmpeg-
install/pip-install overhead (~2-3 minutes) and the one-time segment bake
(~1 minute). This is an extrapolation from one data point, not a proven
rate, so BABY_NOISE_MAX_DURATION_MINUTES stops well short of the "8-12
hour all night" videos common in this niche -- once real CI run logs
confirm the actual scaling at this range, extending further is a safe,
easy next step (just raise the env var), not a code change.

Writes `_videos/noise-*.mp4` + matching `.json` that
upload_youtube.py's `_collect_pending_meta()` picks up (extended to
recognize the "noise-" prefix).
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

from utils.ai_titling import generate_baby_noise_copy  # noqa: E402
from utils.baby_noise_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title  # noqa: E402
from utils.broll import pick_noise_broll_file  # noqa: E402
from utils.noise_audio import NOISE_COLORS, generate_noise_bed, write_wav  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_baby_noise_ambience")

# Rotating real-footage pool (scripts/sync_noise_broll.py) -- no fixed
# pinned clip and no illustrated fallback exist for this pillar yet (see
# scripts/sync_noise_broll.py's module docstring for why: no one was
# available tonight to hand-pick specific clips the way the channel
# owner did for the rain pillar). A completely empty pool skips this run
# rather than faking a placeholder, same as generate_cute_animal_short.py.
NOISE_BROLL_DIR = ROOT / "_assets" / "video" / "noise_broll"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_baby_noise"

TARGET_W = 3840
TARGET_H = 2160
# 24fps, not the rain pillar's 20 (which matches its hand-drawn
# illustration's own frame count) -- this pillar has no illustration to
# match, and a mostly-static calm scene doesn't need more than 24fps;
# keeping it modest also keeps the multi-hour baked segment's bitrate (and
# therefore the final render's file size) down.
TARGET_FPS = 24

CATEGORY = "baby_noise_ambience"
SERIES_SUFFIX = "Ambience"
YOUTUBE_CATEGORY_ID = "10"  # Music -- consistent with the rest of the channel's uploads

NOISE_BED_SECONDS = 41.0  # deliberately non-round, non-matching the video loop's own (real-clip-dependent) period
LOOP_CROSSFADE_S = 1.0  # same value/technique as generate_storm_ambience.py's identical constant
MIN_DURATION_MINUTES = float(os.environ.get("BABY_NOISE_MIN_DURATION_MINUTES", "180"))
MAX_DURATION_MINUTES = float(os.environ.get("BABY_NOISE_MAX_DURATION_MINUTES", "300"))

# Real pt-BR search-intent tags for this niche -- deliberately distinct
# from the rain pillar's DEFAULT_TAGS (see utils/baby_noise_branding.py's
# docstring for why the two vocabularies serve different, if adjacent,
# search intent).
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


def _load_sidecar(media_path: Path) -> dict:
    meta_path = media_path.with_suffix(".json")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _pick_scene() -> str:
    return random.choice(list(HOOK_BY_SCENE.keys())).title()


def _pick_color() -> str:
    return random.choice(sorted(NOISE_COLORS))


def _media_duration_s(path: Path) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _prepare_seamless_loop_clip(clip_path: Path) -> Path:
    """Same technique as generate_storm_ambience.py's identical helper: a
    short crossfade between the clip's tail and head so -stream_loop has
    no visible hard cut. Real Pixabay footage has no seamless-loop
    guarantee by construction, unlike a hand-drawn illustration."""
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
    """Same approach as generate_storm_ambience.py's identical helper:
    apply the scale/crop filter chain ONCE against the pinned clip's own
    short duration, producing a small already-encoded segment the final
    render can loop with -c:v copy -- this is what keeps the final
    compose step's cost independent of the target runtime (see this
    module's docstring's timeout arithmetic)."""
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


def _prepare_noise_bed(seed: int, color: str) -> Path:
    bed_path = TEMP_DIR / f"noise_bed_{color}_{seed}.wav"
    if bed_path.exists() and bed_path.stat().st_size > 0:
        return bed_path
    bed = generate_noise_bed(duration_s=NOISE_BED_SECONDS, seed=seed, color=color)
    write_wav(bed, bed_path)
    return bed_path


def _extract_thumbnail_frame(clip_path: Path, seed: int) -> Path | None:
    """Grab one real frame from the actual clip this run used -- same
    reasoning and technique as generate_cute_animal_short.py's identical
    helper, applied from day one here too (never ship the rain pillar's
    original illustrated-vs-real thumbnail mismatch a third time)."""
    out_path = TEMP_DIR / f"thumb_{seed}.jpg"
    duration = _media_duration_s(clip_path)
    offset = min(2.0, max(duration / 3, 0.0))
    cmd = ["ffmpeg", "-y", "-i", str(clip_path), "-ss", f"{offset:.2f}", "-vframes", "1", str(out_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as exc:
        log.warning("Failed to extract thumbnail frame: %s", exc)
        return None
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        log.warning("ffmpeg thumbnail-frame extraction failed: %s", result.stderr[-500:])
        return None
    return out_path


def _compose_ambience(filtered_segment: Path, noise_bed_path: Path, output_path: Path, duration_s: float) -> bool:
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
        str(noise_bed_path),
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
        # 2400s (40min), up from the rain pillar's 1800s: this pillar's
        # target duration is up to ~3x longer (300min vs storm's 75min
        # max) -- see this module's docstring for the extrapolated
        # compose-time math this timeout is padded well above.
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
    except Exception as exc:
        log.error("ffmpeg failed to run: %s", exc)
        return False
    if result.returncode != 0:
        log.error("ffmpeg exited %d: %s", result.returncode, result.stderr[-2000:])
        return False
    return output_path.exists() and output_path.stat().st_size > 0


_ALWAYS_ON_DISCLOSURE = (
    "O som deste vídeo é ruído (branco/rosa/marrom) sintetizado por computador, não uma gravação em loop "
    "-- nenhuma amostra para se esgotar, nenhuma licença para verificar."
)


def _build_metadata(
    scene: str,
    color: str,
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

    color_label = {"white": "branco", "pink": "rosa", "brown": "marrom"}[color]
    description_lines = [
        f"Ruído {color_label} constante e real -- ambiência para ajudar seu bebê a dormir, "
        "ou para você focar/estudar/relaxar, sem narração.",
        "",
        f"\U0001f50a Parte da coleção {bucket} no Amber Hours.",
        "",
        f"\U0001f3a7 {_ALWAYS_ON_DISCLOSURE}",
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
        "packaging": {
            "pinned_comment": "Qual cor de ruído ajuda mais no seu bebê dormir: branco, rosa ou marrom? \U0001f50a"
        },
        "pre_publish_audit": {"approved": True, "reason": "baby_noise_no_claims_to_vet"},
        "source": str(broll_meta.get("source") or ""),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
        # A daily-multiple-slots key, distinct from the storm/animal grids
        # -- see generate_storm_ambience.py's identical publish_slot
        # comment for why this matters for upload_youtube.py's per-slot
        # idempotency check.
        "publish_slot": f"noise-{now.hour:02d}",
        "publish_slot_key": f"noise-{today}-{now.hour:02d}",
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
    duration_s = random.uniform(MIN_DURATION_MINUTES * 60, MAX_DURATION_MINUTES * 60)

    log.info("Stage 1/3: baking filtered segment from %s", broll_path.name)
    seamless_clip = _prepare_seamless_loop_clip(broll_path)
    filtered_segment = _bake_filtered_segment(seamless_clip)
    if filtered_segment is None:
        log.error("Could not prepare a loopable video segment from %s", broll_path.name)
        return 1

    log.info("Stage 2/3: synthesizing %s noise bed", color)
    noise_bed_path = _prepare_noise_bed(seed=random.randint(0, 1_000_000), color=color)

    slug = f"ambience-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"noise-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    log.info("Stage 3/3: composing %.0fs %s-noise ambience at %s", duration_s, color, video_path.name)
    if not _compose_ambience(filtered_segment, noise_bed_path, video_path, duration_s):
        log.error("Baby-noise ambience composition failed for %s", slug)
        return 1

    metadata = _build_metadata(scene, color, duration_s, video_path, slug, broll_meta=broll_meta)
    thumbnail_path = _extract_thumbnail_frame(broll_path, seed=random.randint(0, 1_000_000))
    if thumbnail_path is not None:
        metadata["thumbnail"] = str(thumbnail_path)
    else:
        log.warning("Could not extract a real thumbnail frame -- YouTube will auto-pick one.")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.0fs, %s): %s", video_path.name, duration_s, color, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
