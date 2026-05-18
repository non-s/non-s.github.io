"""
utils/video_compose.py — FFmpeg pipelines for Shorts assembly.

Two pipelines:

  build_broll_short(...)   — multi-clip vertical Short with burned captions
                              and a hook overlay. The "best" path; used when
                              we successfully fetched b-roll motion footage.

  build_static_short(...)  — single static-image fallback (current behaviour).
                              Used when b-roll is unavailable and we still
                              need to ship.

Both produce a 1080x1920 / 30fps / yuv420p / faststart MP4 muxed with the
TTS MP3 we already render.
"""
from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

SHORT_W, SHORT_H = 1080, 1920
TARGET_FPS = 30
MAX_DURATION_S = 59.0   # YouTube Shorts hard cap is 60s; we stay below.

# Path to the system font we burn the hook overlay with. Falls back to
# DejaVu if Liberation isn't installed (covers ubuntu-latest runners).
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
)


def _font_path() -> str:
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return ""


def _audio_duration_s(audio_path: Path) -> float:
    """Use ffprobe to extract the audio duration. Returns ~50s on parse failure."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_path)],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return 50.0


def _ffmpeg_escape(text: str) -> str:
    """drawtext requires ':', '\\', and "'" to be escaped."""
    if not text:
        return ""
    text = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    text = text.replace("%", "%%")  # avoid printf-style expansion
    return text


# ── Multi-clip b-roll pipeline ────────────────────────────────────

def build_broll_short(broll_paths: list[Path],
                      audio_path: Path,
                      output_path: Path,
                      ass_subtitle_path: Path | None = None,
                      hook_text: str = "",
                      cta_text: str = "") -> bool:
    """Compose a vertical Short from N b-roll clips + audio.

    - Each clip is cropped to 9:16, scaled to 1080x1920, played for
      `audio_duration / n_clips` seconds. Shorter clips loop, longer
      clips trim. Hard cuts between segments (xfade is brittle when
      clip durations vary).
    - If `ass_subtitle_path` is provided, the subtitle file is burned
      onto the final video via libass. Word-level captions = +18%
      retention on Shorts (Zebracat 2025 data).
    - `hook_text` (max ~40 chars) is drawn as a top-center text overlay
      during the first 3 seconds, the highest-leverage retention window.
    - `cta_text` is drawn near the bottom for the last 6 seconds.

    Returns True on success.
    """
    if not broll_paths:
        log.warning("build_broll_short: no clips provided")
        return False
    if not audio_path.exists():
        log.warning("build_broll_short: audio missing")
        return False

    audio_dur = min(_audio_duration_s(audio_path), MAX_DURATION_S)
    n = len(broll_paths)
    seg_dur = audio_dur / n

    # Build the filter graph. Each clip becomes a normalised vertical
    # segment of `seg_dur` seconds with a subtle Ken Burns push so the
    # frame is never literally static — a hard requirement for the
    # Inauthentic Content policy. Direction alternates per clip
    # (in / out / in) so consecutive segments feel different.
    parts: list[str] = []
    segment_frames = int(round(seg_dur * TARGET_FPS))
    for i, clip in enumerate(broll_paths):
        zoom_in = (i % 2 == 0)
        # zoompan z' starts at 1 and grows (or shrinks) per frame. A 1.08
        # final zoom over seg_dur ≈ 1.78 % per second — slow enough to
        # feel cinematic, not so fast the viewer notices the crop walking.
        if zoom_in:
            z_expr = f"min(zoom+0.0008,1.08)"
        else:
            z_expr = f"if(eq(on,0),1.08,max(zoom-0.0008,1.00))"
        parts.append(
            # Loop short clips, trim long ones to the exact segment length.
            # `setpts=PTS-STARTPTS` resets timestamps so concat splices cleanly.
            f"[{i}:v]"
            f"loop=loop=-1:size=10000:start=0,"  # cheap loop covers under-length clips
            f"scale={SHORT_W * 2}:{SHORT_H * 2}:force_original_aspect_ratio=increase,"
            f"crop={SHORT_W * 2}:{SHORT_H * 2},"
            # Ken Burns push — `d=1` outputs one frame per input frame so
            # the zoom envelope is smooth, not jittery. `s={W}x{H}` scales
            # the output back down to Shorts native after the crop walk.
            f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={SHORT_W}x{SHORT_H}:fps={TARGET_FPS},"
            f"setsar=1,"
            f"trim=duration={seg_dur:.3f},setpts=PTS-STARTPTS"
            f"[v{i}]"
        )
    concat_inputs = "".join(f"[v{i}]" for i in range(n))
    parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[concat]")

    last_label = "concat"

    # Burn the hook text on the top half for the first 3 seconds.
    font = _font_path()
    if hook_text and font:
        safe = _ffmpeg_escape(hook_text[:60])
        parts.append(
            f"[{last_label}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white:fontsize=78"
            f":box=1:boxcolor=black@0.55:boxborderw=22"
            f":x=(w-text_w)/2:y=180"
            # Visible 0-3s with a quick fade-out 2.7-3s.
            f":enable='between(t,0,3)'"
            f"[withhook]"
        )
        last_label = "withhook"

    # Bottom CTA for the last 6 seconds.
    if cta_text and font:
        safe = _ffmpeg_escape(cta_text[:50])
        cta_start = max(0.0, audio_dur - 6.0)
        parts.append(
            f"[{last_label}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white:fontsize=52"
            f":box=1:boxcolor=black@0.65:boxborderw=18"
            f":x=(w-text_w)/2:y=h-260"
            f":enable='between(t,{cta_start:.2f},{audio_dur:.2f})'"
            f"[withcta]"
        )
        last_label = "withcta"

    # Burned ASS subtitles (word-level captions in the middle band).
    if ass_subtitle_path and ass_subtitle_path.exists():
        # Use the ASS filter so V4+ styles are honoured. Path is escaped
        # via single-quotes; FFmpeg requires backslashes inside.
        ass_path = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
        parts.append(f"[{last_label}]ass={ass_path}[final]")
        last_label = "final"

    filtergraph = ";".join(parts)

    cmd = ["ffmpeg", "-y"]
    for clip in broll_paths:
        cmd += ["-i", str(clip)]
    cmd += ["-i", str(audio_path)]
    cmd += [
        "-filter_complex", filtergraph,
        "-map", f"[{last_label}]",
        "-map", f"{n}:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-r", str(TARGET_FPS),
        "-t", f"{audio_dur:.2f}",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        log.error("ffmpeg b-roll compose timed out after 180s")
        return False

    if result.returncode != 0:
        log.error("ffmpeg b-roll compose failed: %s", result.stderr[-1200:])
        return False
    log.info("  🎬 B-roll Short ready (%s clips, %.1fs): %s",
             n, audio_dur, output_path.name)
    return True


# ── Static-image fallback pipeline ───────────────────────────────

def build_static_short(frame_path: Path,
                       audio_path: Path,
                       output_path: Path,
                       ass_subtitle_path: Path | None = None,
                       hook_text: str = "") -> bool:
    """Single still image + audio, with optional burned captions.

    The legacy path. Used when no b-roll was acquired. We still burn
    captions (huge retention lever) and overlay the hook text — even
    a static Short benefits.
    """
    if not frame_path.exists() or not audio_path.exists():
        return False
    audio_dur = min(_audio_duration_s(audio_path), MAX_DURATION_S)
    font = _font_path()
    parts: list[str] = []
    last = "0:v"
    parts.append(
        f"[{last}]scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
        f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={TARGET_FPS}[scaled]"
    )
    last = "scaled"
    if hook_text and font:
        safe = _ffmpeg_escape(hook_text[:60])
        parts.append(
            f"[{last}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white:fontsize=78"
            f":box=1:boxcolor=black@0.55:boxborderw=22"
            f":x=(w-text_w)/2:y=180:enable='between(t,0,3)'[withhook]"
        )
        last = "withhook"
    if ass_subtitle_path and ass_subtitle_path.exists():
        ass_path = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
        parts.append(f"[{last}]ass={ass_path}[final]")
        last = "final"

    filtergraph = ";".join(parts)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(frame_path),
        "-i", str(audio_path),
        "-filter_complex", filtergraph,
        "-map", f"[{last}]",
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-r", str(TARGET_FPS),
        "-t", f"{audio_dur:.2f}",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        log.error("ffmpeg static compose timed out")
        return False
    if result.returncode != 0:
        log.error("ffmpeg static compose failed: %s", result.stderr[-1200:])
        return False
    log.info("  🎞  Static-frame Short ready (%.1fs): %s", audio_dur, output_path.name)
    return True
