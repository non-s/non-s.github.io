"""
Autonomous background music layer for Shorts.

Internet Archive is the only source used here. Discovery is restricted
to audio items whose metadata explicitly indicates public-domain or CC0
evidence, and downloads go through utils.internet_archive.

Music is an enhancement, not a hard dependency: if discovery, download,
or FFmpeg mixing fails, the caller still produces the Short with the
original narration.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from utils.internet_archive import ArchiveAudioAsset, discover_public_domain_audio, download_asset

log = logging.getLogger(__name__)

MUSIC_CACHE_DIR = Path(os.environ.get("MUSIC_CACHE_DIR", "_data/music_cache"))
MUSIC_ENABLED = os.environ.get("MUSIC_BED_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
ARCHIVE_AUDIO_ENABLED = os.environ.get("ARCHIVE_AUDIO_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
ARCHIVE_AUDIO_ROWS = int(os.environ.get("ARCHIVE_AUDIO_ROWS", "12"))
# Volume of the music bed relative to the TTS. -26 dB keeps the narrator
# dominant while adding enough ambience to avoid a bare voice-over.
MUSIC_BED_VOLUME_DB = float(os.environ.get("MUSIC_BED_VOLUME", "-26"))


@dataclass(frozen=True)
class MusicTrack:
    name: str
    url: str
    mood: str
    license: str = "Internet Archive public-domain/CC0 item"
    source: str = "Internet Archive"
    source_url: str = ""
    license_evidence: str = ""


def _normalise_manifest_mood(value: str) -> str:
    mood = (value or "").strip().lower()
    if mood in {"suspense", "tense", "danger"}:
        return "tense"
    if mood in {"calm", "reflective", "analysis"}:
        return "reflective"
    if mood in {"discovery", "wonder", "upbeat", "curious"}:
        return "upbeat"
    return mood or "upbeat"


def _mood_for_story(story: dict) -> str:
    """Pick a music mood from the story signal."""
    if story.get("breaking"):
        return "tense"
    sentiment = (story.get("sentiment") or "").lower()
    if sentiment == "negative":
        return "tense"
    cat = (story.get("category") or "").lower()
    if cat in ("ocean", "birds", "wildlife"):
        return "reflective"
    return "upbeat"


def _archive_query_for_story(story: dict) -> str:
    cat = (story.get("category") or "").lower()
    if cat in {"ocean", "rivers"}:
        return "collection:audio_music AND (ambient OR nature OR ocean OR water OR instrumental)"
    if cat in {"birds", "forests", "wildlife"}:
        return "collection:audio_music AND (nature OR birds OR forest OR ambient OR instrumental)"
    if cat in {"nocturnal", "reptiles", "insects"}:
        return "collection:audio_music AND (suspense OR drone OR ambient OR nature OR instrumental)"
    return "collection:audio_music AND (ambient OR background OR nature OR instrumental)"


def track_from_archive_asset(asset: ArchiveAudioAsset) -> MusicTrack:
    return MusicTrack(
        name=asset.title,
        url=asset.url,
        mood=_normalise_manifest_mood(asset.mood),
        license=asset.license or "Internet Archive public-domain/CC0 item",
        source="Internet Archive",
        source_url=asset.source_url,
        license_evidence=asset.license_evidence,
    )


def _archive_track_score(track: MusicTrack, story: dict) -> int:
    text = " ".join(
        [
            track.name,
            track.url,
            track.source_url,
            story.get("category", ""),
            story.get("title", ""),
        ]
    ).lower()
    score = 50
    for term in (
        "nature",
        "rain",
        "water",
        "ocean",
        "forest",
        "bird",
        "ambient",
        "ambience",
        "instrumental",
        "sound",
        "animal",
        "wildlife",
    ):
        if term in text:
            score += 8
    for term in (
        "librivox",
        "speech",
        "sermon",
        "lecture",
        "audiobook",
        "reading",
        "quran",
        "dracula",
        "bull of heaven",
        "of course, the personality is gone",
    ):
        if term in text:
            score -= 30
    if track.mood == _mood_for_story(story):
        score += 12
    if "publicdomain" in track.license_evidence or "creativecommons.org/publicdomain" in track.license_evidence:
        score += 10
    return score


def archive_tracks_for_story(story: dict, *, rows: int | None = None) -> list[MusicTrack]:
    """Discover public-domain Archive audio as music-bed material."""
    if not ARCHIVE_AUDIO_ENABLED:
        return []
    mood = _mood_for_story(story)
    assets = discover_public_domain_audio(_archive_query_for_story(story), mood=mood, rows=rows or ARCHIVE_AUDIO_ROWS)
    tracks = [track_from_archive_asset(asset) for asset in assets]
    return sorted(tracks, key=lambda track: _archive_track_score(track, story), reverse=True)


def pick_track(story: dict) -> MusicTrack | None:
    """Pick the best safe Internet Archive track for the story."""
    if not MUSIC_ENABLED:
        return None
    mood = _mood_for_story(story)
    archive_tracks = archive_tracks_for_story(story)
    archive_eligible = [t for t in archive_tracks if t.mood == mood]
    eligible = archive_eligible or archive_tracks
    if not eligible:
        return None
    return eligible[0]


def _cache_path(track: MusicTrack) -> Path:
    h = hashlib.sha256(track.url.encode()).hexdigest()[:16]
    return MUSIC_CACHE_DIR / f"{h}.mp3"


def download_track(track: MusicTrack) -> Path | None:
    """Download an Internet Archive track into its Archive cache."""
    if track.source != "Internet Archive" or not track.url:
        return None
    asset = ArchiveAudioAsset(
        identifier=track.source_url.rstrip("/").split("/")[-1] if track.source_url else track.name,
        file_name=Path(track.url).name,
        title=track.name,
        creator="",
        url=track.url,
        source_url=track.source_url,
        license=track.license,
        license_evidence=track.license_evidence,
        mood=track.mood,
    )
    return download_asset(asset)


def mix_tts_with_music(
    tts_path: Path, music_path: Path, output_path: Path, music_volume_db: float = MUSIC_BED_VOLUME_DB
) -> bool:
    """FFmpeg-mix TTS foreground with looped background music."""
    if not tts_path.exists() or not music_path.exists():
        return False
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(tts_path),
        "-stream_loop",
        "-1",
        "-i",
        str(music_path),
        "-filter_complex",
        (
            f"[1:a]volume={music_volume_db}dB,afade=t=in:st=0:d=0.4[bg];"
            "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]"
        ),
        "-map",
        "[a]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
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


def add_music_bed(tts_path: Path, story: dict, tmp_dir: Path) -> Path:
    """Pick, download, and mix an autonomous Archive music bed."""
    if not MUSIC_ENABLED:
        return tts_path
    track = pick_track(story)
    if not track:
        log.info("  Music bed skipped: no safe Internet Archive audio candidate")
        return tts_path
    music = download_track(track)
    if not music:
        log.info("  Music bed skipped: Internet Archive download failed for %s", track.name)
        return tts_path
    mixed = tmp_dir / "audio_with_music.mp3"
    if not mix_tts_with_music(tts_path, music, mixed):
        return tts_path
    log.info("  Music bed mixed: %s (%s)", track.name, track.mood)
    story["music_bed_track"] = {
        "name": track.name,
        "mood": track.mood,
        "license": track.license,
        "source": track.source,
        "source_url": track.source_url,
        "license_evidence": track.license_evidence,
    }
    return mixed
