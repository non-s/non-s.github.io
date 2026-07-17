#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_stream_dynamic.py -- 24/7 lofi live relay with self-healing broadcast.

Streams gaplessly to YouTube Live using an MPEG-TS pipe: loops whichever
long_video_*.mp4 files exist (built by generate_lofi_long_video.py, a
silent landscape lofi b-roll compilation), mixing in a track from the local
Jamendo bgm library on the way in since the source video itself carries no
audio. A background thread keeps a public broadcast bound to the stream key
at all times -- ffmpeg can push RTMP data forever, but that alone never
puts the channel back on-air once a broadcast ends, so a new one has to be
created and bound whenever none is active.

This used to also run an AI "virtual host" that answered live chat
questions with synthesized speech cut into the stream. That feature has
been removed: this channel's format is deliberately narration-free (loop +
music only), and a spoken voice answering chat mid-loop would break that
format on every question asked.
"""

import logging
import os
import random
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from googleapiclient.discovery import build  # noqa: E402

from utils.youtube_oauth import can_manage_comments, credentials_from_token_info, load_token_info  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BGM_DIR = ROOT / "_assets" / "audio" / "bgm"

BROADCAST_TITLE = "\U0001f534 24/7 Lofi Beats to Relax/Study to | Live"
BROADCAST_DESCRIPTION = (
    "Non-stop lofi beats, looping live -- cozy visuals and chill music to relax, study or unwind to."
)


class DynamicStreamer:
    def __init__(self, stream_key: str):
        self.stream_key = stream_key.strip()
        self.videos_dir = Path("_videos")
        self.temp_dir = Path("_videos/temp_stream")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_proc = None

        self.youtube = self._get_youtube_client()
        self.stream_id = None
        self.broadcast_id = None

    def _get_youtube_client(self):
        token_file = ROOT / "youtube_token.json"
        info = load_token_info(token_file)
        if not info.present or not can_manage_comments(info.data):
            log.warning("No valid youtube token for broadcast management.")
            return None
        creds = credentials_from_token_info(info, ["https://www.googleapis.com/auth/youtube.force-ssl"])
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def _find_stream_id(self) -> str | None:
        """Resolve the liveStreams resource bound to our RTMP stream key."""
        if self.stream_id or not self.youtube:
            return self.stream_id
        try:
            response = self.youtube.liveStreams().list(part="id,cdn", mine=True, maxResults=50).execute()
            for item in response.get("items", []):
                stream_name = ((item.get("cdn") or {}).get("ingestionInfo") or {}).get("streamName", "")
                if stream_name and stream_name == self.stream_key:
                    self.stream_id = item.get("id")
                    log.info(f"Resolved liveStreams id {self.stream_id} for our stream key.")
                    break
        except Exception as e:
            log.error(f"Failed to list liveStreams: {e}")
        return self.stream_id

    def ensure_live_broadcast(self):
        """Create+bind a new public broadcast whenever none is currently
        active or upcoming, so the 24/7 relay never streams into a void."""
        if not self.youtube:
            return
        try:
            response = (
                self.youtube.liveBroadcasts()
                .list(
                    part="snippet,status",
                    broadcastStatus="all",
                    broadcastType="all",
                    maxResults=50,
                )
                .execute()
            )
            for item in response.get("items", []):
                life_cycle = (item.get("status") or {}).get("lifeCycleStatus") or ""
                if life_cycle in {"live", "ready", "testing"}:
                    self.broadcast_id = item.get("id")
                    return
        except Exception as e:
            log.error(f"Failed to list liveBroadcasts: {e}")
            return

        stream_id = self._find_stream_id()
        if not stream_id:
            log.error("No liveStreams resource matches YOUTUBE_STREAM_KEY; cannot create a broadcast.")
            return

        log.info("No active/ready broadcast found. Creating a new one so the channel goes live again...")
        try:
            insert_response = (
                self.youtube.liveBroadcasts()
                .insert(
                    part="snippet,status,contentDetails",
                    body={
                        "snippet": {
                            "title": BROADCAST_TITLE,
                            "description": BROADCAST_DESCRIPTION,
                            "scheduledStartTime": datetime.now(timezone.utc).isoformat(),
                        },
                        "status": {
                            "privacyStatus": "public",
                            "selfDeclaredMadeForKids": False,
                        },
                        "contentDetails": {
                            "enableAutoStart": True,
                            "enableAutoStop": False,
                            "enableDvr": True,
                            "latencyPreference": "normal",
                        },
                    },
                )
                .execute()
            )
            new_broadcast_id = insert_response.get("id")
            self.youtube.liveBroadcasts().bind(
                id=new_broadcast_id,
                part="id,contentDetails",
                streamId=stream_id,
            ).execute()
            self.broadcast_id = new_broadcast_id
            log.info(
                f"Created and bound new broadcast {new_broadcast_id}. It will auto-go-live once video data arrives."
            )
        except Exception as e:
            log.error(f"Failed to create/bind a new broadcast: {e}")

    def _pick_bgm_track(self) -> Path | None:
        tracks = list(BGM_DIR.glob("jamendo_*.mp3"))
        return random.choice(tracks) if tracks else None

    def convert_to_ts(self, mp4_path: Path) -> Path:
        out_ts = self.temp_dir / f"{mp4_path.stem}.ts"
        if out_ts.exists() and out_ts.stat().st_size > 0:
            return out_ts

        bgm_path = self._pick_bgm_track()
        log.info(f"Converting {mp4_path.name} to MPEG-TS for streaming (fixing keyframes)...")
        if bgm_path:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(mp4_path),
                "-stream_loop",
                "-1",
                "-i",
                str(bgm_path),
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-r",
                "30",
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
                "-b:v",
                "4500k",
                "-maxrate",
                "4500k",
                "-bufsize",
                "9000k",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "44100",
                "-shortest",
                "-f",
                "mpegts",
                str(out_ts),
            ]
        else:
            # A stream with no audio track at all can leave YouTube's live
            # ingestion stuck validating the broadcast instead of ever
            # transitioning it out of "waiting for stream data" -- so even
            # this fallback carries a (silent) audio track rather than
            # dropping it with -an. This should be rare: the workflow syncs
            # the bgm library before every relay run.
            log.warning("No bgm track found in %s; streaming this segment with silent audio.", BGM_DIR)
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(mp4_path),
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=stereo",
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-r",
                "30",
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
                "-b:v",
                "4500k",
                "-maxrate",
                "4500k",
                "-bufsize",
                "9000k",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "44100",
                "-shortest",
                "-f",
                "mpegts",
                str(out_ts),
            ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            log.error(f"FFmpeg failed to convert {mp4_path.name} to TS. Exit code: {res.returncode}")
            log.error(f"FFmpeg stderr: {res.stderr}")
        return out_ts

    def broadcast_monitor_thread(self):
        """Keep a public broadcast bound to our stream key at all times.
        This is what makes the relay self-heal on YouTube's side: ffmpeg
        can push RTMP data forever, but that alone never puts the channel
        back on-air once a broadcast ends -- a new one has to be created
        and bound."""
        log.info("Starting Broadcast Monitor Thread...")
        while True:
            try:
                self.ensure_live_broadcast()
            except Exception as e:
                log.error(f"Broadcast monitor error: {e}")
            time.sleep(120)

    def content_updater_thread(self):
        log.info("Starting Content Updater Thread...")
        while True:
            try:
                log.info("Checking for new generated videos...")
                run_id_cmd = [
                    "gh",
                    "run",
                    "list",
                    "--workflow=Generate Long Video",
                    "--status=success",
                    "--limit",
                    "1",
                    "--json",
                    "databaseId",
                    "--jq",
                    ".[0].databaseId",
                ]
                result = subprocess.run(run_id_cmd, capture_output=True, text=True)
                run_id = result.stdout.strip()
                if run_id and run_id != "null":
                    log.info(f"Found latest run {run_id}, downloading if not present...")
                    dl_cmd = [
                        "gh",
                        "run",
                        "download",
                        str(run_id),
                        "--name",
                        f"long-video-{run_id}",
                        "--dir",
                        str(self.videos_dir),
                    ]
                    subprocess.run(dl_cmd, capture_output=True)
            except Exception as e:
                log.error(f"Content updater error: {e}")
            time.sleep(3600)  # Check every hour

    def start_ffmpeg_pipe(self):
        rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{self.stream_key}"
        cmd = [
            "ffmpeg",
            "-re",  # Important: read stdin at native frame rate!
            "-i",
            "pipe:0",  # Read from stdin
            "-c",
            "copy",  # Copy the already compatible TS streams
            "-f",
            "flv",
            rtmp_url,
        ]
        log.info("Starting master FFmpeg pipe...")
        self.ffmpeg_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def run(self):
        long_videos = list(self.videos_dir.glob("long_video_*.mp4"))
        if not long_videos:
            log.error("No long videos found.")
            return

        # Make sure a broadcast exists and is bound *before* we start
        # pushing video, so YouTube has somewhere to auto-start it.
        self.ensure_live_broadcast()

        threading.Thread(target=self.content_updater_thread, daemon=True).start()
        threading.Thread(target=self.broadcast_monitor_thread, daemon=True).start()

        self.start_ffmpeg_pipe()

        try:
            while True:
                long_videos = list(self.videos_dir.glob("long_video_*.mp4"))
                if not long_videos:
                    time.sleep(5)
                    continue

                chosen_mp4 = random.choice(long_videos)
                target = self.convert_to_ts(chosen_mp4)
                log.info(f"Looping base video: {target.name}")

                if self.ffmpeg_proc.poll() is not None:
                    log.error("Master FFmpeg pipe crashed! Restarting...")
                    self.start_ffmpeg_pipe()

                try:
                    with open(target, "rb") as f:
                        while True:
                            if self.ffmpeg_proc.poll() is not None:
                                log.error("Master FFmpeg pipe crashed during streaming! Breaking out to restart...")
                                break

                            chunk = f.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            self.ffmpeg_proc.stdin.write(chunk)
                            self.ffmpeg_proc.stdin.flush()
                except Exception as e:
                    log.error(f"Error streaming {target.name}: {e}")
                    time.sleep(2)
                    if self.ffmpeg_proc:
                        self.ffmpeg_proc.kill()
                        self.ffmpeg_proc.wait()
                    time.sleep(5)  # Cooldown before reconnecting
                    self.start_ffmpeg_pipe()

        except KeyboardInterrupt:
            log.info("Stopping stream...")
        finally:
            if self.ffmpeg_proc and self.ffmpeg_proc.stdin:
                self.ffmpeg_proc.stdin.close()
                self.ffmpeg_proc.wait()


def main():
    stream_key = os.environ.get("YOUTUBE_STREAM_KEY")
    if not stream_key:
        log.warning("No YOUTUBE_STREAM_KEY found. Running in local test mode (writing to output.flv).")
        os.environ["YOUTUBE_STREAM_KEY"] = "test"

    streamer = DynamicStreamer(os.environ.get("YOUTUBE_STREAM_KEY"))
    if stream_key is None:
        streamer.start_ffmpeg_pipe = lambda: setattr(
            streamer,
            "ffmpeg_proc",
            subprocess.Popen(
                ["ffmpeg", "-y", "-re", "-i", "pipe:0", "-c", "copy", "test_output.flv"],
                stdin=subprocess.PIPE,
            ),
        )

    streamer.run()


if __name__ == "__main__":
    main()
