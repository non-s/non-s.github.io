"""
utils/video_compose.py â€” FFmpeg pipelines for Shorts assembly.

Two pipelines:

  build_broll_short(...)   â€” multi-clip vertical Short with burned captions
                              and a hook overlay. The "best" path; used when
                              we successfully fetched b-roll motion footage.

  build_static_short(...)  â€” single static-image fallback (current behaviour).
                              Used when b-roll is unavailable and we still
                              need to ship.

Both produce a 1080x1920 / 30fps / yuv420p / faststart MP4 muxed with the
TTS MP3 we already render.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

SHORT_W, SHORT_H = 1080, 1920
TARGET_FPS = 30
# Fast Shorts are easier to finish, replay, and recommend. Keep a hard
# ceiling so TTS variance never turns a tight script into a slow one.
MAX_DURATION_S = 24.0

# How long the branded intro / outro cards appear. These are PNGs
# (not motion clips) loop-displayed for these durations. Total
# intro+outro budget is bounded so the animal fact gets the
# remaining ~56 s.
INTRO_CARD_S = 0.8
OUTRO_CARD_S = 2.0
BRAND_CARDS_ENABLED = os.environ.get("BRAND_CARDS_ENABLED", "1") not in ("0", "false", "False")

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
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio_path)],
            capture_output=True,
            text=True,
            timeout=15,
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


# â”€â”€ Multi-clip b-roll pipeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _overlay_copy(text: str, max_chars: int = 42) -> str:
    """Compact spoken hooks for a single mobile-readable overlay line."""
    cleaned = " ".join((text or "").strip().split())
    if len(cleaned) <= max_chars:
        return cleaned
    words: list[str] = []
    for word in cleaned.split():
        candidate = " ".join(words + [word])
        if len(candidate) > max_chars - 3:
            break
        words.append(word)
    return (" ".join(words).rstrip(" .,;:-") + "...") if words else cleaned[: max_chars - 3] + "..."


def build_broll_short(
    broll_paths: list[Path],
    audio_path: Path,
    output_path: Path,
    ass_subtitle_path: Path | None = None,
    hook_text: str = "",
    cover_text: str = "",
    cta_text: str = "",
    watermark_text: str = "@WildBrief",
) -> bool:
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
    - `watermark_text` is the channel handle drawn lower-right
      throughout the entire video â€” the industry-standard brand bug.

    Returns True on success.
    """
    if not broll_paths:
        log.warning("build_broll_short: no clips provided")
        return False
    if not audio_path.exists():
        log.warning("build_broll_short: audio missing")
        return False

    audio_dur = min(_audio_duration_s(audio_path), MAX_DURATION_S)

    # Branded intro + outro cards reserve a fixed slice at the head
    # and tail of the timeline. The b-roll fills the remaining
    # duration so the FULL Short still matches the audio length.
    intro_card_path: Path | None = None
    outro_card_path: Path | None = None
    if BRAND_CARDS_ENABLED:
        try:
            from utils.brand_card import get_intro_outro_cards

            intro_card_path, outro_card_path = get_intro_outro_cards()
        except Exception as exc:
            log.warning("brand cards skipped: %s", exc)
            intro_card_path = outro_card_path = None
    intro_s = INTRO_CARD_S if intro_card_path else 0.0
    outro_s = OUTRO_CARD_S if outro_card_path else 0.0
    # Floor the b-roll budget so even a 10 s Short still has body.
    body_dur = max(audio_dur - intro_s - outro_s, audio_dur * 0.6)
    intro_s = (audio_dur - body_dur - outro_s) if intro_card_path else 0.0

    n = len(broll_paths)
    seg_dur = body_dur / n

    # Pre-probe each clip for a face so the crop window can be biased
    # to keep it on-screen. Cheap: one PNG extract + one cascade pass
    # per clip. Falls back to centre-crop when no face is found OR
    # OpenCV isn't installed.
    from utils.face_crop import detect_face_center

    face_centers: list[tuple[float, float] | None] = []
    for clip in broll_paths:
        face_centers.append(detect_face_center(clip, output_path.parent))

    # Build the filter graph. Each clip becomes a normalised vertical
    # segment of `seg_dur` seconds with a subtle Ken Burns push so the
    # frame is never literally static â€” a hard requirement for the
    # Inauthentic Content policy. Direction alternates per clip
    # (in / out / in) so consecutive segments feel different.
    parts: list[str] = []
    segment_frames = int(round(seg_dur * TARGET_FPS))
    for i, clip in enumerate(broll_paths):
        zoom_in = i % 2 == 0
        # zoompan z' starts at 1 and grows (or shrinks) per frame. A 1.08
        # final zoom over seg_dur â‰ˆ 1.78 % per second â€” slow enough to
        # feel cinematic, not so fast the viewer notices the crop walking.
        #
        # Every comma inside the z-expression has to be backslash-escaped
        # (`\,`) or FFmpeg's filter_complex parser treats it as a filter
        # separator and the zoompan splits into two malformed filters â†’
        # "Filter not found" hard error. Unescaped commas were silently
        # falling back to static-frame compose for every b-roll Short.
        if zoom_in:
            z_expr = "min(zoom+0.00125\\,1.12)"
        else:
            z_expr = "if(eq(on\\,0)\\,1.12\\,max(zoom-0.00125\\,1.00))"
        # Face-aware crop: bias the crop window so the face stays
        # centred in the cropped frame. Face detection runs on the
        # ORIGINAL frame; once we scale to 2Ã— the offset scales too.
        face = face_centers[i] if i < len(face_centers) else None
        if face is not None:
            fx, fy = face
            # In the scaled space iw = source_w Ã— 2. We want the crop
            # window of width ow centred at fx Ã— iw, clamped. Every
            # comma inside the max(0,min(...)) expressions has to be
            # backslash-escaped â€” see the zoompan note above.
            crop_x = f"max(0\\,min(iw-ow\\," f"{fx:.4f}*iw-(ow/2)))"
            crop_y = f"max(0\\,min(ih-oh\\," f"{fy:.4f}*ih-(oh/2)))"
            crop_expr = f"crop={SHORT_W * 2}:{SHORT_H * 2}:{crop_x}:{crop_y}"
        else:
            crop_expr = f"crop={SHORT_W * 2}:{SHORT_H * 2}"
        parts.append(
            # Loop short clips, trim long ones to the exact segment length.
            # `setpts=PTS-STARTPTS` resets timestamps so concat splices cleanly.
            f"[{i}:v]"
            f"loop=loop=-1:size=10000:start=0,"  # cheap loop covers under-length clips
            f"scale={SHORT_W * 2}:{SHORT_H * 2}:force_original_aspect_ratio=increase,"
            f"{crop_expr},"
            # Ken Burns push â€” `d=1` outputs one frame per input frame so
            # the zoom envelope is smooth, not jittery. `s={W}x{H}` scales
            # the output back down to Shorts native after the crop walk.
            f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={SHORT_W}x{SHORT_H}:fps={TARGET_FPS},"
            f"eq=contrast=1.08:saturation=1.14:brightness=0.015,"
            f"unsharp=5:5:0.55:3:3:0.25,"
            f"fade=t=in:st=0:d=0.08,fade=t=out:st={max(seg_dur - 0.08, 0):.3f}:d=0.08,"
            f"setsar=1,"
            f"trim=duration={seg_dur:.3f},setpts=PTS-STARTPTS"
            f"[v{i}]"
        )
    # Brand-card streams. We add them as extra FFmpeg inputs and
    # PREPEND/APPEND to the concat chain so the body is bracketed
    # by the same visual on every Short.
    extra_inputs: list[Path] = []
    intro_node = outro_node = None
    if intro_card_path:
        idx = n + len(extra_inputs)  # next ffmpeg input slot
        extra_inputs.append(intro_card_path)
        parts.append(
            f"[{idx}:v]"
            f"scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
            f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,fps={TARGET_FPS},"
            f"trim=duration={intro_s:.3f},setpts=PTS-STARTPTS"
            f"[vintro]"
        )
        intro_node = "vintro"
    if outro_card_path:
        idx = n + len(extra_inputs)
        extra_inputs.append(outro_card_path)
        parts.append(
            f"[{idx}:v]"
            f"scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
            f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,fps={TARGET_FPS},"
            f"trim=duration={outro_s:.3f},setpts=PTS-STARTPTS"
            f"[voutro]"
        )
        outro_node = "voutro"

    # Build the concat chain: optional intro card + body clips + optional outro.
    concat_inputs_parts: list[str] = []
    if intro_node:
        concat_inputs_parts.append(f"[{intro_node}]")
    concat_inputs_parts.extend(f"[v{i}]" for i in range(n))
    if outro_node:
        concat_inputs_parts.append(f"[{outro_node}]")
    total_segs = len(concat_inputs_parts)
    parts.append(f"{''.join(concat_inputs_parts)}concat=n={total_segs}:v=1:a=0[concat]")

    last_label = "concat"

    # Burn the hook text on the top half for the first 3 seconds.
    font = _font_path()
    if hook_text and font:
        safe = _ffmpeg_escape(_overlay_copy(hook_text))
        parts.append(
            f"[{last_label}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white:fontsize=72"
            f":borderw=5:bordercolor=black@0.92"
            f":box=1:boxcolor=black@0.30:boxborderw=18"
            f":x=(w-text_w)/2:y=150"
            # Visible 0-3s with a quick fade-out 2.7-3s.
            f":enable='between(t,0,3)'"
            f"[withhook]"
        )
        last_label = "withhook"

    # Shorts do not accept an API-uploaded custom thumbnail. Put the
    # strongest 2-4 word cover inside the opening second of the MP4.
    if cover_text and font:
        safe = _ffmpeg_escape(_overlay_copy(cover_text.upper(), max_chars=28))
        parts.append(
            f"[{last_label}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white:fontsize=122"
            f":borderw=8:bordercolor=black@0.94"
            f":x=64:y=h*0.43:enable='between(t,0,1.2)'"
            f"[withcover]"
        )
        last_label = "withcover"

    # Bottom CTA for the last 6 seconds.
    if cta_text and font:
        safe = _ffmpeg_escape(cta_text[:50])
        cta_start = max(0.0, audio_dur - 6.0)
        parts.append(
            f"[{last_label}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=0xFFF200:fontsize=54"
            f":box=1:boxcolor=black@0.65:boxborderw=18"
            f":x=(w-text_w)/2:y=h-260"
            f":enable='between(t,{cta_start:.2f},{audio_dur:.2f})'"
            f"[withcta]"
        )
        last_label = "withcta"

    # Brand-bug watermark â€” drawn ALL THE TIME at the upper-right,
    # offset to clear YouTube's interaction rail at the right side.
    # Standard practice on short-form video; lets reposters get traced.
    if watermark_text and font:
        safe = _ffmpeg_escape(watermark_text[:32])
        parts.append(
            f"[{last_label}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white@0.75:fontsize=36"
            f":box=1:boxcolor=black@0.30:boxborderw=10"
            f":x=w-text_w-40:y=140"
            f"[withbug]"
        )
        last_label = "withbug"

    # Burned ASS subtitles (word-level captions in the middle band).
    if ass_subtitle_path and ass_subtitle_path.exists():
        # Use the ASS filter so V4+ styles are honoured. Path is escaped
        # via single-quotes; FFmpeg requires backslashes inside.
        ass_path = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
        parts.append(f"[{last_label}]ass={ass_path}[final]")
        last_label = "final"

    # --- AUDIO MIXING (TTS + BGM + SFX) ---
    import random
    bgm_candidates = list(Path("_assets/audio/bgm").glob("*.*"))
    sfx_candidates = list(Path("_assets/audio/sfx").glob("*.*"))
    bgm_path = random.choice([p for p in bgm_candidates if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac")]) if bgm_candidates else None
    sfx_path = random.choice([p for p in sfx_candidates if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac")]) if sfx_candidates else None
    
    cmd = ["ffmpeg", "-y"]
    for clip in broll_paths:
        cmd += ["-i", str(clip)]
    
    for card in extra_inputs:
        cmd += ["-loop", "1", "-t", f"{max(intro_s, outro_s):.3f}", "-i", str(card)]
        
    cmd += ["-i", str(audio_path)]
    audio_idx = n + len(extra_inputs)
    
    audio_inputs_count = 1
    amix_labels = f"[{audio_idx}:a]"
    
    if bgm_path:
        cmd += ["-stream_loop", "-1", "-i", str(bgm_path)]
        bgm_idx = audio_idx + audio_inputs_count
        parts.append(f"[{bgm_idx}:a]volume=0.10[abgm]")
        amix_labels += "[abgm]"
        audio_inputs_count += 1
        
    if sfx_path:
        cmd += ["-i", str(sfx_path)]
        sfx_idx = audio_idx + audio_inputs_count
        parts.append(f"[{sfx_idx}:a]volume=0.90[asfx]")
        amix_labels += "[asfx]"
        audio_inputs_count += 1
        
    if audio_inputs_count > 1:
        parts.append(f"{amix_labels}amix=inputs={audio_inputs_count}:duration=first:dropout_transition=2[aout]")
        final_audio_map = "[aout]"
    else:
        final_audio_map = f"{audio_idx}:a"
    # --------------------------------------

    filtergraph = ";".join(parts)

    cmd += [
        "-filter_complex",
        filtergraph,
        "-map",
        f"[{last_label}]",
        "-map",
        final_audio_map,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(TARGET_FPS),
        "-t",
        f"{audio_dur:.2f}",
        "-movflags",
        "+faststart",
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
    log.info("  ðŸŽ¬ B-roll Short ready (%s clips, %.1fs): %s", n, audio_dur, output_path.name)
    return True


# â”€â”€ Static-image fallback pipeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def build_static_short(
    frame_path: Path,
    audio_path: Path,
    output_path: Path,
    ass_subtitle_path: Path | None = None,
    hook_text: str = "",
    cover_text: str = "",
    cta_text: str = "",
    watermark_text: str = "@WildBrief",
) -> bool:
    """Single still image + audio, with optional burned captions.

    Used when no b-roll was acquired. We still burn
    captions (huge retention lever) and overlay the hook text â€” even
    a static Short benefits.
    """
    if not frame_path.exists() or not audio_path.exists():
        return False
    audio_dur = min(_audio_duration_s(audio_path), MAX_DURATION_S)
    font = _font_path()
    parts: list[str] = []
    last = "0:v"
    # Slow Ken Burns zoom-in (1.00 â†’ 1.04 over the full audio
    # duration). Without this the static-frame fallback shipped as
    # a JPEG-with-audio Short â€” viewers swipe within 2 s because
    # NOTHING moves. 4 % zoom is enough to register as motion without
    # cropping out the title or the 3 numbered points the title card
    # carries. The b-roll path applies the same trick per segment
    # (utils/video_compose.py:build_broll_short); this just mirrors
    # it for the fallback so every Short has motion.
    zoom_frames = max(int(audio_dur * TARGET_FPS), 1)
    zoom_step = 0.07 / zoom_frames  # total magnification over the clip
    # Commas inside the zoompan z-expression have to be backslash-
    # escaped so FFmpeg doesn't parse them as filter separators.
    parts.append(
        f"[{last}]scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
        f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
        f"zoompan=z='min(zoom+{zoom_step:.6f}\\,1.07)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={SHORT_W}x{SHORT_H}:fps={TARGET_FPS},"
        f"eq=contrast=1.06:saturation=1.12:brightness=0.012,"
        f"unsharp=5:5:0.45:3:3:0.20[scaled]"
    )
    last = "scaled"
    if hook_text and font:
        safe = _ffmpeg_escape(_overlay_copy(hook_text))
        parts.append(
            f"[{last}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white:fontsize=72"
            f":borderw=5:bordercolor=black@0.92"
            f":box=1:boxcolor=black@0.30:boxborderw=18"
            f":x=(w-text_w)/2:y=150:enable='between(t,0,3)'[withhook]"
        )
        last = "withhook"
    if cover_text and font:
        safe = _ffmpeg_escape(_overlay_copy(cover_text.upper(), max_chars=28))
        parts.append(
            f"[{last}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white:fontsize=122"
            f":borderw=8:bordercolor=black@0.94"
            f":x=64:y=h*0.43:enable='between(t,0,1.2)'[withcover]"
        )
        last = "withcover"
    if cta_text and font:
        safe = _ffmpeg_escape(cta_text[:50])
        cta_start = max(0.0, audio_dur - 6.0)
        parts.append(
            f"[{last}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=0xFFF200:fontsize=54"
            f":box=1:boxcolor=black@0.65:boxborderw=18"
            f":x=(w-text_w)/2:y=h-260"
            f":enable='between(t,{cta_start:.2f},{audio_dur:.2f})'[withcta]"
        )
        last = "withcta"
    if watermark_text and font:
        safe = _ffmpeg_escape(watermark_text[:32])
        parts.append(
            f"[{last}]drawtext=fontfile={font}"
            f":text='{safe}':fontcolor=white@0.75:fontsize=36"
            f":box=1:boxcolor=black@0.30:boxborderw=10"
            f":x=w-text_w-40:y=140[withbug]"
        )
        last = "withbug"
    if ass_subtitle_path and ass_subtitle_path.exists():
        ass_path = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
        parts.append(f"[{last}]ass={ass_path}[final]")
        last = "final"

    filtergraph = ";".join(parts)
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(frame_path),
        "-i",
        str(audio_path),
        "-filter_complex",
        filtergraph,
        "-map",
        f"[{last}]",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(TARGET_FPS),
        "-t",
        f"{audio_dur:.2f}",
        "-movflags",
        "+faststart",
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
    log.info("  ðŸŽž  Static-frame Short ready (%.1fs): %s", audio_dur, output_path.name)
    return True
