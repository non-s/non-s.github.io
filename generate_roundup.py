#!/usr/bin/env python3
"""
generate_roundup.py — Weekly long-form roundup video for the algorithmic foundation.

Why this exists
---------------
The May 2026 pivot dropped long-form for Shorts-only, but the case-study
research is clear: Shorts-only channels plateau at ~50-100k subs because
YouTube's ranking layer weighs total watch time (long-form wins) not
just average view percentage (Shorts wins). Channels that grow past
that ceiling all have at least one long-form video / week.

This script builds a single 8-12 minute "Top 7 Stories of the Week"
video using the same primitives the Shorts pipeline does:

  * Pulls the top-scoring Shorts of the last 7 days from the queue
  * Builds a unified script with chapter intros + transitions
  * Renders with b-roll + captions + dynamic title cards
  * Outputs a YouTube-ready MP4 + metadata + thumbnail

Runs once a week — `weekly-roundup.yml` cron. Outputs to `_videos/`
alongside the daily Shorts and is picked up by `upload_youtube.py`
in the same step.

Format
------
  Intro              ~15s   Brand opening + "this week" framing
  Story 1 chapter    ~80s   Title card, b-roll, narration, takeaway
  Story 2-7          80s ea Same structure, varied voices
  Outro              ~30s   "Subscribe + see you next week"

Total target: 9-11 minutes (sweet spot for News & Politics — see
TLDR News data: ~9min videos retain best in the niche).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.broll import download_clip, fetch_broll_clips
from utils.captions import (
    group_words_into_phrases,
    transcribe as captions_transcribe,
    write_ass,
)
from utils.text import humanize_for_tts

# Reuse the rich TTS rate map + voice picker from generate_shorts so a
# long-form video has the same voice palette as the daily Shorts.
from generate_shorts import (
    VOICE_PANEL,
    VOICE_RATE_OFFSETS,
    pick_voice,
    text_to_speech,
)

ROUNDUP_DIR = Path("_videos")
LOG_FILE    = "generate_roundup.log"
SHORT_W, SHORT_H = 1080, 1920  # we still produce vertical so the
                               # roundup also lands on the Shorts shelf
                               # (10 min vertical = "long-form-vertical")

# Number of stories to feature per weekly roundup.
ROUNDUP_STORIES = int(os.environ.get("ROUNDUP_STORIES", "7"))
# Minimum story score to qualify for the roundup.
ROUNDUP_MIN_SCORE = int(os.environ.get("ROUNDUP_MIN_SCORE", "7"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

QUEUE_FILE = Path("_data/stories_queue.json")


# ── Story selection ───────────────────────────────────────────────

def select_roundup_stories(n: int = ROUNDUP_STORIES,
                            lookback_days: int = 7) -> list[dict]:
    """Pull the top N stories of the last `lookback_days` by AI score.

    We pick stories that have already been published as Shorts (so we
    know they cleared the quality gate) AND score >= ROUNDUP_MIN_SCORE.
    Sorted by score then by recency.
    """
    if not QUEUE_FILE.exists():
        log.error("queue file missing: %s", QUEUE_FILE)
        return []
    try:
        queue = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.error("queue parse failed: %s", exc)
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    candidates: list[dict] = []
    for s in queue.get("stories", []):
        try:
            fetched = datetime.fromisoformat(
                (s.get("fetched_at") or "").replace("Z", "+00:00")
            )
        except Exception:
            continue
        if fetched < cutoff:
            continue
        # Score gate — only the best stories of the week land here.
        if int(s.get("score", 0) or 0) < ROUNDUP_MIN_SCORE:
            continue
        # We want stories that already shipped as Shorts; an unshipped
        # high-score story would mean the b-roll / TTS failed and we
        # don't want to re-attempt it inside a 10-min compile.
        if not s.get("consumed"):
            continue
        # Prefer stories from native English feeds; PT-BR feeds get
        # their own weekly roundup workflow.
        if (s.get("native_lang") or "en") != "en":
            continue
        candidates.append(s)
    candidates.sort(
        key=lambda s: (int(s.get("score", 0) or 0), s.get("consumed_at", "")),
        reverse=True,
    )
    return candidates[:n]


# ── Script construction ───────────────────────────────────────────

def build_roundup_script(stories: list[dict]) -> str:
    """Build the unified voice-over script for the roundup.

    The structure is intentionally chapter-driven so YouTube auto-
    detects chapters from the description (we mirror the same
    timestamps there). Chapter-aware long-form retains markedly
    better than monolithic 10-min blocks (TubeBuddy 2025).
    """
    if not stories:
        return ""

    week_label = datetime.now(timezone.utc).strftime("%B %d, %Y")
    lines: list[str] = []
    lines.append(
        f"Welcome back to GlobalBR News. Here are the seven biggest "
        f"stories the world should be paying attention to this week, "
        f"week ending {week_label}. Stick around — number one might "
        f"not be what you expect."
    )
    for i, s in enumerate(stories, 1):
        title = (s.get("seo_title") or s.get("title", "")).strip()
        hook  = (s.get("hook") or "").strip()
        # Prefer the AI-authored script; if that's missing for any
        # reason fall back to a shorter form built from the lead.
        body  = (s.get("script") or s.get("lead") or
                  s.get("description", "")).strip()
        source = s.get("source", "")
        chapter_intro = f"Number {i}. {title}."
        if hook and hook.lower() not in chapter_intro.lower():
            chapter_intro += f" {hook}"
        # Trim the per-story body so the whole roundup lands at 9-11min.
        # ~80s per story × 7 stories = 9.3 min + intro/outro. At TTS pace
        # that's ~200 words per story.
        if body:
            body_words = body.split()
            if len(body_words) > 220:
                body = " ".join(body_words[:220]).rstrip() + "..."
        # Source citation: every chapter ends naming the outlet that
        # broke the story. Crucial for the "transformative use"
        # documentation YouTube's Inauthentic Content reviews want.
        outro = f"That story broke first on {source}." if source else ""
        chapter = " ".join(p for p in (chapter_intro, body, outro) if p)
        lines.append(chapter)
    lines.append(
        "That's your week. If this format works for you, drop a "
        "comment — and subscribe so you never miss what matters. "
        "GlobalBR News, every day on Shorts, every Sunday in long-form."
    )
    return "\n\n".join(lines)


# ── Video assembly ────────────────────────────────────────────────
#
# The roundup uses the SAME b-roll + caption + zoompan primitives as
# the Shorts pipeline, but with multiple b-roll concatenations and a
# longer audio track. We splice 2 b-roll clips per chapter so the
# 10-min video has visual cuts roughly every 40 s.

def acquire_chapter_broll(stories: list[dict], tmp_dir: Path,
                           clips_per_chapter: int = 2) -> list[list[Path]]:
    """For each story, fetch `clips_per_chapter` MP4s. Returns a list
    of lists, parallel to `stories`. Empty inner list means the
    chapter will run on the still-frame fallback path."""
    out: list[list[Path]] = []
    for i, s in enumerate(stories):
        query = (s.get("seo_title") or s.get("title", "")) + " " + s.get("topic_hashtag", "")
        category = s.get("category", "")
        try:
            candidates = fetch_broll_clips(query[:160], want_n=clips_per_chapter * 2,
                                            category=category)
        except Exception as exc:
            log.debug("broll fetch failed for chapter %d: %s", i + 1, exc)
            candidates = []
        chapter_paths: list[Path] = []
        for j, clip in enumerate(candidates):
            if len(chapter_paths) >= clips_per_chapter:
                break
            dest = tmp_dir / f"broll_{i+1}_{j}.mp4"
            if download_clip(clip, dest):
                chapter_paths.append(dest)
        out.append(chapter_paths)
        log.info("  chapter %d: %d b-roll(s)", i + 1, len(chapter_paths))
    return out


def render_intro_card(text: str, dest: Path,
                       w: int = SHORT_W, h: int = SHORT_H) -> Path:
    """Render a high-contrast 5s title card PNG that FFmpeg can loop
    into a clip. Used as the per-chapter visual when no b-roll exists."""
    from PIL import Image, ImageDraw
    from utils.video_common import get_font, draw_rounded_rect
    img = Image.new("RGB", (w, h), (8, 8, 18))
    draw = ImageDraw.Draw(img)
    font_size = 110
    font = get_font(font_size, bold=True)
    # Naive word-wrap.
    words = text.split()
    line, lines = [], []
    for word in words:
        test = " ".join(line + [word])
        if draw.textbbox((0, 0), test, font=font)[2] > w - 120 and line:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    while len(lines) > 6 and font_size > 70:
        font_size -= 10
        font = get_font(font_size, bold=True)
    total_h = len(lines) * (font_size + 18)
    y = (h - total_h) // 2
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        tw = bbox[2] - bbox[0]
        cx = (w - tw) // 2
        draw_rounded_rect(draw,
                           (cx - 30, y - 16, cx + tw + 30, y + font_size + 10),
                           radius=20, fill=(0, 0, 10))
        draw.text((cx, y), ln, font=font, fill=(245, 245, 255))
        y += font_size + 18
    img.save(str(dest), "PNG")
    return dest


def compose_roundup(stories: list[dict], chapter_broll: list[list[Path]],
                     audio_path: Path, ass_subtitle: Path | None,
                     output: Path, tmp_dir: Path) -> bool:
    """FFmpeg pipeline: concat per-chapter clips → mux with audio → burn captions.

    The audio drives the duration; the visual track is built to match.
    Each chapter gets ~audio_duration / n_chapters seconds of motion.
    """
    if not stories or not audio_path.exists():
        return False

    # ffprobe the audio.
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_path)],
            capture_output=True, text=True, timeout=15,
        )
        total_duration = float(result.stdout.strip())
    except Exception:
        total_duration = 600.0  # 10-min fallback
    n_chapters = len(stories)
    # Reserve 15s for intro + 30s for outro; rest split across chapters.
    intro_dur, outro_dur = 15.0, 30.0
    chapter_total = max(60.0, total_duration - intro_dur - outro_dur)
    per_chapter = chapter_total / n_chapters

    # Build per-chapter visual sources.
    visual_inputs: list[Path] = []
    intro_card_path = tmp_dir / "intro_card.png"
    render_intro_card("Top 7 stories of the week", intro_card_path)
    visual_inputs.append(intro_card_path)
    for i, s in enumerate(stories):
        clips = chapter_broll[i] if i < len(chapter_broll) else []
        if clips:
            visual_inputs.extend(clips)
        else:
            card = tmp_dir / f"chapter_{i+1}_card.png"
            render_intro_card(
                f"#{i+1}. {(s.get('seo_title') or s.get('title',''))[:60]}",
                card,
            )
            visual_inputs.append(card)
    outro_card_path = tmp_dir / "outro_card.png"
    render_intro_card("Subscribe — see you next week", outro_card_path)
    visual_inputs.append(outro_card_path)

    # FFmpeg input list.
    ffmpeg_inputs: list[str] = []
    filter_parts: list[str] = []
    # Compute per-segment duration assignment.
    seg_durations: list[float] = [intro_dur]
    n_chapter_visuals_per_chapter = max(1, len(chapter_broll[0])) if chapter_broll else 1
    for i in range(n_chapters):
        clips = chapter_broll[i] if i < len(chapter_broll) else []
        if clips:
            # Split per_chapter across however many clips we have.
            each = per_chapter / len(clips)
            seg_durations.extend([each] * len(clips))
        else:
            seg_durations.append(per_chapter)
    seg_durations.append(outro_dur)

    assert len(seg_durations) == len(visual_inputs), \
        f"duration count {len(seg_durations)} vs visual count {len(visual_inputs)}"

    for i, src in enumerate(visual_inputs):
        is_image = src.suffix.lower() in (".png", ".jpg", ".jpeg")
        if is_image:
            ffmpeg_inputs += ["-loop", "1", "-t", f"{seg_durations[i]:.2f}", "-i", str(src)]
        else:
            ffmpeg_inputs += ["-stream_loop", "-1", "-i", str(src)]
        filter_parts.append(
            f"[{i}:v]"
            f"scale={SHORT_W * 2}:{SHORT_H * 2}:force_original_aspect_ratio=increase,"
            f"crop={SHORT_W * 2}:{SHORT_H * 2},"
            f"zoompan=z='min(zoom+0.0006,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={SHORT_W}x{SHORT_H}:fps=30,"
            f"setsar=1,trim=duration={seg_durations[i]:.2f},setpts=PTS-STARTPTS"
            f"[v{i}]"
        )
    concat = "".join(f"[v{i}]" for i in range(len(visual_inputs)))
    filter_parts.append(
        f"{concat}concat=n={len(visual_inputs)}:v=1:a=0[concat]"
    )
    last = "concat"
    if ass_subtitle and ass_subtitle.exists():
        ass_path = str(ass_subtitle).replace("\\", "/").replace(":", "\\:")
        filter_parts.append(f"[{last}]ass={ass_path}[final]")
        last = "final"
    filter_complex = ";".join(filter_parts)

    audio_idx = len(visual_inputs)
    cmd = ["ffmpeg", "-y"] + ffmpeg_inputs + [
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", f"[{last}]", "-map", f"{audio_idx}:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "160k",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-t", f"{total_duration:.2f}",
        "-movflags", "+faststart",
        "-shortest",
        str(output),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        log.error("ffmpeg roundup timed out at 600s")
        return False
    if r.returncode != 0:
        log.error("ffmpeg roundup failed: %s", r.stderr[-1200:])
        return False
    log.info("🎬 Roundup ready: %s (%.1f s)", output.name, total_duration)
    return True


# ── Metadata for the uploader ────────────────────────────────────

def build_roundup_metadata(stories: list[dict],
                            video_path: Path,
                            thumb_path: Path) -> dict:
    """Produce the metadata sidecar upload_youtube.py picks up."""
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")
    title = f"Top {len(stories)} stories of the week — {today} | GlobalBR News"
    # YouTube auto-detects chapters from `00:00 Title` lines in the
    # description IFF they're monotonically increasing and the first
    # one is 00:00. We mirror the seg_durations of the compose step.
    desc_lines = [f"This week's top {len(stories)} stories, in 10 minutes.\n"]
    timestamp = 15  # after the intro
    desc_lines.append("00:00 Intro")
    for s in stories:
        mm = timestamp // 60
        ss = timestamp % 60
        desc_lines.append(f"{mm:02d}:{ss:02d} {s.get('seo_title') or s.get('title','')}"[:120])
        timestamp += 80  # rough per-chapter duration in seconds
    desc_lines.append(f"\nSources: {', '.join(sorted({s.get('source','') for s in stories if s.get('source')}))}")
    desc_lines.append("\n#WeeklyRoundup #WorldNews #News2026")
    description = "\n".join(desc_lines)[:4900]

    tags = ["weekly roundup", "world news", "news 2026", "globalbr news",
             "news roundup", "top stories", "this week", "news recap"]
    return {
        "title":       title[:100],
        "description": description,
        "tags":        tags,
        "category_id": "25",   # News & Politics
        "privacy":     "public",
        "thumbnail":   str(thumb_path),
        "video":       str(video_path),
        "story_slug":  f"roundup-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "category":    "roundup",
        "is_short":    False,
        "altered_content": True,
        "source":      "GlobalBR News",
        "geo_hashtag": "Global",
        "experiments": {},  # roundup doesn't participate in Shorts experiments
    }


# ── Main ──────────────────────────────────────────────────────────

def main() -> None:
    from utils.panic import abort_if_halted
    abort_if_halted("generate_roundup")

    log.info("=" * 60)
    log.info("🎬 Weekly roundup — %s", datetime.now(timezone.utc).isoformat())
    log.info("=" * 60)
    ROUNDUP_DIR.mkdir(exist_ok=True)
    stories = select_roundup_stories()
    log.info("Selected %d stories for the roundup", len(stories))
    if len(stories) < 3:
        log.warning("Too few qualifying stories (%d) — skipping this week's "
                     "roundup so we don't ship a half-empty video.", len(stories))
        return

    tmp = Path(f"/tmp/roundup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    tmp.mkdir(exist_ok=True)
    try:
        script = build_roundup_script(stories)
        script_humanised = humanize_for_tts(script)
        log.info("Script: %d words", len(script_humanised.split()))

        audio = tmp / "audio.mp3"
        voice = pick_voice(seed_text="weekly-roundup", category="WORLD")
        try:
            asyncio.run(text_to_speech(script_humanised, audio, voice))
        except Exception as exc:
            log.error("TTS failed: %s", exc)
            return
        log.info("TTS audio: %s (voice=%s)", audio.name, voice)

        # Captions for the full roundup audio — same Whisper pipeline.
        ass = tmp / "captions.ass"
        try:
            words = captions_transcribe(audio)
            if words:
                phrases = group_words_into_phrases(words, max_words=4, max_gap_s=0.6)
                if not write_ass(phrases, ass):
                    ass = None
            else:
                ass = None
        except Exception as exc:
            log.warning("captions skipped: %s", exc)
            ass = None

        chapter_broll = acquire_chapter_broll(stories, tmp, clips_per_chapter=2)

        out_video = ROUNDUP_DIR / f"roundup-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.mp4"
        out_thumb = out_video.with_suffix(".jpg")

        # Thumbnail: simple high-contrast brand card. We don't have a
        # single per-story image so the static brand block reads best.
        try:
            thumb_src = render_intro_card("Top 7 of the week", tmp / "thumb.png",
                                            w=1920, h=1080)
            from PIL import Image
            Image.open(thumb_src).convert("RGB").save(str(out_thumb),
                                                       "JPEG", quality=88)
        except Exception as exc:
            log.warning("thumbnail render failed: %s", exc)

        if not compose_roundup(stories, chapter_broll, audio,
                                ass if ass and ass.exists() else None,
                                out_video, tmp):
            log.error("FFmpeg compose failed — aborting roundup")
            return

        meta = build_roundup_metadata(stories, out_video, out_thumb)
        meta_path = out_video.with_suffix(".json")
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                              encoding="utf-8")
        log.info("✅ Roundup metadata: %s", meta_path.name)
        log.info("✅ Roundup video:    %s", out_video.name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
