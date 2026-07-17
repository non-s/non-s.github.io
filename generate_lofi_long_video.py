#!/usr/bin/env python3
"""Compose a long silent lofi loop video for the 24/7 live stream relay.

Fetches fresh landscape lofi b-roll clips, turns each into a fixed-length
silent segment, and concatenates them into one _videos/long_video_*.mp4.
The live relay (scripts/live_stream_dynamic.py) loops this file
indefinitely, mixing in a track from the local Jamendo bgm library on the
way in since this generator only produces picture -- no audio, no
narration, no per-run bgm decision.

This is the lofi replacement for generate_long_video.py, which built each
segment from a narrated, multi-agent-scripted nature fact (TTS + burned-in
captions). A lofi 24/7 background has neither: it is meant to sit quietly
in a tab while people study or relax.
"""

from __future__ import annotations

import logging
import random
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.broll import BrollClip, download_clip, fetch_broll_clips  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

VIDEOS_DIR = Path("_videos")
TEMP_DIR = VIDEOS_DIR / "long_video_temp"

TARGET_W = 1920
TARGET_H = 1080
TARGET_FPS = 30
SEGMENT_DURATION_S = 75.0
SEGMENT_COUNT = 12

LOFI_QUERIES = [
    "rain window cozy",
    "fireplace night cozy room",
    "coffee cup steam desk",
    "night city lights window",
    "study desk lamp night",
    "snow falling window cozy",
    "candle warm room night",
    "ocean waves night calm",
    "bedroom plants sunlight morning",
    "cat sleeping cozy blanket",
    "library books reading corner",
    "forest rain window view",
]


def _build_segment(clip_path: Path, output_path: Path, duration_s: float) -> bool:
    video_filter = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},fps={TARGET_FPS},"
        f"zoompan=z='min(zoom+0.0004,1.08)':d=1:s={TARGET_W}x{TARGET_H}:fps={TARGET_FPS},"
        f"setsar=1"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(clip_path),
        "-vf",
        video_filter,
        "-t",
        f"{duration_s:.3f}",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as exc:
        log.error("ffmpeg failed to run for %s: %s", clip_path.name, exc)
        return False
    if result.returncode != 0:
        log.error("ffmpeg exited %d for %s: %s", result.returncode, clip_path.name, result.stderr[-500:])
        return False
    return output_path.exists() and output_path.stat().st_size > 0


def _concat_segments(segment_paths: list[Path], output_path: Path) -> bool:
    list_path = TEMP_DIR / "concat.txt"
    list_path.write_text(
        "\n".join(f"file '{path.resolve()}'" for path in segment_paths) + "\n",
        encoding="utf-8",
    )
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as exc:
        log.error("ffmpeg concat failed to run: %s", exc)
        return False
    if result.returncode != 0:
        log.error("ffmpeg concat exited %d: %s", result.returncode, result.stderr[-500:])
        return False
    return output_path.exists() and output_path.stat().st_size > 0


def _fetch_unique_clips(want_n: int) -> list[BrollClip]:
    queries = random.sample(LOFI_QUERIES, k=min(want_n, len(LOFI_QUERIES)))
    seen_urls: set[str] = set()
    clips: list[BrollClip] = []
    for query in queries:
        for clip in fetch_broll_clips(query, want_n=2, orientation="landscape"):
            if clip.download_url in seen_urls:
                continue
            seen_urls.add(clip.download_url)
            clips.append(clip)
            break
        if len(clips) >= want_n:
            break
    return clips


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True)

    clips = _fetch_unique_clips(SEGMENT_COUNT)
    if not clips:
        log.error("No lofi b-roll clips available to build the long video.")
        return 1

    segment_paths: list[Path] = []
    for index, clip in enumerate(clips):
        raw_path = TEMP_DIR / f"raw_{index}.mp4"
        if not download_clip(clip, raw_path):
            log.warning("Failed to download clip %d, skipping.", index)
            continue
        segment_path = TEMP_DIR / f"segment_{index}.mp4"
        if _build_segment(raw_path, segment_path, SEGMENT_DURATION_S):
            segment_paths.append(segment_path)
        else:
            log.warning("Failed to build segment %d, skipping.", index)

    if not segment_paths:
        log.error("No segments were built successfully.")
        return 1

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = VIDEOS_DIR / f"long_video_{date_str}.mp4"
    if not _concat_segments(segment_paths, output_path):
        log.error("Failed to concatenate segments into %s.", output_path)
        return 1

    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    log.info(
        "Generated %s: %d segment(s), ~%.1f minutes.",
        output_path.name,
        len(segment_paths),
        len(segment_paths) * SEGMENT_DURATION_S / 60,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
