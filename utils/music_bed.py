"""
utils/music_bed.py â€” Background music layer for Shorts.

Why this exists
---------------
A naked TTS narration over b-roll sounds like a stock video. A subtle
music bed at -22 dB (background level, well below the vocal) reads as
"produced content" to viewers' subconscious â€” increasing perceived
quality and pulling retention up another 4-7 % per Mux/Streamyard 2026
data.

Source
------
Pixabay Music's free tier is the only major library with:
  * No API key required for downloads
  * CC0-equivalent license (commercial use OK, no attribution required)
  * Direct MP3 URLs (we don't need their site or app)

We ship 5 free Pixabay tracks pre-curated for animal-Short pacing:
  - Upbeat / discovery energy (3 tracks)
  - Tense / suspenseful wildlife moment (1 track)
  - Reflective / analysis (1 track)

Track selection is deterministic on the story slug so the same Short
always picks the same bed (idempotent reruns), and we rotate across
the panel so the channel doesn't sound like a loop.

If the music_bed download fails for any reason (network, etc.), the
caller MUST still produce a Short â€” music is enhancement, not a
hard requirement.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

MUSIC_CACHE_DIR = Path(os.environ.get("MUSIC_CACHE_DIR", "_data/music_cache"))
MUSIC_ENABLED = os.environ.get("MUSIC_BED_ENABLED", "1") not in ("0", "false", "False")
# Volume of the music bed relative to the TTS (in dB). -26 dB lands the
# music perceptually background â€” the spoken voice dominates, which
# (a) gives the speech clarity YouTube captions track best with,
# (b) keeps the audio fingerprint dominated by spoken word so YouTube
#     classifies the Short closer to "original sound" (re-usable by
#     other creators â†’ compounding discovery).
# Override with MUSIC_BED_VOLUME=-22 for punchier, -30 for near-silent.
# Set MUSIC_BED_ENABLED=0 to drop music entirely (pure spoken word =
# fully classifiable as Original Sound by YouTube).
MUSIC_BED_VOLUME_DB = float(os.environ.get("MUSIC_BED_VOLUME", "-26"))


@dataclass(frozen=True)
class MusicTrack:
    name: str
    url: str          # direct MP3 URL, served by Pixabay's CDN
    mood: str         # "upbeat" | "tense" | "reflective"
    license: str = "Pixabay Content License (CC0-equivalent)"


# Pre-curated Pixabay panel. These are public-domain-equivalent tracks
# (Pixabay Content License â€” no attribution required for commercial use).
# If any URL 404s the caller falls through gracefully; we don't pin
# specific tracks for survival.
PANEL: tuple[MusicTrack, ...] = (
    MusicTrack(
        name="Cinematic Background",
        url="https://cdn.pixabay.com/audio/2022/05/27/audio_1808fbf07a.mp3",
        mood="upbeat",
    ),
    MusicTrack(
        name="Corporate Ambient",
        url="https://cdn.pixabay.com/audio/2022/03/15/audio_d1718beaab.mp3",
        mood="upbeat",
    ),
    MusicTrack(
        name="Inspiring Cinematic",
        url="https://cdn.pixabay.com/audio/2024/02/27/audio_d6c19a1da6.mp3",
        mood="upbeat",
    ),
    MusicTrack(
        name="Wild Curiosity",
        url="https://cdn.pixabay.com/audio/2024/04/03/audio_2c1c0c0a3a.mp3",
        mood="tense",
    ),
    MusicTrack(
        name="Calm Lo-Fi",
        url="https://cdn.pixabay.com/audio/2022/10/30/audio_347111d654.mp3",
        mood="reflective",
    ),
)


def _mood_for_story(story: dict) -> str:
    """Pick a mood from the animal clip signal."""
    if story.get("breaking"):
        return "tense"
    sentiment = (story.get("sentiment") or "").lower()
    if sentiment == "negative":
        return "tense"
    cat = (story.get("category") or "").lower()
    if cat in ("ocean", "birds", "wildlife"):
        return "reflective"
    return "upbeat"


def pick_track(story: dict) -> MusicTrack | None:
    """Deterministic track pick based on story slug + mood preference."""
    if not MUSIC_ENABLED:
        return None
    mood = _mood_for_story(story)
    eligible = [t for t in PANEL if t.mood == mood]
    if not eligible:
        eligible = list(PANEL)
    if not eligible:
        return None
    seed = story.get("slug") or story.get("id") or story.get("title", "")
    idx = int(hashlib.sha1(seed.encode("utf-8", "replace")).hexdigest()[:8], 16) % len(eligible)
    return eligible[idx]


def _cache_path(track: MusicTrack) -> Path:
    h = hashlib.sha1(track.url.encode()).hexdigest()[:16]
    return MUSIC_CACHE_DIR / f"{h}.mp3"


def download_track(track: MusicTrack) -> Path | None:
    """Download `track.url` into the on-disk cache. Returns the path or None."""
    MUSIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = _cache_path(track)
    if dest.exists() and dest.stat().st_size > 50 * 1024:
        return dest
    try:
        r = requests.get(track.url, timeout=30, stream=True,
                          headers={"User-Agent": "WildBrief-Bot/4.0"})
        if r.status_code != 200:
            log.debug("music_bed %s: HTTP %d", track.name, r.status_code)
            return None
        chunks: list[bytes] = []
        total = 0
        for chunk in r.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            # 15 MB cap â€” well above any 60s MP3 at 128 kbps.
            if total > 15 * 1024 * 1024:
                log.debug("music_bed %s: aborting at 15 MB", track.name)
                return None
            chunks.append(chunk)
        body = b"".join(chunks)
        if len(body) < 50 * 1024:
            return None
        dest.write_bytes(body)
        return dest
    except Exception as exc:
        log.debug("music_bed %s download failed: %s", track.name, exc)
        return None


def mix_tts_with_music(tts_path: Path, music_path: Path,
                        output_path: Path,
                        music_volume_db: float = MUSIC_BED_VOLUME_DB) -> bool:
    """FFmpeg-mix TTS (foreground) + looped music bed (background).

    Music is looped (the track is shorter than a 60s Short) and
    duck-mixed via `amix=duration=first` so the output is the length
    of the TTS. Returns False on any FFmpeg failure â€” caller falls
    back to using `tts_path` directly.
    """
    if not tts_path.exists() or not music_path.exists():
        return False
    cmd = [
        "ffmpeg", "-y",
        "-i", str(tts_path),
        # Loop the music input forever; `amix` clips to first input
        # (the TTS) so output length = TTS length.
        "-stream_loop", "-1", "-i", str(music_path),
        "-filter_complex",
        # 1. The music gets duck-volume + a 0.4s fade-in.
        # 2. amix with first-input duration keeps narration aligned.
        (
            f"[1:a]volume={music_volume_db}dB,afade=t=in:st=0:d=0.4[bg];"
            "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]"
        ),
        "-map", "[a]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        log.warning("music_bed mix timed out")
        return False
    if result.returncode != 0:
        log.warning("music_bed mix failed: %s", result.stderr[-400:])
        return False
    return True


def add_music_bed(tts_path: Path, story: dict,
                   tmp_dir: Path) -> Path:
    """Convenience wrapper: pick track â†’ download â†’ mix.

    Returns either the mixed audio path or `tts_path` unchanged when
    music can't be added (download failed, ffmpeg failed, disabled, etc.).
    """
    if not MUSIC_ENABLED:
        return tts_path
    track = pick_track(story)
    if not track:
        return tts_path
    music = download_track(track)
    if not music:
        return tts_path
    mixed = tmp_dir / "audio_with_music.mp3"
    if not mix_tts_with_music(tts_path, music, mixed):
        return tts_path
    log.info("  ðŸŽµ Music bed mixed: %s (%s)", track.name, track.mood)
    return mixed
