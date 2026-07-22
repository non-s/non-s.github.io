"""
utils/media_pool.py — gerencia o pool local de b-roll (Pixabay) e musica (Jamendo).
"""

from __future__ import annotations

import json
import logging
import os
import random
from pathlib import Path
from typing import Iterator

from utils.animal_branding import is_allowed_animal_text

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "_assets" / "video" / "animal_broll"
AUDIO_DIR = ROOT / "_assets" / "audio" / "animal_jazz"


def video_pool() -> list[Path]:
    paths = sorted(VIDEO_DIR.glob("*.mp4"))
    allowed: list[Path] = []
    for p in paths:
        if is_allowed_animal_text(p.name):
            allowed.append(p)
    return allowed


def audio_pool() -> list[Path]:
    return sorted(AUDIO_DIR.glob("*.mp3"))


def pick_videos(min_count: int = 1, max_count: int = 5) -> list[Path]:
    pool = video_pool()
    if not pool:
        return []
    count = random.randint(min_count, min(max_count, len(pool)))
    return random.sample(pool, count)


def pick_audio() -> Path | None:
    pool = audio_pool()
    return random.choice(pool) if pool else None


def available_audio_metadata() -> Iterator[dict]:
    for p in sorted(AUDIO_DIR.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                yield json.load(f)
        except Exception:
            continue


def ensure_dirs() -> None:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def pool_stats() -> dict:
    return {
        "videos": len(video_pool()),
        "audio": len(audio_pool()),
    }
