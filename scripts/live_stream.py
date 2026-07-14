#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_stream.py — Loop a long video to YouTube Live 24/7.
"""

import os
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)



def main():
    stream_key = os.environ.get("YOUTUBE_STREAM_KEY")
    if not stream_key:
        log.error("Missing YOUTUBE_STREAM_KEY environment variable.")
        return

    videos_dir = Path("_videos")
    long_videos = list(videos_dir.glob("long_video_*.mp4"))
    
    if not long_videos:
        log.error(f"No long_video_*.mp4 found in {videos_dir}. Run generate_long_video.py first.")
        return
        
    # Pick the most recently generated video
    latest_video = sorted(long_videos, key=lambda p: p.stat().st_mtime)[-1]
    log.info(f"Starting 24/7 Live Stream using: {latest_video.name}")
    
    rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
    
    cmd = [
        "ffmpeg",
        "-re",  # Read input at native frame rate
        "-stream_loop", "-1",  # Infinite loop
        "-i", str(latest_video),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-maxrate", "3000k",
        "-bufsize", "6000k",
        "-pix_fmt", "yuv420p",
        "-g", "60",  # Keyframe interval (2s for 30fps)
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-f", "flv",
        rtmp_url
    ]
    
    log.info("Running FFmpeg stream loop...")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        log.info("Stream interrupted by user.")
    except subprocess.CalledProcessError as e:
        log.error(f"FFmpeg crashed: {e}")



if __name__ == "__main__":
    main()
