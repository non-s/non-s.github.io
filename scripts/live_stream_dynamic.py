#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_stream_dynamic.py -- 24/7 lofi live relay with self-healing broadcast.

The "Lofi Girl" format this channel is modeled on isn't several different
video clips cut together -- it's one single looping animation with a music
playlist rotating underneath, for hours. So this relay picks ONE random
anime/illustrated clip from the same Pixabay b-roll library the Shorts
generator uses (_assets/video/lofi_broll), loops it, and concatenates every
locally available Jamendo track into one playlist that plays through in
sequence and then repeats -- not a single song on loop for the whole
session. Streams gaplessly to YouTube Live using an MPEG-TS pipe.

A background thread keeps a public broadcast bound to the stream key at
all times -- ffmpeg can push RTMP data forever, but that alone never puts
the channel back on-air once a broadcast ends, so a new one has to be
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
BROLL_DIR = ROOT / "_assets" / "video" / "lofi_broll"

TARGET_W = 1920
TARGET_H = 1080
TARGET_FPS = 30
FALLBACK_SILENT_DURATION_S = 1800.0

BROADCAST_TITLE = "\U0001f534 24/7 Lofi Beats to Relax/Study to | Live"
BROADCAST_DESCRIPTION = (
    "Non-stop lofi beats, looping live -- cozy visuals and chill music to relax, study or unwind to."
)


def _audio_duration_s(path: Path) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return FALLBACK_SILENT_DURATION_S


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
                    self._rebrand_if_stale(item)
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

    def _rebrand_if_stale(self, broadcast_item: dict) -> None:
        """Fix an already-active broadcast's title/description if they
        don't match the current branding.

        ensure_live_broadcast() only creates a NEW broadcast when none is
        active -- an already-live/ready/testing broadcast created under
        older branding (e.g. the pre-lofi-pivot nature-facts title) would
        otherwise just keep getting reused forever with its stale title,
        even though the video/audio streaming through it is already lofi.
        """
        snippet = broadcast_item.get("snippet") or {}
        if snippet.get("title") == BROADCAST_TITLE and snippet.get("description") == BROADCAST_DESCRIPTION:
            return
        try:
            self.youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": broadcast_item.get("id"),
                    "snippet": {
                        "title": BROADCAST_TITLE,
                        "description": BROADCAST_DESCRIPTION,
                        "scheduledStartTime": snippet.get("scheduledStartTime")
                        or datetime.now(timezone.utc).isoformat(),
                    },
                },
            ).execute()
            log.info("Rebranded stale broadcast %s to current lofi title.", broadcast_item.get("id"))
        except Exception as e:
            log.warning(f"Failed to rebrand stale broadcast: {e}")

    def _pick_broll_clip(self) -> Path | None:
        clips = list(BROLL_DIR.glob("pixabay_*.mp4"))
        return random.choice(clips) if clips else None

    def _build_bgm_playlist(self) -> Path | None:
        """Concatenate every locally available bgm track into one file, so
        the loop segment plays through the whole library in sequence
        instead of a single track repeating for the whole session."""
        tracks = list(BGM_DIR.glob("jamendo_*.mp3"))
        if not tracks:
            return None
        playlist_path = self.temp_dir / "playlist.mp3"
        if playlist_path.exists() and playlist_path.stat().st_size > 0:
            return playlist_path
        random.shuffle(tracks)
        list_path = self.temp_dir / "playlist_concat.txt"
        list_path.write_text(
            "\n".join(f"file '{track.resolve()}'" for track in tracks) + "\n",
            encoding="utf-8",
        )
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(playlist_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception as exc:
            log.error(f"Failed to build bgm playlist: {exc}")
            return None
        if result.returncode != 0 or not playlist_path.exists():
            log.error(f"ffmpeg playlist concat exited {result.returncode}: {result.stderr[-500:]}")
            return None
        log.info("Built bgm playlist from %d track(s).", len(tracks))
        return playlist_path

    def build_loop_segment(self) -> Path | None:
        """Build (or reuse) the single video-loop + music-playlist segment
        this relay streams: one anime clip, looped for as long as the
        local bgm playlist takes to play through once, matching the
        "one video, whole playlist on loop" lofi-radio format instead of
        cutting between several different clips."""
        out_ts = self.temp_dir / "loop_segment.ts"
        if out_ts.exists() and out_ts.stat().st_size > 0:
            return out_ts

        clip_path = self._pick_broll_clip()
        if not clip_path:
            log.error("No lofi b-roll clip found in %s to loop.", BROLL_DIR)
            return None

        playlist_path = self._build_bgm_playlist()
        video_filter = (
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},fps={TARGET_FPS},"
            f"zoompan=z='min(zoom+0.0003,1.06)':d=1:s={TARGET_W}x{TARGET_H}:fps={TARGET_FPS},"
            "setsar=1"
        )
        cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip_path)]
        if playlist_path:
            duration_s = _audio_duration_s(playlist_path)
            cmd += ["-stream_loop", "-1", "-i", str(playlist_path), "-map", "0:v", "-map", "1:a"]
        else:
            log.warning("No bgm tracks found in %s; looping this segment with silent audio.", BGM_DIR)
            duration_s = FALLBACK_SILENT_DURATION_S
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v", "-map", "1:a"]
        cmd += [
            "-vf",
            video_filter,
            "-t",
            f"{duration_s:.3f}",
            "-r",
            str(TARGET_FPS),
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
            "-f",
            "mpegts",
            str(out_ts),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=max(300, int(duration_s) + 120))
        except Exception as exc:
            log.error(f"Failed to build loop segment: {exc}")
            return None
        if result.returncode != 0:
            log.error(f"FFmpeg failed to build loop segment. Exit code: {result.returncode}")
            log.error(f"FFmpeg stderr: {result.stderr[-2000:]}")
            return None
        if not out_ts.exists() or out_ts.stat().st_size == 0:
            return None
        log.info("Built loop segment from %s (%.1f min).", clip_path.name, duration_s / 60)
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
        if not list(BROLL_DIR.glob("pixabay_*.mp4")):
            log.error("No lofi b-roll clips found in %s.", BROLL_DIR)
            return

        # Make sure a broadcast exists and is bound *before* we start
        # pushing video, so YouTube has somewhere to auto-start it.
        self.ensure_live_broadcast()

        threading.Thread(target=self.broadcast_monitor_thread, daemon=True).start()

        self.start_ffmpeg_pipe()

        try:
            while True:
                target = self.build_loop_segment()
                if not target:
                    time.sleep(10)
                    continue
                log.info(f"Looping segment: {target.name}")

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
