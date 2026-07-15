#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_stream_dynamic.py — Interactive 24/7 Live Stream with Virtual Host.

This script streams gaplessly to YouTube Live using an MPEG-TS pipe.
While streaming the main content, a background thread fetches Live Chat,
generates AI responses to viewer questions, and renders dynamic clips
which are seamlessly injected into the stream!
"""

import os
import time
import json
import subprocess
import threading
import shutil
import glob
from pathlib import Path

# Fix path for imports
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

from utils.ai_helper import ai_text
import asyncio
from generate_shorts import text_to_speech
from utils.youtube_oauth import load_token_info, credentials_from_token_info, can_manage_comments
from googleapiclient.discovery import build


class DynamicStreamer:
    def __init__(self, stream_key: str):
        self.stream_key = stream_key
        self.videos_dir = Path("_videos")
        self.temp_dir = Path("_videos/temp_stream")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_proc = None
        
        self.dynamic_queue = []
        self.lock = threading.Lock()
        
        self.youtube = self._get_youtube_client()
        self.live_chat_id = None

    def _get_youtube_client(self):
        token_file = ROOT / "youtube_token.json"
        info = load_token_info(token_file)
        if not info.present or not can_manage_comments(info.data):
            log.warning("No valid youtube token for chat fetching.")
            return None
        creds = credentials_from_token_info(info, ["https://www.googleapis.com/auth/youtube.readonly"])
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def _update_live_chat_id(self):
        if not self.youtube:
            return
        try:
            request = self.youtube.liveBroadcasts().list(
                part="snippet",
                broadcastStatus="active",
                broadcastType="all"
            )
            response = request.execute()
            items = response.get("items", [])
            if items:
                self.live_chat_id = items[0]["snippet"].get("liveChatId")
                log.info(f"Found active liveChatId: {self.live_chat_id}")
            else:
                log.info("No active broadcast found.")
        except Exception as e:
            log.error(f"Failed to fetch liveChatId: {e}")

    def fetch_questions_from_chat(self) -> list:
        if not self.youtube or not self.live_chat_id:
            return []
        try:
            request = self.youtube.liveChatMessages().list(
                liveChatId=self.live_chat_id,
                part="snippet,authorDetails",
                maxResults=50
            )
            response = request.execute()
            items = response.get("items", [])
            questions = []
            votes = []
            for item in items:
                text = item["snippet"]["displayMessage"]
                author = item["authorDetails"]["displayName"]
                if "?" in text and len(text) > 10:
                    questions.append({"author": author, "text": text})
                if text.lower().startswith("!vote "):
                    vote = text[6:].strip().lower()
                    if len(vote) < 20:
                        votes.append(vote)
            
            # Tally votes and save to JSON
            if votes:
                try:
                    votes_file = Path("_data/live_votes.json")
                    votes_file.parent.mkdir(exist_ok=True)
                    current_votes = json.loads(votes_file.read_text()) if votes_file.exists() else {}
                    for v in votes:
                        current_votes[v] = current_votes.get(v, 0) + 1
                    votes_file.write_text(json.dumps(current_votes, indent=2))
                except Exception as e:
                    log.error(f"Failed to record votes: {e}")
                    
            return questions
        except Exception as e:
            log.error(f"Failed to fetch chat messages: {e}")
            return []

    def convert_to_ts(self, mp4_path: Path) -> Path:
        ts_path = self.temp_dir / f"{mp4_path.stem}.ts"
        if ts_path.exists():
            return ts_path
            
        log.info(f"Converting {mp4_path.name} to MPEG-TS...")
        # Scale to 1920x1080 and ensure consistent framerate/audio for gapless concat
        cmd = [
            "ffmpeg", "-y", "-i", str(mp4_path),
            "-vf", "scale=1920:1080,fps=30",
            "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high",
            "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
            "-f", "mpegts",
            str(ts_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return ts_path

    def generate_host_response(self, question: dict) -> Path | None:
        log.info(f"Generating Virtual Host response for: {question['author']} - {question['text']}")
        
        # 1. Generate Answer Script
        prompt = (
            f"A viewer named '{question['author']}' asked this in our live chat: '{question['text']}'. "
            "Write a very brief, punchy, and fascinating 2-3 sentence answer. "
            "Start by saying 'Great question from [Name]!' or similar. Keep it under 40 words."
        )
        script = ai_text(prompt, timeout=15)
        if not script:
            return None
            
        # 2. Generate TTS
        tts_path = self.temp_dir / f"response_{int(time.time())}.mp3"
        asyncio.run(text_to_speech(script, str(tts_path)))
        if not tts_path.exists():
            return None
            
        # 3. Generate Video Clip
        # We'll create a simple background with text overlay
        out_mp4 = self.temp_dir / f"response_{int(time.time())}.mp4"
        
        # Make a black background video of the exact duration of the audio
        # Draw the text in the center
        safe_text = script.replace("'", "").replace(":", "").replace("\\", "")
        viewer_text = f"Viewer {question['author']} asked: {question['text']}".replace("'", "")
        
        vf_string = (
            f"color=c=black:s=1920x1080:r=30,"
            f"drawtext=text='{viewer_text}':fontcolor=yellow:fontsize=48:x=(w-text_w)/2:y=200,"
            f"drawtext=text='{safe_text}':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080",
            "-i", str(tts_path),
            "-vf", vf_string,
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
            "-c:a", "aac",
            "-shortest",
            str(out_mp4)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        return self.convert_to_ts(out_mp4)

    def chat_monitor_thread(self):
        log.info("Starting Chat Monitor Thread...")
        last_question_time = 0
        while True:
            try:
                if not self.live_chat_id:
                    self._update_live_chat_id()
                
                if self.live_chat_id and time.time() - last_question_time > 600:  # Every 10 mins
                    questions = self.fetch_questions_from_chat()
                    if questions:
                        q = questions[-1]  # Pick the latest
                        ts_file = self.generate_host_response(q)
                        if ts_file:
                            with self.lock:
                                self.dynamic_queue.append(ts_file)
                            last_question_time = time.time()
                
            except Exception as e:
                log.error(f"Chat monitor error: {e}")
            time.sleep(60)

    def start_ffmpeg_pipe(self):
        rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{self.stream_key}"
        cmd = [
            "ffmpeg",
            "-re",           # Important: read stdin at native frame rate!
            "-i", "pipe:0",  # Read from stdin
            "-c", "copy",    # Copy the already compatible TS streams
            "-f", "flv",
            rtmp_url
        ]
        log.info("Starting master FFmpeg pipe...")
        self.ffmpeg_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def run(self):
        long_videos = list(self.videos_dir.glob("long_video_*.mp4"))
        if not long_videos:
            log.error("No long videos found.")
            return

        latest_mp4 = sorted(long_videos, key=lambda p: p.stat().st_mtime)[-1]
        base_ts = self.convert_to_ts(latest_mp4)

        # Start background threads
        threading.Thread(target=self.chat_monitor_thread, daemon=True).start()

        self.start_ffmpeg_pipe()

        try:
            while True:
                # Check if we have a dynamic clip waiting
                next_clip = None
                with self.lock:
                    if self.dynamic_queue:
                        next_clip = self.dynamic_queue.pop(0)

                if next_clip:
                    log.info(f"Injecting dynamic clip: {next_clip.name}")
                    target = next_clip
                else:
                    log.info(f"Looping base video: {base_ts.name}")
                    target = base_ts

                # Stream the file chunk by chunk into ffmpeg's stdin
                # Since ffmpeg uses -re, it will throttle this read to exactly 1x real-time!
                with open(target, "rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        self.ffmpeg_proc.stdin.write(chunk)
                        self.ffmpeg_proc.stdin.flush()

        except KeyboardInterrupt:
            log.info("Stopping stream...")
        finally:
            if self.ffmpeg_proc:
                self.ffmpeg_proc.stdin.close()
                self.ffmpeg_proc.wait()


def main():
    stream_key = os.environ.get("YOUTUBE_STREAM_KEY")
    if not stream_key:
        log.warning("No YOUTUBE_STREAM_KEY found. Running in local test mode (writing to output.flv).")
        # Override to local file for testing if no key
        os.environ["YOUTUBE_STREAM_KEY"] = "test"
    
    streamer = DynamicStreamer(os.environ.get("YOUTUBE_STREAM_KEY"))
    if stream_key is None:
        streamer.start_ffmpeg_pipe = lambda: setattr(streamer, 'ffmpeg_proc', subprocess.Popen(
            ["ffmpeg", "-y", "-re", "-i", "pipe:0", "-c", "copy", "test_output.flv"], 
            stdin=subprocess.PIPE
        ))

    streamer.run()


if __name__ == "__main__":
    main()
