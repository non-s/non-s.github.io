#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_long_video.py — Fetch, narrate, and compose a long horizontal video (Compilation).
"""

import os
os.environ["BRAND_CARDS_ENABLED"] = "0"

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
from utils.captions import transcribe as captions_transcribe, write_ass, group_words_into_phrases
from utils.video_compose import build_broll_short
from utils.nature_strategy import NATURE_TOPICS
from generate_shorts import text_to_speech, pick_voice

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

VIDEOS_DIR = Path("_videos")
MAX_SEGMENTS = 15

async def generate_segment(segment_index: int, topic_key: str, query: str) -> Path | None:
    """Generate a single 16:9 segment."""
    segment_dir = VIDEOS_DIR / "compilation_temp"
    segment_dir.mkdir(parents=True, exist_ok=True)

    # 1. Multi-Agent Script Generation
    from utils.multi_agent_board import run_editorial_board
    data = run_editorial_board(query)

    # 1. Fetch B-roll with Multimodal Quality Gate
    from utils.visual_qa import evaluate_frame
    
    # We ask for up to 3 clips to have fallbacks if visual QA fails
    clips = fetch_broll_clips(query, want_n=3, orientation="landscape")
    if not clips:
        log.warning(f"No clips found for {query}")
        return None
        
    valid_clip_path = None
    for idx, clip in enumerate(clips):
        clip_path = segment_dir / f"clip_{segment_index}_{idx}.mp4"
        if not clip_path.exists():
            r = subprocess.run(["curl", "-sL", clip.download_url, "-o", str(clip_path)])
            if r.returncode != 0:
                continue
        
        # Extract a middle frame for Multimodal Validation
        frame_path = segment_dir / f"frame_{segment_index}_{idx}.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", str(clip_path), "-vf", "select=eq(n\,30)", "-vframes", "1", str(frame_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if frame_path.exists():
            evaluation = evaluate_frame(frame_path, expected_subject=query)
            if evaluation.get("approved", True):
                log.info(f"Multimodal Gate Approved clip {idx} for {query}")
                valid_clip_path = clip_path
                break
            else:
                log.warning(f"Multimodal Gate Rejected clip {idx} for {query}. Reason: {evaluation.get('reason')}")
        else:
            # If ffmpeg fails, just accept the video
            valid_clip_path = clip_path
            break
            
    if not valid_clip_path:
        log.warning(f"All clips rejected by Multimodal Gate for {query}")
        return None
    
    # Symlink or rename the valid clip to the expected clip_path
    final_clip_path = segment_dir / f"clip_{segment_index}.mp4"
    if final_clip_path.exists(): final_clip_path.unlink()
    valid_clip_path.rename(final_clip_path)

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
        phrases = group_words_into_phrases(words, max_words=3, max_gap_s=0.45, max_duration_s=1.8)
        write_ass(phrases, ass_path, video_w=1920, video_h=1080, margin_v=120)

    # 5. Compose
    out_mp4 = segment_dir / f"segment_{segment_index}.mp4"
    ok = build_broll_short(
        broll_paths=[clip_path],
        audio_path=audio_path,
        output_path=out_mp4,
        ass_subtitle_path=ass_path if ass_path.exists() else None,
        target_w=1920,
        target_h=1080,
        enable_brand_cards=False,
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

    # 1. Democracy Selvagem (Live Votes Integration)
    try:
        import json
        votes_file = Path("_data/live_votes.json")
        if votes_file.exists():
            votes = json.loads(votes_file.read_text())
            if votes:
                top_vote = max(votes, key=votes.get)
                # Inject the winning vote as the very first segment of the documentary
                topics.insert(0, (top_vote, {"queries": [top_vote]}))
                log.info(f"Democracia Selvagem: Injecting Audience Vote Winner: {top_vote}")
                # Clear votes for the next cycle
                votes_file.unlink()
    except Exception as e:
        log.error(f"Failed to read live votes: {e}")

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
        # Upload compilation to YouTube if token exists
        if Path("youtube_token.json").exists():
            log.info("youtube_token.json found. Attempting to upload compilation to YouTube...")
            try:
                from upload_youtube import get_youtube_service
                from googleapiclient.http import MediaFileUpload

                youtube = get_youtube_service()

                title = f"The Wonders of Nature & Science | 15-in-1 Documentary Compilation"
                description = (
                    "Explore the incredible wonders of our natural world, from rare geological phenomena "
                    "to deep ecosystems and astronomical views. A compilation of 15 short documentaries.\n\n"
                    "#Nature #Science #Documentary #WildBrief"
                )
                tags = ["Nature", "Science", "Documentary", "WildBrief", "Ecosystems", "Astronomy"]

                request = youtube.videos().insert(
                    part="snippet,status",
                    body={
                        "snippet": {
                            "title": title,
                            "description": description,
                            "tags": tags,
                            "categoryId": "28",  # Science & Technology
                        },
                        "status": {
                            "privacyStatus": "public",
                            "selfDeclaredMadeForKids": False
                        },
                    },
                    media_body=MediaFileUpload(str(final_output), mimetype="video/mp4", chunksize=1024*1024, resumable=True),
                )

                log.info(f"Uploading {final_output.name} to YouTube...")
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        log.info(f"Upload progress: {int(status.progress() * 100)}%")

                video_id = response.get("id")
                if video_id:
                    log.info(f"SUCCESS: Compilation uploaded to YouTube! Video URL: https://youtu.be/{video_id}")
                else:
                    log.error("Failed to retrieve uploaded video ID.")
            except Exception as e:
                log.error(f"Failed to upload compiled video to YouTube: {e}")
        else:
            log.info("No youtube_token.json found; skipping YouTube upload.")
    else:
        log.error("Failed to concatenate segments.")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
