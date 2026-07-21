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
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ai_titling import generate_video_copy  # noqa: E402
from utils.storm_audio import generate_rain_bed, write_wav  # noqa: E402
from utils.storm_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_storm_short")

PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_storm_short_clip.mp4"
BRAND_THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "storm_short_scene_1080x1920.png"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_storm_short"

TARGET_W = 1080
TARGET_H = 1920
MIN_DURATION_S = 30.0
MAX_DURATION_S = 58.0
FADE_S = 1.5
RAIN_BED_SECONDS = 37.0  # short + non-matching period vs. the 14s video loop and the ambience pillar's 53s bed

CATEGORY = "storm_ambience"
SERIES_SUFFIX = "Shorts"
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


def _pick_scene() -> str:
    return random.choice(list(HOOK_BY_SCENE.keys())).title()


def _prepare_rain_bed(seed: int) -> Path:
    bed_path = TEMP_DIR / f"rain_bed_short_{seed}.wav"
    if bed_path.exists() and bed_path.stat().st_size > 0:
        return bed_path
    bed = generate_rain_bed(duration_s=RAIN_BED_SECONDS, seed=seed, thunder_count=random.randint(0, 1))
    write_wav(bed, bed_path)
    return bed_path


def _compose_short(broll_path: Path, rain_bed_path: Path, output_path: Path, duration_s: float) -> bool:
    fade_out_start = max(duration_s - FADE_S, 0.0)
    video_filter = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},"
        f"setsar=1,fade=t=in:st=0:d={FADE_S},fade=t=out:st={fade_out_start:.3f}:d={FADE_S}[v]"
    )
    audio_filter = f"afade=t=in:st=0:d={FADE_S},afade=t=out:st={fade_out_start:.3f}:d={FADE_S}[a]"
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
        str(rain_bed_path),
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
        "160k",
        "-ar",
        "44100",
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


def _build_metadata(scene: str, duration_s: float, video_path: Path, slug: str) -> dict:
    template_title = branded_title(scene)
    bucket = playlist_bucket_for_title(template_title)

    disclosure = (
        "The rain and thunder in this video are procedurally synthesized, not a looped recording "
        "-- no sample to run out of, no license to clear."
    )
    description_lines = [
        f"{scene.lower()} rain sounds with distant thunder -- a quick rain break to help you relax.",
        "",
        f"\U0001f327️ Part of the {bucket} collection on Amber Hours.",
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
        "packaging": {"pinned_comment": "What should the next rain Short sound like? \U0001f327️"},
        "pre_publish_audit": {"approved": True, "reason": "storm_ambience_no_claims_to_vet"},
        "source": "branding",
        "source_clip_id": "",
        "source_url": "",
        "source_license": "",
        "source_license_evidence": "",
        "bgm_track_id": "",
        "bgm_license_ccurl": "",
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if not PINNED_BROLL_CLIP.exists():
        log.error(
            "Pinned storm Short clip missing: %s -- run scripts/generate_storm_scene.py first.", PINNED_BROLL_CLIP
        )
        return 1

    scene = _pick_scene()
    duration_s = round(random.uniform(MIN_DURATION_S, MAX_DURATION_S), 1)
    rain_bed_path = _prepare_rain_bed(seed=random.randint(0, 1_000_000))

    slug = f"stormshort-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"storm-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    if not _compose_short(PINNED_BROLL_CLIP, rain_bed_path, video_path, duration_s):
        log.error("Storm Short composition failed for %s", slug)
        return 1

    metadata = _build_metadata(scene, duration_s, video_path, slug)
    if BRAND_THUMBNAIL_IMAGE.exists():
        metadata["thumbnail"] = str(BRAND_THUMBNAIL_IMAGE)
    else:
        log.warning("Brand thumbnail image missing: %s -- YouTube will auto-pick a frame.", BRAND_THUMBNAIL_IMAGE)
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.1fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
