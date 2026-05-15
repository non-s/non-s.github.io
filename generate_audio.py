#!/usr/bin/env python3
"""
generate_audio.py — Voice-over MP3 for each new post (edge-tts, no API key).

For every post in `_posts/` that does NOT yet have an `audio:` field in
its frontmatter, we:

  1. Build a short script (TL;DR + lead + first 2 paragraphs of body),
  2. Synthesise it with edge-tts (free, online),
  3. Save to `assets/audio/posts/<slug>.mp3`,
  4. Write `audio: "/assets/audio/posts/<slug>.mp3"` back into the
     post's frontmatter so the post-template renders a player.

Designed to be safe to re-run: it skips files that already have audio
and tolerates network failures silently. Total work per run is capped
to AUDIO_MAX_PER_RUN to keep CI runs short.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from utils.frontmatter import parse, get_str, get_list

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

POSTS_DIR    = Path(__file__).parent / "_posts"
AUDIO_DIR    = Path(__file__).parent / "assets" / "audio" / "posts"
MAX_PER_RUN  = int(os.environ.get("AUDIO_MAX_PER_RUN", "8"))
LOOKBACK_D   = int(os.environ.get("AUDIO_LOOKBACK_DAYS", "3"))
DEFAULT_VOICE = os.environ.get("AUDIO_VOICE", "en-US-AriaNeural")
CATEGORY_VOICES = {
    "ai":        "en-US-GuyNeural",
    "security":  "en-US-DavisNeural",
    "war":       "en-US-DavisNeural",
    "business":  "en-US-JennyNeural",
    "world":     "en-US-AriaNeural",
    "politics":  "en-US-AriaNeural",
}


def _voice_for(fm: dict) -> str:
    for cat in get_list(fm, "categories"):
        if cat.lower() in CATEGORY_VOICES:
            return CATEGORY_VOICES[cat.lower()]
    return DEFAULT_VOICE


def _script(fm: dict, body: str) -> str:
    """The TTS-friendly version of the article: ~120-180 spoken seconds."""
    title  = get_str(fm, "title")
    tl_dr  = get_str(fm, "tl_dr")
    lead   = get_str(fm, "lead")
    desc   = get_str(fm, "description")

    intro_lines = [title]
    if tl_dr:
        intro_lines.append(tl_dr)
    elif desc:
        intro_lines.append(desc)
    if lead and lead.lower() != (tl_dr or desc or "").lower():
        intro_lines.append(lead)

    # Pull the first 1-2 prose paragraphs of the body (strip markdown).
    body_text = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    body_text = re.sub(r"!\[.*?\]\(.*?\)", "", body_text)
    body_text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", body_text)
    body_text = re.sub(r"^#{1,6}\s+.*$", "", body_text, flags=re.MULTILINE)
    body_text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", body_text)
    paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip() and len(p.strip()) > 60]
    intro_lines.extend(paragraphs[:2])

    intro_lines.append("This audio version was produced automatically by GlobalBR News.")
    return "\n\n".join(intro_lines)[:3500]


async def _synth(text: str, dest: Path, voice: str) -> bool:
    try:
        import edge_tts
    except ImportError:
        log.warning("edge_tts not installed — skipping audio for %s", dest.name)
        return False
    try:
        communicate = edge_tts.Communicate(text, voice, rate="+4%", pitch="+0Hz")
        await communicate.save(str(dest))
        return dest.exists() and dest.stat().st_size > 1024
    except Exception as e:
        log.warning("edge-tts failed for %s: %s", dest.name, e)
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        return False


def _update_frontmatter(path: Path, audio_rel: str, duration: int | None = None) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        return
    fm = parts[1]
    body = parts[2]
    if re.search(r"^audio:", fm, re.MULTILINE):
        fm = re.sub(r'^audio:.*$', f'audio: "{audio_rel}"', fm, flags=re.MULTILINE)
    else:
        fm = fm.rstrip("\n") + f'\naudio: "{audio_rel}"\n'
    if duration is not None and not re.search(r"^audio_duration:", fm, re.MULTILINE):
        fm = fm.rstrip("\n") + f'\naudio_duration: {duration}\n'
    path.write_text(f"---{fm}---{body}", encoding="utf-8")


def _eligible_posts() -> list[Path]:
    cutoff = date.today() - timedelta(days=LOOKBACK_D)
    out: list[Path] = []
    for path in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        try:
            stem = path.stem
            y, m, d = stem.split("-")[:3]
            dt = date(int(y), int(m), int(d))
        except Exception:
            continue
        if dt < cutoff:
            break
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^audio:", text, re.MULTILINE):
            continue
        if not text.startswith("---"):
            continue
        out.append(path)
        if len(out) >= MAX_PER_RUN * 2:  # buffer in case some fail
            break
    return out


async def _main_async() -> int:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    posts = _eligible_posts()
    if not posts:
        log.info("No eligible posts (all recent posts already have audio).")
        return 0

    produced = 0
    for path in posts:
        if produced >= MAX_PER_RUN:
            break
        text = path.read_text(encoding="utf-8", errors="replace")
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        fm = parse(text)
        body = parts[2]
        script = _script(fm, body)
        if len(script) < 80:
            continue
        slug = path.stem
        mp3 = AUDIO_DIR / f"{slug}.mp3"
        voice = _voice_for(fm)
        ok = await _synth(script, mp3, voice)
        if not ok:
            continue
        audio_rel = "/" + str(mp3.relative_to(Path(__file__).parent)).replace("\\", "/")
        _update_frontmatter(path, audio_rel)
        produced += 1
        log.info("🔊 %s (%s)", mp3.name, voice)

    log.info("Done — %d audio file(s) produced.", produced)
    return produced


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
