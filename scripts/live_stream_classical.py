#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_stream_classical.py -- 24/7 "Amber Hours Classical" live relay with
self-healing broadcast.

Fourth content pillar's live component (chat, 2026-07-22): the one fixed,
hand-picked real Pixabay clip (`_assets/video/pinned_classical_ambience.mp4`)
loops under a real, rotating playlist of every currently-synced classical/
orchestral/piano track from Jamendo (`scripts/sync_classical_music.py`,
target ~150 tracks -- see that script's module docstring for the real
ramp-up curve). Every track is genuinely licensed (CC BY, commercially
safe) real music, unlike the rain pillar's procedurally-synthesized audio
-- this pillar's whole audio identity IS the licensed catalog, so there is
no "no music layer" fallback here the way the rain pillar has: if the
library is completely empty, this relay has nothing to stream and exits
with a clear error rather than faking silence or a placeholder tone.

Written as its own dedicated relay rather than adding a pillar-switch
branch to scripts/live_stream_dynamic.py (that file is intentionally
storm-only) -- but reuses the same proven patterns from that file:
self-healing broadcast creation/rebrand-if-stale, thumbnail-setting,
seamless-loop-crossfade bake for the video side, and the outer
self-restarting `while true` loop. See that file for the fuller
explanation of each technique; comments here focus on what's different
for this pillar (the playlist concat, no music-optional branch, English
copy).

A single ffmpeg process streams straight to RTMP with `-stream_loop -1` on
both the video clip and the concatenated playlist -- no bake-to-file step
sized to the stream's length, so a restart just relaunches ffmpeg against
the same (cached) inputs and is back on air within seconds.
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
from googleapiclient.http import MediaFileUpload  # noqa: E402

from utils.ai_titling import generate_classical_video_copy  # noqa: E402
from utils.youtube_oauth import can_manage_comments, credentials_from_token_info, load_token_info  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# The one fixed real clip this relay always loops -- no rotation, no
# illustrated fallback (none exists for this pillar).
PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_classical_ambience.mp4"
CLASSICAL_DIR = ROOT / "_assets" / "audio" / "classical"
THUMBNAIL_IMAGE = ROOT / "_assets" / "branding" / "classical_ambience_thumbnail.jpg"

TARGET_W = 1920
TARGET_H = 1080
TARGET_FPS = 30
LOOP_CROSSFADE_S = 1.0

_FALLBACK_BROADCAST_TITLE = "Classical Piano & Orchestral Music -- Amber Hours Classical \U0001f3b9 [24/7 LIVE]"
_FALLBACK_BROADCAST_DESCRIPTION = (
    "Real classical, orchestral and piano recordings, licensed and rotating, looping live -- "
    "for studying, focus, reading or a calm night. Music sourced from Jamendo under Creative "
    "Commons Attribution (CC BY) licenses; individual track/performer credit for each piece is "
    "included in that piece's own archived upload on this channel."
)

_LEGACY_BROADCAST_TITLES = {_FALLBACK_BROADCAST_TITLE}


def _media_duration_s(path: Path) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


class ClassicalStreamer:
    def __init__(self, stream_key: str):
        self.stream_key = stream_key.strip()
        self.videos_dir = Path("_videos")
        self.temp_dir = Path("_videos/temp_stream_classical")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_proc = None

        self.youtube = self._get_youtube_client()
        self.stream_id = None
        self.broadcast_id = None
        self.broadcast_title, self.broadcast_description = self._broadcast_copy()

    def _broadcast_copy(self) -> tuple[str, str]:
        """AI-generated title/description for the persistent broadcast,
        computed once per process start -- degrades to the hardcoded
        template when no AI provider key is configured or the call
        fails. Reuses generate_classical_video_copy() with a generic
        "the library" stand-in for track/artist, since the live has no
        single track to name -- the per-piece attribution instead lives
        in the description's own generic Jamendo/CC-BY credit line."""
        ai_copy = generate_classical_video_copy(
            mood="24/7 Live",
            duration_s=0.0,
            track_name="a rotating library of real classical recordings",
            artist_name="various licensed performers",
            fallback_title=_FALLBACK_BROADCAST_TITLE,
        )
        if ai_copy:
            description = (
                f"{ai_copy['description']}\n\n"
                "Music sourced from Jamendo under Creative Commons Attribution (CC BY) licenses; "
                "individual track/performer credit for each piece is included in that piece's own "
                "archived upload on this channel."
            )
            return ai_copy["title"], description
        return _FALLBACK_BROADCAST_TITLE, _FALLBACK_BROADCAST_DESCRIPTION

    def _get_youtube_client(self):
        token_file = ROOT / "youtube_token.json"
        info = load_token_info(token_file)
        if not info.present or not can_manage_comments(info.data):
            log.warning("No valid youtube token for broadcast management.")
            return None
        creds = credentials_from_token_info(info, ["https://www.googleapis.com/auth/youtube.force-ssl"])
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def _find_stream_id(self) -> str | None:
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
        if not self.youtube:
            return
        try:
            response = (
                self.youtube.liveBroadcasts()
                .list(part="snippet,status", broadcastStatus="all", broadcastType="all", maxResults=50)
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
                            "title": self.broadcast_title,
                            "description": self.broadcast_description,
                            "scheduledStartTime": datetime.now(timezone.utc).isoformat(),
                        },
                        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
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
                id=new_broadcast_id, part="id,contentDetails", streamId=stream_id
            ).execute()
            self.broadcast_id = new_broadcast_id
            log.info(
                f"Created and bound new broadcast {new_broadcast_id}. It will auto-go-live once video data arrives."
            )
            self._set_thumbnail(new_broadcast_id)
        except Exception as e:
            log.error(f"Failed to create/bind a new broadcast: {e}")

    def _set_thumbnail(self, video_id: str) -> None:
        """Best-effort: a failure here never blocks the broadcast itself
        from going live. Uses the same committed real-frame thumbnail
        the long-form generator uses -- one fixed clip, one fixed
        thumbnail, no per-run extraction needed."""
        if not THUMBNAIL_IMAGE.exists():
            return
        try:
            media = MediaFileUpload(str(THUMBNAIL_IMAGE), mimetype="image/jpeg")
            self.youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
        except Exception as e:
            log.warning(f"Failed to set live broadcast thumbnail: {e}")

    def _rebrand_if_stale(self, broadcast_item: dict) -> None:
        """Same staleness contract as scripts/live_stream_dynamic.py's
        identical method -- only known-legacy strings (or a blank title)
        get overwritten; anything else (including a previous run's own
        AI-generated title) is left alone."""
        snippet = broadcast_item.get("snippet") or {}
        current_title = snippet.get("title") or ""
        if current_title and current_title not in _LEGACY_BROADCAST_TITLES:
            return
        try:
            self.youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": broadcast_item.get("id"),
                    "snippet": {
                        "title": self.broadcast_title,
                        "description": self.broadcast_description,
                        "scheduledStartTime": snippet.get("scheduledStartTime")
                        or datetime.now(timezone.utc).isoformat(),
                    },
                },
            ).execute()
            log.info("Rebranded stale broadcast %s to current classical title.", broadcast_item.get("id"))
        except Exception as e:
            log.warning(f"Failed to rebrand stale broadcast: {e}")

    def _prepare_seamless_loop_clip(self, clip_path: Path) -> Path:
        """Same crossfade-bake technique as scripts/live_stream_dynamic.py's
        identical method -- see that file for the full concat-order
        reasoning."""
        out_path = self.temp_dir / f"seamless_{clip_path.stem}.mp4"
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path

        duration = _media_duration_s(clip_path)
        fade = min(LOOP_CROSSFADE_S, duration / 6) if duration > 3 else 0.0
        if fade <= 0:
            return clip_path

        filter_complex = (
            f"[0:v]trim=0:{fade:.3f},setpts=PTS-STARTPTS[start];"
            f"[0:v]trim={duration - fade:.3f}:{duration:.3f},setpts=PTS-STARTPTS[end];"
            f"[0:v]trim={fade:.3f}:{duration - fade:.3f},setpts=PTS-STARTPTS[mid];"
            f"[end][start]xfade=transition=fade:duration={fade:.3f}:offset=0[blend];"
            "[mid][blend]concat=n=2:v=1:a=0[out]"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(clip_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-an",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            str(out_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception as exc:
            log.warning("Failed to bake seamless loop clip, streaming raw clip instead: %s", exc)
            return clip_path
        if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            log.warning("ffmpeg seamless-loop bake failed, streaming raw clip instead: %s", result.stderr[-500:])
            return clip_path
        log.info("Baked seamless loop clip from %s (crossfade=%.2fs).", clip_path.name, fade)
        return out_path

    def _build_playlist(self) -> Path | None:
        """Concatenate every locally synced classical track into one
        playlist file, shuffled once per process start -- the relay then
        loops that whole file via -stream_loop -1, same technique the
        old (now-removed) lofi live pillar used for its bgm playlist.
        Rebuilding per restart (not cached across restarts the way the
        video bake is) means a crash/restart also picks up any tracks
        the sync step added since the last restart."""
        tracks = list(CLASSICAL_DIR.glob("jamendo_*.mp3"))
        if not tracks:
            return None
        random.shuffle(tracks)
        list_path = self.temp_dir / "classical_playlist_concat.txt"
        list_path.write_text(
            "\n".join(f"file '{track.resolve()}'" for track in tracks) + "\n",
            encoding="utf-8",
        )
        playlist_path = self.temp_dir / "classical_playlist.mp3"
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(playlist_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except Exception as exc:
            log.error(f"Failed to build classical playlist: {exc}")
            return None
        if result.returncode != 0 or not playlist_path.exists():
            log.error(f"ffmpeg playlist concat exited {result.returncode}: {result.stderr[-500:]}")
            return None
        log.info("Built classical playlist from %d track(s).", len(tracks))
        return playlist_path

    def build_stream_command(self) -> list[str] | None:
        if not PINNED_BROLL_CLIP.exists():
            log.error("Pinned classical clip missing at %s.", PINNED_BROLL_CLIP)
            return None
        playlist_path = self._build_playlist()
        if playlist_path is None:
            log.error("No classical tracks synced yet in %s -- nothing to stream.", CLASSICAL_DIR)
            return None

        video_input = self._prepare_seamless_loop_clip(PINNED_BROLL_CLIP)
        video_filter = (
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},fps={TARGET_FPS},"
            f"zoompan=z='min(zoom+0.0003,1.06)':d=1:s={TARGET_W}x{TARGET_H}:fps={TARGET_FPS},"
            "setsar=1,format=yuv420p"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-re",
            "-stream_loop",
            "-1",
            "-i",
            str(video_input),
            "-re",
            "-stream_loop",
            "-1",
            "-i",
            str(playlist_path),
            "-map",
            "0:v",
            "-map",
            "1:a",
        ]

        if self.stream_key == "test":
            output = ["-f", "flv", "test_output_classical.flv"]
        else:
            output = ["-f", "flv", f"rtmp://a.rtmp.youtube.com/live2/{self.stream_key}"]

        cmd += [
            "-vf",
            video_filter,
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
            "6000k",
            "-maxrate",
            "6000k",
            "-bufsize",
            "12000k",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "44100",
        ] + output
        return cmd

    def broadcast_monitor_thread(self):
        log.info("Starting Broadcast Monitor Thread...")
        while True:
            try:
                self.ensure_live_broadcast()
            except Exception as e:
                log.error(f"Broadcast monitor error: {e}")
            time.sleep(120)

    def run(self):
        if not PINNED_BROLL_CLIP.exists():
            log.error("No pinned classical clip found at %s.", PINNED_BROLL_CLIP)
            return
        if not list(CLASSICAL_DIR.glob("jamendo_*.mp3")):
            log.error(
                "No classical tracks synced yet in %s -- run scripts/sync_classical_music.py first.", CLASSICAL_DIR
            )
            return

        self.ensure_live_broadcast()
        threading.Thread(target=self.broadcast_monitor_thread, daemon=True).start()

        try:
            while True:
                cmd = self.build_stream_command()
                if not cmd:
                    time.sleep(10)
                    continue
                log.info("Starting classical stream ffmpeg process...")
                self.ffmpeg_proc = subprocess.Popen(cmd)
                self.ffmpeg_proc.wait()
                log.error("Classical stream ffmpeg process exited (code %s); restarting.", self.ffmpeg_proc.returncode)
                time.sleep(5)
        except KeyboardInterrupt:
            log.info("Stopping classical stream...")
            if self.ffmpeg_proc:
                self.ffmpeg_proc.terminate()
                self.ffmpeg_proc.wait()


def main():
    # Deliberately its OWN stream key, not a fallback to YOUTUBE_STREAM_KEY
    # (the rain pillar's live key): reusing that key would mean both
    # relays fight over the same RTMP ingestion point the moment both are
    # ever enabled together, breaking whichever one starts second. YouTube
    # supports multiple independent persistent live streams per channel
    # (create a second one in YouTube Studio -> Go Live -> Stream), so
    # this needs its own real secret once the owner is ready to actually
    # go live with this pillar -- see this repo's SETUP.md for the step.
    stream_key = os.environ.get("YOUTUBE_STREAM_KEY_CLASSICAL")
    if not stream_key:
        log.warning("No YOUTUBE_STREAM_KEY_CLASSICAL found. Running in local test mode.")
        stream_key = "test"

    streamer = ClassicalStreamer(stream_key)
    streamer.run()


if __name__ == "__main__":
    main()
