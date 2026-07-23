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


def _load_video_metadata(video: Path) -> dict:
    meta_path = video.with_suffix(".json")
    if not meta_path.exists():
        return {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _cuteness_score(video: Path) -> int:
    """Score heurístico: preferir clips com likes/views altos e palavras fofas."""
    meta = _load_video_metadata(video)
    tags = str(meta.get("tags", "")).lower()
    likes = int(meta.get("likes", 0) or 0)
    views = int(meta.get("views", 0) or 0)
    cute_bonus = sum(10 for kw in ("kitten", "puppy", "adorable", "cute", "sleepy", "baby") if kw in tags)
    # views e likes contribuem com pesos menores para nao dominar completamente.
    return cute_bonus + (likes // 20) + (views // 1000)


def pick_videos(min_count: int = 1, max_count: int = 5, cuteness_sort: bool = True) -> list[Path]:
    pool = video_pool()
    if not pool:
        return []
    count = random.randint(min_count, min(max_count, len(pool)))
    if cuteness_sort and len(pool) > count:
        # Pega os top clips fofos, mas embaralha para nao repetir sempre os mesmos.
        scored = sorted(pool, key=_cuteness_score, reverse=True)
        top = scored[: max(count * 3, len(pool) // 2)]
        return random.sample(top, count)
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
