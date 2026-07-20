#!/usr/bin/env python3
"""Generate one short horizontal lofi mix video: a looping b-roll clip +
exactly 3 Jamendo tracks back to back, no narration. Published hourly
as the companion to generate_lofi_short.py's vertical Shorts.

Companion to generate_lofi_short.py's vertical Shorts. Loops one fixed
committed clip (PINNED_BROLL_CLIP -- see its own comment; a different,
also-pinned clip from generate_lofi_short.py's and
scripts/live_stream_dynamic.py's own, so live/Shorts/mix each have a
distinct fixed visual) and bakes the same seamless crossfade loop
live_stream_dynamic.py uses so the clip has no visible jump cut at the
wrap-around point.

Rendering approach: the crossfade-baked clip and its scale/zoompan
filter are only ever encoded ONCE, against the clip's own short
duration (a few seconds of ffmpeg work). The output (duration = the
sum of the 3 chosen tracks) is then produced by remuxing that
already-encoded segment on a loop (`-stream_loop -1 -c:v copy`)
instead of re-encoding the whole runtime -- the same "no bake sized to
the loop length" principle live_stream_dynamic.py uses for its RTMP
relay, just aimed at a file instead of a stream.

Writes `_videos/mix-*.mp4` + matching `.json` that upload_youtube.py's
_collect_pending_meta() picks up (extended to recognize the "mix-"
prefix alongside "short-"/"roundup-").
"""

from __future__ import annotations

import json
import logging
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.lofi_branding import HOOK_BY_MOOD, branded_title, playlist_bucket_for_title  # noqa: E402
from utils.thumbnail_branding import brand_mix_thumbnail  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_lofi_mix")

# See generate_lofi_short.py's PINNED_BROLL_CLIP comment for why this is a
# single committed asset instead of a Pixabay-synced rotating pool.
PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_mix_clip.mp4"
BGM_DIR = ROOT / "_assets" / "audio" / "bgm"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_mix"

TARGET_W = 1920
TARGET_H = 1080
TARGET_FPS = 30
SONGS_PER_MIX = 3
LOOP_CROSSFADE_S = 1.0

CATEGORY = "lofi"
# See generate_lofi_short.py's SERIES_SUFFIX comment -- same fixed
# per-mood-bucket series naming, "Mix" suffix instead of "Shorts" so the
# two formats stay distinct series/playlists per theme.
SERIES_SUFFIX = "Mix"
YOUTUBE_CATEGORY_ID = "10"  # Music -- more accurate for a mix than the Shorts' default.
# Niche-first (chat, 2026-07-19): see generate_lofi_short.py's DEFAULT_TAGS
# comment -- same reasoning, "lofi hip hop radio" alone is Lofi Girl's turf.
DEFAULT_TAGS = [
    "lofi",
    "lofi mix",
    "anime lofi radio",
    "rainy night lofi",
    "midnight lofi",
    "sleep lofi",
    "amber hours",
]


def _load_sidecar(media_path: Path) -> dict:
    meta_path = media_path.with_suffix(".json")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _pick_mood() -> str:
    """See generate_lofi_short.py's identical helper: the pinned clip no
    longer varies, so mood is picked independently instead of derived from
    a per-video b-roll search query."""
    return random.choice(list(HOOK_BY_MOOD.keys())).title()


def _media_duration_s(path: Path) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _prepare_seamless_loop_clip(clip_path: Path) -> Path:
    """Bake a short crossfade between the clip's tail and head once, so
    looping it via -stream_loop has no visible hard cut at the seam.
    Same technique as live_stream_dynamic.py._prepare_seamless_loop_clip."""
    out_path = TEMP_DIR / f"seamless_{clip_path.stem}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    duration = _media_duration_s(clip_path)
    fade = min(LOOP_CROSSFADE_S, duration / 6) if duration > 3 else 0.0
    if fade <= 0:
        return clip_path

    # `mid` must be concat's FIRST input, `blend` its second. `mid` spans
    # almost the whole clip (fade..duration-fade) and its trim filter can
    # start emitting frames the instant ffmpeg starts demuxing; `blend`
    # (xfade of `end`+`start`) can't emit anything until the demuxer has
    # read all the way to the clip's tail. With concat's original
    # [blend][mid] order, concat waits on segment 0 (blend) first, so
    # every one of `mid`'s frames backs up unread in its filter queue for
    # the whole clip -- confirmed locally: this deadlocks ffmpeg's internal
    # frame queue ("100 buffers queued... something may be wrong", process
    # never finishes) on the pinned 60fps clip, and is what CI's "runner
    # received a shutdown signal" / exit 143 was actually memory pressure
    # from -- the same failure mode this function's docstring already
    # flags for live_stream_dynamic.py's identical graph. [mid][blend]
    # instead matches the graph's natural read order (mid drains as it's
    # produced; only `start`'s ~1s has to wait) and finishes in seconds
    # with no queued-frames warning.
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


def _bake_filtered_segment(seamless_clip: Path) -> Path | None:
    """Apply the scale/crop/zoompan filter chain ONCE against the short
    crossfade-baked clip, producing a small already-encoded segment that
    the final render can loop with -c:v copy (no per-frame work over the
    full hour)."""
    out_path = TEMP_DIR / f"filtered_{seamless_clip.stem}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    video_filter = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},fps={TARGET_FPS},"
        f"zoompan=z='min(zoom+0.0003,1.06)':d=1:s={TARGET_W}x{TARGET_H}:fps={TARGET_FPS},"
        "setsar=1,format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(seamless_clip),
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
        "60",
        "-keyint_min",
        "60",
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


def _build_bgm_playlist(tracks: list[Path]) -> Path | None:
    """Concatenate exactly SONGS_PER_MIX tracks (already chosen by the
    caller) into one file, same approach as
    live_stream_dynamic.py._build_bgm_playlist."""
    if not tracks:
        return None
    playlist_path = TEMP_DIR / "playlist.mp3"
    list_path = TEMP_DIR / "playlist_concat.txt"
    list_path.write_text(
        "\n".join(f"file '{track.resolve()}'" for track in tracks) + "\n",
        encoding="utf-8",
    )
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(playlist_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as exc:
        log.error("Failed to build bgm playlist: %s", exc)
        return None
    if result.returncode != 0 or not playlist_path.exists():
        log.error("ffmpeg playlist concat exited %d: %s", result.returncode, result.stderr[-500:])
        return None
    log.info("Built bgm playlist from %d track(s).", len(tracks))
    return playlist_path


def _compose_mix(filtered_segment: Path, playlist_path: Path, output_path: Path, duration_s: float) -> bool:
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
        str(playlist_path),
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
        "128k",
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


def _extract_thumbnail(video_path: Path, thumb_path: Path, timestamp_s: float = 5.0) -> bool:
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


def _build_metadata(
    mood: str, broll_meta: dict, bgm_metas: list[dict], duration_s: float, video_path: Path, slug: str
) -> dict:
    minutes = max(1, round(duration_s / 60))
    title = branded_title(mood, suffix=f"({minutes} Min Mix)")
    photographer = str(broll_meta.get("photographer") or "")

    bucket = playlist_bucket_for_title(title)
    description_lines = [
        f"{SONGS_PER_MIX} songs of {mood.lower()} lofi beats -- chill music to relax, study or unwind to.",
        "",
        f"\U0001f319 Part of the {bucket} collection on Amber Hours -- rainy night "
        "anime lofi, cozy beats for late nights, playing 24/7 on the channel live stream.",
        "",
    ]
    credits = []
    for bgm_meta in bgm_metas:
        track_name = str(bgm_meta.get("track_name") or "").strip()
        if not track_name:
            continue
        artist_name = str(bgm_meta.get("artist_name") or "").strip()
        license_url = str(bgm_meta.get("license_ccurl") or "").strip()
        credit = f'\U0001f3b5 "{track_name}"'
        if artist_name:
            credit += f" by {artist_name}"
        if license_url:
            credit += f" ({license_url})"
        credits.append(credit)
    if credits:
        description_lines.append("Music:")
        description_lines.extend(credits)
        description_lines.append("")
    if photographer:
        description_lines.append(f"\U0001f3ac Visual: Pixabay / {photographer}")

    # Mood tag leads (not trails) DEFAULT_TAGS -- see generate_lofi_short.py's
    # identical comment: fixes every unrelated video's title-collision dedup
    # landing on the same suffix regardless of its own mood.
    tags = [mood.lower()] if mood.lower() not in {tag.lower() for tag in DEFAULT_TAGS} else []
    tags += DEFAULT_TAGS

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    return {
        "title": title,
        "description": "\n".join(description_lines).strip(),
        "category": CATEGORY,
        "series": f"{bucket} {SERIES_SUFFIX}",
        "tags": tags,
        "video": str(video_path),
        "duration_s": duration_s,
        "story_id": slug,
        "is_short": False,
        "youtube_category_id": YOUTUBE_CATEGORY_ID,
        "packaging": {"pinned_comment": "What should the next mix be? \U0001f319"},
        "pre_publish_audit": {"approved": True, "reason": "lofi_no_claims_to_vet"},
        "source": "pixabay",
        "pexels_video_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
        "bgm_track_ids": [str(m.get("track_id") or "") for m in bgm_metas if m.get("track_id")],
        # An hourly slot key -- distinct from the 10-minute canonical grid
        # the Shorts publish_slot uses (a "mix-HH" prefix), so
        # upload_youtube.py's per-slot idempotency check
        # (duplicate_slot_uploaded) never mistakes this for -- or gets
        # shadowed by -- a Short published in the same clock hour. Still
        # naturally caught as a real duplicate if this job somehow runs
        # twice in the same hour.
        "publish_slot": f"mix-{now.hour:02d}",
        "publish_slot_key": f"mix-{today}-{now.hour:02d}",
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if not PINNED_BROLL_CLIP.exists():
        log.error("Pinned mix b-roll clip missing: %s", PINNED_BROLL_CLIP)
        return 1
    broll_path = PINNED_BROLL_CLIP

    all_bgm_tracks = sorted(BGM_DIR.glob("jamendo_*.mp3"))
    if len(all_bgm_tracks) < SONGS_PER_MIX:
        log.error(
            "Need %d bgm tracks for a mix, only %d available in %s -- run "
            "scripts/sync_jamendo_music.py first.",
            SONGS_PER_MIX,
            len(all_bgm_tracks),
            BGM_DIR,
        )
        return 1
    bgm_tracks = random.sample(all_bgm_tracks, SONGS_PER_MIX)

    broll_meta = _load_sidecar(broll_path)
    bgm_metas = [_load_sidecar(t) for t in bgm_tracks]
    mood = _pick_mood()

    log.info("Stage 1/4: preparing seamless loop clip from %s", broll_path.name)
    seamless_clip = _prepare_seamless_loop_clip(broll_path)
    log.info("Stage 2/4: baking filtered segment from %s", seamless_clip.name)
    filtered_segment = _bake_filtered_segment(seamless_clip)
    if filtered_segment is None:
        log.error("Could not prepare a loopable video segment from %s", broll_path.name)
        return 1

    log.info("Stage 3/4: building bgm playlist from %d track(s)", len(bgm_tracks))
    playlist_path = _build_bgm_playlist(bgm_tracks)
    if playlist_path is None:
        log.error("Could not build a bgm playlist.")
        return 1
    duration_s = sum(_media_duration_s(track) for track in bgm_tracks)
    if duration_s <= 0:
        log.error("Could not determine playlist duration from the selected tracks.")
        return 1

    slug = f"lofimix-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"mix-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    log.info("Stage 4/4: composing %.0fs mix at %s", duration_s, video_path.name)
    if not _compose_mix(filtered_segment, playlist_path, video_path, duration_s):
        log.error("Mix composition failed for %s", slug)
        return 1

    metadata = _build_metadata(mood, broll_meta, bgm_metas, duration_s, video_path, slug)
    thumb_path = VIDEOS_DIR / f"mix-{slug}_thumb.jpg"
    if _extract_thumbnail(video_path, thumb_path):
        try:
            brand_mix_thumbnail(thumb_path, mood)
        except Exception as exc:
            log.warning("thumbnail branding failed for %s, keeping raw frame: %s", slug, exc)
        metadata["thumbnail"] = str(thumb_path)
    else:
        log.warning("No custom thumbnail for %s -- YouTube will auto-pick a frame.", slug)
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.0fs): %s", video_path.name, duration_s, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
