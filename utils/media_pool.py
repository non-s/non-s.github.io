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
from utils.media_usage import filter_unused

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
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.debug("Metadata de video %s corrompida: %s", meta_path, exc)
        return {}


MOOD_GENRES: dict[str, list[str]] = {
    "fofura": ["bossa nova", "lounge", "chill", "easy listening", "lofi", "jazzhop"],
    "relax": ["smooth jazz", "ambient", "calm", "meditation", "lofi"],
    "diversao": ["swing", "bebop", "fusion", "upbeat"],
}


def _load_audio_metadata(audio: Path) -> dict:
    meta_path = audio.with_suffix(".json")
    if not meta_path.exists():
        return {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.debug("Metadata de audio %s corrompida: %s", meta_path, exc)
        return {}


def music_attribution(audio: Path) -> str:
    """Monta um crédito público e legível para a faixa licenciada do Jamendo."""
    meta = _load_audio_metadata(audio)
    if not meta:
        return ""

    def clean(value: object) -> str:
        return " ".join(str(value or "").split())

    track = clean(meta.get("name"))
    artist = clean(meta.get("artist_name"))
    if not track and not artist:
        return ""

    credit = f"Music: {track or 'Untitled'}"
    if artist:
        credit += f" — {artist}"
    credit += " (via Jamendo)"

    license_url = clean(meta.get("license_ccurl") or meta.get("license_url"))
    source_url = clean(meta.get("shorturl") or meta.get("shareurl") or meta.get("url"))
    if license_url:
        return f"{credit}\nLicense: {license_url}"
    if source_url:
        return f"{credit}\nSource: {source_url}"
    return credit


def _audio_genres(meta: dict) -> list[str]:
    """Extrai generos da metadata do Jamendo (musicinfo.tags.genres + tags top-level)."""
    genres: list[str] = []
    musicinfo = meta.get("musicinfo") or {}
    if isinstance(musicinfo, dict):
        mtags = musicinfo.get("tags") or {}
        if isinstance(mtags, dict):
            g = mtags.get("genres") or []
            if isinstance(g, list):
                genres.extend(str(x).lower() for x in g)
    tags = meta.get("tags", "")
    if isinstance(tags, str):
        genres.extend(t.lower() for t in tags.split() if t)
    elif isinstance(tags, list):
        genres.extend(str(t).lower() for t in tags)
    return genres


def _filter_by_mood(pool: list[Path], mood: str, min_needed: int) -> list[Path]:
    """Restringe o pool de audio as faixas cuja metadata bate com o mood.
    Sem match, retorna vazio: uma faixa incompatível quebra a promessa emocional
    do vídeo mais do que pular uma execução até o próximo sync."""
    wanted = [g.lower() for g in MOOD_GENRES.get(mood, [])]
    if not wanted:
        return pool
    filtered = [p for p in pool if any(g in wanted for g in _audio_genres(_load_audio_metadata(p)))]
    return filtered


def _cuteness_score(video: Path) -> int:
    """Score heurístico: preferir clips com likes/views altos e palavras fofas."""
    meta = _load_video_metadata(video)
    tags = str(meta.get("tags", "")).lower()
    likes = int(meta.get("likes", 0) or 0)
    views = int(meta.get("views", 0) or 0)
    cute_bonus = sum(10 for kw in ("kitten", "puppy", "adorable", "cute", "sleepy", "baby") if kw in tags)
    # views e likes contribuem com pesos menores para nao dominar completamente.
    return cute_bonus + (likes // 20) + (views // 1000)


_CAT_KEYWORDS = ("cat", "kitten")
_DOG_KEYWORDS = ("dog", "puppy")


def _filter_by_animal(pool: list[Path], animal: str, min_needed: int) -> list[Path]:
    """Restringe o pool aos clipes cujo nome de arquivo bate com o animal
    pedido (nomes vem da query do Pixabay - ver scripts/sync_animal_broll.py
    _safe_name - entao "real_cat_00_xxxx.mp4" contem "cat", etc).

    Nunca retorna o animal oposto como fallback: se não há mídia suficiente,
    o gerador deve falhar e esperar a próxima sincronização, em vez de
    publicar um vídeo cuja promessa editorial não bate com a imagem.
    """
    keywords = _CAT_KEYWORDS if animal in ("cat", "kitten") else _DOG_KEYWORDS
    filtered = [p for p in pool if any(kw in p.name.lower() for kw in keywords)]
    return filtered


def pick_videos(
    min_count: int = 1,
    max_count: int = 5,
    cuteness_sort: bool = True,
    animal: str = "",
) -> list[Path]:
    # Regra editorial estrita: assets confirmados ou reservados nunca voltam
    # ao conjunto elegivel. Se o pool inedito acabar, o caller deve falhar e
    # sincronizar material novo, jamais cair em repeticao silenciosa.
    pool = filter_unused(video_pool(), "video")
    if not pool:
        return []
    if animal:
        pool = _filter_by_animal(pool, animal, min_count)
        if len(pool) < min_count:
            return []
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
    return chosen


def pick_audio(mood: str = "") -> Path | None:
    pool = filter_unused(audio_pool(), "audio")
    if not pool:
        return None
    if mood:
        pool = _filter_by_mood(pool, mood, min_needed=1)
        if not pool:
            return None
    chosen = random.choice(pool)
    return chosen


def available_audio_metadata() -> Iterator[dict]:
    for p in sorted(AUDIO_DIR.glob("*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                yield json.load(f)
        except Exception as exc:
            log.debug("Metadata de audio %s corrompida: %s", p, exc)
            continue


def ensure_dirs() -> None:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def pool_stats() -> dict:
    return {
        "videos": len(video_pool()),
        "audio": len(audio_pool()),
    }
