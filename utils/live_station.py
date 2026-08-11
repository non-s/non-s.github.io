"""Editorial programming for the Pata Jazz always-on visual radio.

This module plans a station; it never creates a YouTube broadcast or sends a
stream key anywhere. A plan reports licensing and diversity work still needed.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from utils.media_pool import _load_audio_metadata, _load_video_metadata
from utils.paths import data_dir

TARGET_TRACKS = 181
SESSION_TEMPLATES = (
    ("sunrise-companions", "morning"),
    ("focus-with-paws", "focus"),
    ("golden-hour-friends", "afternoon"),
    ("rainy-window-club", "rain"),
    ("after-dark-nest", "night"),
)


@dataclass(frozen=True)
class StationSegment:
    number: int
    session: str
    mood: str
    audio: str
    video: str
    music_credit: str
    visual_credit: str


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _audio_is_live_eligible(meta: dict) -> bool:
    """A provider name is not a licence; demand an explicit audit signal."""
    return bool(meta.get("license_verified_for_youtube")) and bool(_clean(meta.get("license_url")))


def _video_is_live_eligible(meta: dict) -> bool:
    return bool(_clean(meta.get("source_url"))) and bool(_clean(meta.get("license")))


def _credit_audio(path: Path, meta: dict) -> str:
    name = _clean(meta.get("name")) or path.stem
    artist = _clean(meta.get("artist_name"))
    return f"{name} — {artist}".rstrip(" —")


def _credit_video(path: Path, meta: dict) -> str:
    creator = _clean(meta.get("user")) or "Pixabay contributor"
    return f"{creator} — {_clean(meta.get('source_url'))}"


def build_station_plan(
    audio_files: list[Path], video_files: list[Path], *, target_tracks: int = TARGET_TRACKS
) -> dict[str, object]:
    """Build a diversified, deterministic rotation from verified local media."""
    if target_tracks < 1:
        raise ValueError("target_tracks must be at least 1")
    audio = [(p, _load_audio_metadata(p)) for p in sorted(audio_files)]
    video = [(p, _load_video_metadata(p)) for p in sorted(video_files)]
    approved_audio = [(p, meta) for p, meta in audio if _audio_is_live_eligible(meta)]
    approved_video = [(p, meta) for p, meta in video if _video_is_live_eligible(meta)]
    segments: list[StationSegment] = []
    if approved_audio and approved_video:
        for index in range(target_tracks):
            audio_path, audio_meta = approved_audio[index % len(approved_audio)]
            video_path, video_meta = approved_video[(index * 3) % len(approved_video)]
            session, mood = SESSION_TEMPLATES[index % len(SESSION_TEMPLATES)]
            segments.append(
                StationSegment(
                    index + 1,
                    session,
                    mood,
                    audio_path.name,
                    video_path.name,
                    _credit_audio(audio_path, audio_meta),
                    _credit_video(video_path, video_meta),
                )
            )
    return {
        "version": 1,
        "target_unique_tracks": target_tracks,
        "approved_unique_tracks": len(approved_audio),
        "approved_unique_clips": len(approved_video),
        "ready_for_broadcast": len(approved_audio) >= target_tracks and bool(approved_video),
        "requirements": {
            "additional_verified_tracks_needed": max(0, target_tracks - len(approved_audio)),
            "licensing_rule": "Every track needs explicit YouTube commercial-use verification and a licence URL.",
            "publication_rule": "A plan is not permission to create or start a YouTube live broadcast.",
        },
        "session_mix": dict(Counter(segment.session for segment in segments)),
        "segments": [asdict(segment) for segment in segments],
    }


def save_station_plan(plan: dict[str, object], output: Path | None = None) -> Path:
    output = output or data_dir() / "live_station_plan.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return output
