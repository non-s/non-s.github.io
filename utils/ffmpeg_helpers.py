#!/usr/bin/env python3
"""Shared ffmpeg/ffprobe helpers extracted from the six video generators
(generate_storm_ambience, generate_storm_short, generate_baby_noise_ambience,
generate_baby_noise_short, generate_classical_ambience, generate_cute_animal_short).

These functions were previously copy-pasted — bodies byte-identical apart
from docstring wording — across up to six generator modules.  The
per-module constants they depend on (``TEMP_DIR``, ``LOOP_CROSSFADE_S``,
``TARGET_W``, ``TARGET_H``, ``TARGET_FPS``, ``FADE_S``) are now passed as
keyword/positional arguments so each generator can supply its own values
without duplicating logic.

The public names here are the un-underscored forms; each generator module
re-exports aliases with the original ``_``-prefixed names for backward
compatibility (tests may import ``from generate_storm_ambience import
_prepare_seamless_loop_clip``).
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

log = logging.getLogger("utils.ffmpeg_helpers")


# --------------------------------------------------------------------------- #
#  _load_sidecar  (was duplicated in all 6 generators)
# --------------------------------------------------------------------------- #
def load_sidecar(media_path: Path) -> dict:
    """Read the ``.json`` sidecar next to *media_path* and return it as a
    dict.  Returns ``{}`` on any read/parse error or non-dict content."""
    meta_path = media_path.with_suffix(".json")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- #
#  _media_duration_s  (was duplicated in all 6 generators)
# --------------------------------------------------------------------------- #
def media_duration_s(path: Path) -> float:
    """Return the media duration in seconds via ``ffprobe``, or ``0.0`` on
    any error."""
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
#  _prepare_seamless_loop_clip  (was duplicated in all 6 generators)
# --------------------------------------------------------------------------- #
def prepare_seamless_loop_clip(
    clip_path: Path,
    *,
    temp_dir: Path,
    loop_crossfade_s: float = 1.0,
    logger: logging.Logger | None = None,
) -> Path:
    """Bake a short crossfade between the clip's tail and head once, so
    looping it via ``-stream_loop`` has no visible hard cut/motion-snap at
    the seam.

    Parameters
    ----------
    clip_path:
        Source clip to make seamless.
    temp_dir:
        Directory for the baked output file (each generator's ``TEMP_DIR``).
    loop_crossfade_s:
        Maximum crossfade duration in seconds (each generator's
        ``LOOP_CROSSFADE_S``).
    logger:
        Optional logger; defaults to this module's logger.

    Returns the baked seamless clip path, or *clip_path* itself if no
    crossfade was needed or baking failed (the caller can then loop the
    raw clip as a fallback).
    """
    lg = logger or log
    out_path = temp_dir / f"seamless_{clip_path.stem}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    duration = media_duration_s(clip_path)
    fade = min(loop_crossfade_s, duration / 6) if duration > 3 else 0.0
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
        lg.warning("Failed to bake seamless loop clip, using raw clip instead: %s", exc)
        return clip_path
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        lg.warning("ffmpeg seamless-loop bake failed, using raw clip instead: %s", result.stderr[-500:])
        return clip_path
    lg.info("Baked seamless loop clip from %s (crossfade=%.2fs).", clip_path.name, fade)
    return out_path


# --------------------------------------------------------------------------- #
#  _bake_filtered_segment  (was duplicated in storm_ambience,
#  baby_noise_ambience, classical_ambience)
# --------------------------------------------------------------------------- #
def bake_filtered_segment(
    clip_path: Path,
    *,
    temp_dir: Path,
    target_w: int,
    target_h: int,
    target_fps: int,
    gop_size: int = 40,
    logger: logging.Logger | None = None,
) -> Path | None:
    """Apply the scale/crop/fps filter chain ONCE against the pinned clip's
    own short duration, producing a small already-encoded segment the
    final render can loop with ``-c:v copy``.

    Parameters
    ----------
    clip_path:
        Source clip (typically the seamless-looped clip).
    temp_dir:
        Directory for the baked output (each generator's ``TEMP_DIR``).
    target_w, target_h, target_fps:
        Resolution and frame rate to bake to.
    gop_size:
        GOP / keyint value.  Storm and baby-noise pillars use 40;
        classical pillar uses 60 (matches the clip's own frame rate).
    logger:
        Optional logger; defaults to this module's logger.

    Returns the baked segment path, or ``None`` on failure.
    """
    lg = logger or log
    out_path = temp_dir / f"filtered_{clip_path.stem}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    video_filter = (
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},fps={target_fps},setsar=1,format=yuv420p"
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
        str(target_fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-profile:v",
        "high",
        "-g",
        str(gop_size),
        "-keyint_min",
        str(gop_size),
        "-sc_threshold",
        "0",
        "-crf",
        "20",
        str(out_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as exc:
        lg.error("Failed to bake filtered segment: %s", exc)
        return None
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        lg.error("ffmpeg filtered-segment bake failed: %s", result.stderr[-1500:])
        return None
    return out_path


# --------------------------------------------------------------------------- #
#  _extract_thumbnail_frame  (was duplicated in baby_noise_ambience,
#  baby_noise_short, cute_animal_short)
# --------------------------------------------------------------------------- #
def extract_thumbnail_frame(
    clip_path: Path,
    seed: int,
    *,
    temp_dir: Path,
    logger: logging.Logger | None = None,
) -> Path | None:
    """Grab one real frame from *clip_path* — a couple seconds in (not
    frame 0, which can land on an encoder artifact) — and write it as a
    JPEG to *temp_dir*.

    Parameters
    ----------
    clip_path:
        Source clip to extract a frame from.
    seed:
        Unique seed used to generate the output filename (avoids
        collisions when multiple thumbnails are extracted per run).
    temp_dir:
        Directory for the output JPEG.
    logger:
        Optional logger; defaults to this module's logger.

    Returns the thumbnail path, or ``None`` on failure.
    """
    lg = logger or log
    out_path = temp_dir / f"thumb_{seed}.jpg"
    duration = media_duration_s(clip_path)
    offset = min(2.0, max(duration / 3, 0.0))
    cmd = ["ffmpeg", "-y", "-i", str(clip_path), "-ss", f"{offset:.2f}", "-vframes", "1", str(out_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as exc:
        lg.warning("Failed to extract thumbnail frame: %s", exc)
        return None
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        lg.warning("ffmpeg thumbnail-frame extraction failed: %s", result.stderr[-500:])
        return None
    return out_path


# --------------------------------------------------------------------------- #
#  _compose_short  (was duplicated in storm_short, baby_noise_short,
#  cute_animal_short)
# --------------------------------------------------------------------------- #
def compose_short(
    broll_path: Path,
    audio_path: Path | None,
    output_path: Path,
    duration_s: float,
    *,
    target_w: int,
    target_h: int,
    fade_s: float = 1.5,
    logger: logging.Logger | None = None,
) -> bool:
    """Compose a vertical Short: loop the b-roll clip under an audio bed
    (rain, noise, or jazz), with fade-in/out on both video and audio, and
    a ``-t`` cutoff at *duration_s*.

    Parameters
    ----------
    broll_path:
        Seamless-looped b-roll clip to loop as the video source.
    audio_path:
        Audio bed to loop.  If ``None``, silent audio is synthesized
        (cute-animal pillar's graceful degradation when the jazz library
        is empty).
    output_path:
        Destination ``.mp4`` path.
    duration_s:
        Target duration in seconds (the ``-t`` cutoff).
    target_w, target_h:
        Output resolution (e.g. 2160×3840 for 4K-vertical, 1080×1920 for
        standard vertical).
    fade_s:
        Fade in/out duration in seconds.
    logger:
        Optional logger; defaults to this module's logger.

    Returns ``True`` if the output file exists and is non-empty.
    """
    lg = logger or log
    fade_out_start = max(duration_s - fade_s, 0.0)
    video_filter = (
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},"
        f"setsar=1,fade=t=in:st=0:d={fade_s},fade=t=out:st={fade_out_start:.3f}:d={fade_s}[v]"
    )
    cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(broll_path)]
    if audio_path is not None:
        cmd += ["-stream_loop", "-1", "-i", str(audio_path)]
        audio_filter = f"afade=t=in:st=0:d={fade_s},afade=t=out:st={fade_out_start:.3f}:d={fade_s}[a]"
        filter_complex = f"[0:v]{video_filter};[1:a]{audio_filter}"
        audio_args = ["-map", "[a]"]
    else:
        # No audio track available this run -- still ship the real clip
        # with silent audio rather than skip the whole upload.
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        filter_complex = f"[0:v]{video_filter}"
        audio_args = ["-map", "1:a"]
    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        *audio_args,
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
        lg.error("ffmpeg failed to run: %s", exc)
        return False
    if result.returncode != 0:
        lg.error("ffmpeg exited %d: %s", result.returncode, result.stderr[-2000:])
        return False
    return output_path.exists() and output_path.stat().st_size > 0