#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_long_video.py — Fetch, narrate, and compose a long horizontal video (Compilation).
"""

import asyncio
import json
import logging
import random
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from utils.ai_helper import ai_text
from utils.broll import fetch_broll_clips
from utils.captions import transcribe as captions_transcribe, write_ass
from utils.video_compose import build_broll_short
from utils.nature_strategy import NATURE_TOPICS
from generate_shorts import text_to_speech, pick_voice

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

VIDEOS_DIR = Path("_videos")
MAX_SEGMENTS = 15

PROMPT = """
You are a nature documentary narrator.
Write a 3-sentence script about the following topic.
Sentence 1: The hook.
Sentence 2: The explanation.
Sentence 3: The payoff/conclusion.
Use clear, easy to understand English.
Return ONLY valid JSON matching this schema:
{
    "title": "A short descriptive title",
    "script": "The full 3-sentence script here",
    "hook": "The hook (sentence 1) here"
}

TOPIC: {topic}
"""



async def generate_segment(segment_index: int, topic_key: str, query: str) -> Path | None:
    """Generate a single 16:9 segment."""
    segment_dir = VIDEOS_DIR / "compilation_temp"
    segment_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch B-roll
    clips = fetch_broll_clips(query, want_n=1, orientation="landscape")
    if not clips:
        log.warning(f"No clips found for {query}")
        return None
    clip = clips[0]
    clip_path = segment_dir / f"clip_{segment_index}.mp4"
    if not clip_path.exists():
        r = subprocess.run(["curl", "-sL", clip.download_url, "-o", str(clip_path)])
        if r.returncode != 0:
            return None

    # 2. AI Script
    prompt = PROMPT.replace("{topic}", query)
    try:
        response = ai_text(prompt, max_tokens=150, fallback={"title": "", "script": "", "hook": ""})
        data = json.loads(response) if isinstance(response, str) else response
    except Exception as e:
        log.error(f"AI failed: {e}")
        return None

    script = data.get("script")
    if not script:
        return None

    # 3. TTS
    audio_path = segment_dir / f"audio_{segment_index}.mp3"
    voice = pick_voice(query)
    await text_to_speech(script, audio_path, voice=voice)
    if not audio_path.exists():
        return None

    # 4. Captions
    ass_path = segment_dir / f"captions_{segment_index}.ass"
    words = captions_transcribe(audio_path, script)
    if words:
        write_ass(words, ass_path, video_w=1920, video_h=1080, margin_v=120)

    # 5. Compose
    out_mp4 = segment_dir / f"segment_{segment_index}.mp4"
    ok = build_broll_short(
        broll_paths=[clip_path],
        audio_path=audio_path,
        output_path=out_mp4,
        ass_subtitle_path=ass_path if ass_path.exists() else None,
        target_w=1920,
        target_h=1080
    )
    return out_mp4 if ok and out_mp4.exists() else None




async def async_main():
    VIDEOS_DIR.mkdir(exist_ok=True)
    compilation_temp = VIDEOS_DIR / "compilation_temp"
    if compilation_temp.exists():
        shutil.rmtree(compilation_temp)
    compilation_temp.mkdir(parents=True)

    topics = list(NATURE_TOPICS.items())
    random.shuffle(topics)

    segment_paths = []

    for i in range(min(MAX_SEGMENTS, len(topics))):
        key, data = topics[i]
        queries = data.get("queries", [key])
        query = random.choice(queries)
        log.info(f"Generating segment {i+1} for {query}...")
        path = await generate_segment(i, key, query)
        if path:
            segment_paths.append(path)

    if not segment_paths:
        log.error("Failed to generate any segments.")
        return

    # Concat
    list_path = compilation_temp / "concat.txt"
    lines = [f"file '{p.resolve()}'" for p in segment_paths]
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_output = VIDEOS_DIR / f"long_video_{date_str}.mp4"

    log.info(f"Concatenating {len(segment_paths)} segments into {final_output}...")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(final_output)]
    r = subprocess.run(cmd)

    if r.returncode == 0 and final_output.exists():
        log.info(f"SUCCESS: Long video created at {final_output}")
    else:
        log.error("Failed to concatenate segments.")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

