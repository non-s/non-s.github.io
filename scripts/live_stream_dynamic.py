#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_stream_dynamic.py -- 24/7 rain & thunder live relay with self-healing
broadcast.

This channel's 24/7 live format isn't several different video clips cut
together -- it's one single looping animated storm scene with a
procedurally-synthesized rain/thunder bed (plus an optional quiet Jamendo
track) underneath, for hours. So this relay loops ONE fixed storm clip,
committed directly into the repo at _assets/video/pinned_storm_clip.mp4
(STORM_PINNED_BROLL_CLIP below) -- see utils/storm_branding.py's module
docstring for why this pillar (real "rain sounds for sleep"/"thunderstorm
ambience" search intent) is the channel's whole identity now.

A single ffmpeg process streams straight to RTMP with `-stream_loop -1` on
both the video clip and the audio inputs -- there is no bake-to-file step
sized to the stream's length, so a restart just relaunches ffmpeg against
the same (cached) inputs and is back on air within seconds. The video clip
is preprocessed once with a short crossfade baked between its tail and its
head, so looping it forever has no visible jump cut at the wrap-around
point.

A background thread keeps a public broadcast bound to the stream key at
all times -- ffmpeg can push RTMP data forever, but that alone never puts
the channel back on-air once a broadcast ends, so a new one has to be
created and bound whenever none is active.

This used to also run an AI "virtual host" that answered live chat
questions with synthesized speech cut into the stream. That feature has
been removed: this channel's format is deliberately narration-free (loop +
ambience only), and a spoken voice answering chat mid-loop would break
that format on every question asked.
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

# The 24/7 relay's one committed, seamless-loop storm scene -- same asset
# generate_storm_ambience.py/generate_storm_short.py fall back to when no
# real Pixabay clip is synced. See scripts/generate_storm_scene.py.
STORM_PINNED_BROLL_CLIP = ROOT / "_assets" / "video" / "pinned_storm_clip.mp4"

# Real 4K (chat, 2026-07-21: the channel owner explicitly asked for it
# across every format, including this live relay, accepting the OOM risk
# this reintroduces on a standard GitHub Actions runner -- see
# utils/broll.py's fetch_pixabay() comment for the full history/tradeoff).
TARGET_W = 3840
TARGET_H = 2160
TARGET_FPS = 30
LOOP_CROSSFADE_S = 1.0

BROADCAST_TITLE = "Chuva e Trovão — Amber Hours \U0001f327️ [24/7 AO VIVO]"
BROADCAST_DESCRIPTION = (
    "Ambiência real de chuva e trovão sem parar, ao vivo -- para ajudar você a dormir, focar ou "
    "relaxar. A chuva e o trovão são sintetizados por computador, não uma gravação em loop."
)

# Every literal value BROADCAST_TITLE has ever held before the current one --
# see _rebrand_if_stale()'s docstring for why this list (not "anything that
# doesn't match BROADCAST_TITLE") is the staleness check. Includes the
# channel's earlier "rainy-night anime lofi" identity (growth pass,
# 2026-07-21: the channel fully moved to the rain/thunder ambience pillar),
# so an already-live broadcast still carrying that title gets auto-corrected
# on its next check-in instead of being left alone forever.
_LEGACY_BROADCAST_TITLES = {
    "lofi hip hop radio \U0001f4da beats to relax/study to [24/7 LIVE]",
    "\U0001f534 24/7 Lofi Beats to Relax/Study to | Live",
    "\U0001f534 24/7 Wild Nature & Animal Secrets | Ao Vivo | En Vivo",
    "Rainy Night Anime Lofi — Amber Hours \U0001f319 [24/7 LIVE]",
    "Rain & Thunder — Amber Hours \U0001f327️ [24/7 LIVE]",
}


def _media_duration_s(path: Path) -> float:
    """ffprobe wrapper for either audio or video. Returns 0.0 (treat as
    unknown) rather than a guessed fallback duration -- callers that need
    a real duration (the loop-crossfade calc) skip the optional step
    they wanted it for instead of computing it against a made-up number."""
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


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
        """Fix an already-active broadcast's title/description only if
        they're empty or still carrying a known-legacy value.

        ensure_live_broadcast() only creates a NEW broadcast when none is
        active -- an already-live/ready/testing broadcast created under
        older branding would otherwise just keep reusing its stale title
        forever, even though the video/audio streaming through it is
        already rain/thunder. This used to treat ANY mismatch against the
        current BROADCAST_TITLE constant as "stale" and silently overwrite
        it -- which meant a channel owner retitling the live from YouTube
        Studio got reverted on the very next check-in cycle, with no way
        to make a manual edit stick. Only known-legacy strings (or a blank
        title) count as stale now; anything else is left alone.
        """
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
                        "title": BROADCAST_TITLE,
                        "description": BROADCAST_DESCRIPTION,
                        "scheduledStartTime": snippet.get("scheduledStartTime")
                        or datetime.now(timezone.utc).isoformat(),
                    },
                },
            ).execute()
            log.info("Rebranded stale broadcast %s to current rain & thunder title.", broadcast_item.get("id"))
        except Exception as e:
            log.warning(f"Failed to rebrand stale broadcast: {e}")

    def _pick_broll_clip(self) -> Path | None:
        return STORM_PINNED_BROLL_CLIP if STORM_PINNED_BROLL_CLIP.exists() else None

    def _build_storm_audio_inputs(self) -> tuple[Path, Path | None]:
        """Rain/thunder bed (always present) + an optional quiet bgm track
        underneath -- same design as generate_storm_ambience.py's
        MUSIC_LAYER_PROBABILITY, re-rolled on every relay restart."""
        from utils.storm_audio import generate_rain_bed, write_wav

        rain_bed_path = self.temp_dir / "storm_rain_bed.wav"
        if not (rain_bed_path.exists() and rain_bed_path.stat().st_size > 0):
            bed = generate_rain_bed(
                duration_s=75.0, seed=random.randint(0, 1_000_000), thunder_count=random.randint(1, 3)
            )
            write_wav(bed, rain_bed_path)

        music_path = None
        probability = float(os.environ.get("STORM_MUSIC_LAYER_PROBABILITY", "0.35"))
        if random.random() < probability:
            tracks = list(BGM_DIR.glob("jamendo_*.mp3"))
            if tracks:
                music_path = random.choice(tracks)
        return rain_bed_path, music_path

    def _prepare_seamless_loop_clip(self, clip_path: Path) -> Path:
        """Bake a short crossfade between the clip's tail and its head once,
        so repeating it forever via -stream_loop -1 has no visible hard cut
        at the wrap-around point.

        Standard ffmpeg loop-crossfade trick: split the clip into
        [start][mid][end], crossfade end->start into one "blend" segment,
        then output [blend][mid]. Looping that result plays
        mid -> blend -> mid -> blend forever -- the seam (originally the
        cut from the last frame back to the first) is now a smooth fade
        instead of a jump cut, and the fade only has to be computed once
        per clip since the output file is cached and reused across
        restarts.
        """
        out_path = self.temp_dir / f"seamless_{clip_path.stem}.mp4"
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path

        duration = _media_duration_s(clip_path)
        fade = min(LOOP_CROSSFADE_S, duration / 6) if duration > 3 else 0.0
        if fade <= 0:
            return clip_path

        # `mid` must be concat's FIRST input, `blend` its second -- see
        # generate_storm_ambience.py's identical function for the full
        # reasoning. With the original [blend][mid] order this deadlocks
        # ffmpeg's internal frame queue on longer/higher-fps clips (each
        # of `mid`'s frames backs up unread until concat reaches segment
        # 1, since `blend` can't emit anything until the demuxer reaches
        # the clip's tail).
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
            # xfade negotiates a higher-precision pixel format for the
            # blend by default (checked live: yuv444p), which then makes
            # the *next* ffmpeg stage's "-profile:v high" encode fail
            # outright ("high profile doesn't support 4:4:4") -- pin the
            # bake's output back to standard 4:2:0 so it's a drop-in
            # replacement for the raw clip.
            "-pix_fmt",
            "yuv420p",
            # Checked live: the default x264 "medium" preset re-encoding a
            # source clip through this filter graph used enough CPU/memory
            # on a standard GitHub Actions runner to get the whole job
            # killed (SIGTERM) partway through -- "veryfast" matches the
            # preset already used for the main streaming encode below.
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

    def build_stream_command(self) -> list[str] | None:
        """Build the ffmpeg command that streams straight to RTMP: one
        looped (seamlessly crossfaded) clip as video, the synthesized
        rain/thunder bed (plus an optional quiet music track) looped as
        audio -- no intermediate bake-to-file step. The video loop is a
        few seconds of work on a short clip, so a restart (crash, cooldown
        loop) starts producing stream output again within seconds instead
        of waiting through a fresh multi-hour re-encode.
        """
        clip_path = self._pick_broll_clip()
        if not clip_path:
            log.error("No storm b-roll clip found to loop.")
            return None
        video_input = self._prepare_seamless_loop_clip(clip_path)

        video_filter = (
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},fps={TARGET_FPS},"
            f"zoompan=z='min(zoom+0.0003,1.06)':d=1:s={TARGET_W}x{TARGET_H}:fps={TARGET_FPS},"
            # Belt-and-braces: -profile:v high below only supports 4:2:0,
            # so pin the format here regardless of what pixel format the
            # (possibly seamless-loop-baked) video input happens to carry.
            "setsar=1,format=yuv420p"
        )

        cmd = ["ffmpeg", "-y", "-re", "-stream_loop", "-1", "-i", str(video_input)]
        rain_bed_path, music_path = self._build_storm_audio_inputs()
        cmd += ["-re", "-stream_loop", "-1", "-i", str(rain_bed_path)]
        if music_path:
            cmd += ["-re", "-stream_loop", "-1", "-i", str(music_path)]
            filter_complex = (
                "[1:a]volume=1.0[rain];[2:a]volume=0.16[music];"
                "[rain][music]amix=inputs=2:duration=first:dropout_transition=0[a]"
            )
            cmd += ["-filter_complex", filter_complex, "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]

        if self.stream_key == "test":
            output = ["-f", "flv", "test_output.flv"]
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
            # YouTube's own recommended live-encoder bitrate for 4K/2160p at
            # 30fps is roughly 35-45 Mbps (their live encoder settings
            # guidance scales ~2x higher than the plain-upload VOD table for
            # the same resolution/framerate); 40000k sits in the middle of
            # that band. -bufsize at 2x -maxrate is the same ratio the prior
            # 1080p values used (9000k = 2x 4500k).
            "-b:v",
            "40000k",
            "-maxrate",
            "40000k",
            "-bufsize",
            "80000k",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "44100",
        ] + output
        return cmd

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

    def run(self):
        if not STORM_PINNED_BROLL_CLIP.exists():
            log.error("No storm b-roll clip found at %s.", STORM_PINNED_BROLL_CLIP)
            return

        # Make sure a broadcast exists and is bound *before* we start
        # pushing video, so YouTube has somewhere to auto-start it.
        self.ensure_live_broadcast()

        threading.Thread(target=self.broadcast_monitor_thread, daemon=True).start()

        try:
            while True:
                cmd = self.build_stream_command()
                if not cmd:
                    time.sleep(10)
                    continue
                log.info("Starting stream ffmpeg process...")
                self.ffmpeg_proc = subprocess.Popen(cmd)
                self.ffmpeg_proc.wait()
                log.error("Stream ffmpeg process exited (code %s); restarting.", self.ffmpeg_proc.returncode)
                time.sleep(5)  # Cooldown before reconnecting
        except KeyboardInterrupt:
            log.info("Stopping stream...")
            if self.ffmpeg_proc:
                self.ffmpeg_proc.terminate()
                self.ffmpeg_proc.wait()


def main():
    stream_key = os.environ.get("YOUTUBE_STREAM_KEY")
    if not stream_key:
        log.warning("No YOUTUBE_STREAM_KEY found. Running in local test mode (writing to test_output.flv).")
        stream_key = "test"

    streamer = DynamicStreamer(stream_key)
    streamer.run()


if __name__ == "__main__":
    main()
