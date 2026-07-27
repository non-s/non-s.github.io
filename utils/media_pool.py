"""
utils/media_pool.py — gerencia o pool local de b-roll (Pixabay) e musica (Jamendo).
"""

from __future__ import annotations

import json
import logging
import random
from collections.abc import Iterator
from pathlib import Path

from utils.animal_branding import is_allowed_animal_text

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "_assets" / "video" / "animal_broll"
AUDIO_DIR = ROOT / "_assets" / "audio" / "animal_jazz"

# Historico de itens usados recentemente, para nao repetir o mesmo clipe/faixa
# em sequencia quando o pool e pequeno. Persistido em _data/ (gitignored) para
# sobreviver entre runs do workflow (cache do GitHub Actions cobre esse path).
_RECENT_FILE = ROOT / "_data" / "recent_media.json"
_RECENT_VIDEO_WINDOW = 15
_RECENT_AUDIO_WINDOW = 8


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
        with open(meta_path, encoding="utf-8") as f:
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


def _load_recent() -> dict[str, list[str]]:
    try:
        return json.loads(_RECENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"videos": [], "audio": []}


def _remember_recent(kind: str, names: list[str], window: int) -> None:
    data = _load_recent()
    updated = (data.get(kind, []) + names)[-window:]
    data[kind] = updated
    try:
        _RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _RECENT_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception as exc:
        log.warning("Falha ao salvar historico de midia recente: %s", exc)


def _avoid_recent(pool: list[Path], kind: str, min_needed: int) -> list[Path]:
    """Remove itens usados recentemente do pool, a menos que isso deixe menos
    candidatos do que o necessario - nesse caso repetir e melhor que travar."""
    recent_names = set(_load_recent().get(kind, []))
    if not recent_names:
        return pool
    filtered = [p for p in pool if p.name not in recent_names]
    return filtered if len(filtered) >= min_needed else pool


def pick_videos(min_count: int = 1, max_count: int = 5, cuteness_sort: bool = True) -> list[Path]:
    pool = video_pool()
    if not pool:
        return []
    pool = _avoid_recent(pool, "videos", min_count)
    # Garante limites validos para randint: min_count <= upper, e upper <= len(pool).
    upper = min(max_count, len(pool))
    lower = min(min_count, upper)
    count = random.randint(lower, upper)
    if count > len(pool):
        count = len(pool)
    if cuteness_sort and len(pool) > count:
        # Pega os top clips fofos, mas embaralha para nao repetir sempre os mesmos.
        scored = sorted(pool, key=_cuteness_score, reverse=True)
        top = scored[: max(count * 3, len(pool) // 2)]
        chosen = random.sample(top, count)
    else:
        chosen = random.sample(pool, count)
    _remember_recent("videos", [p.name for p in chosen], _RECENT_VIDEO_WINDOW)
    return chosen


def pick_audio() -> Path | None:
    pool = audio_pool()
    if not pool:
        return None
    pool = _avoid_recent(pool, "audio", min_needed=1)
    chosen = random.choice(pool)
    _remember_recent("audio", [chosen.name], _RECENT_AUDIO_WINDOW)
    return chosen


def available_audio_metadata() -> Iterator[dict]:
    for p in sorted(AUDIO_DIR.glob("*.json")):
        try:
            with open(p, encoding="utf-8") as f:
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
