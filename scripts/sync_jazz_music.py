"""
scripts/sync_jazz_music.py — baixa faixas de jazz do Jamendo.

Filtra por termos de busca permitidos em utils.animal_branding.JAMENDO_SEARCH_TERMS.
Baixa apenas musicas com licenca CC que permitam uso comercial (jamendo/no_client).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.animal_branding import JAMENDO_SEARCH_TERMS
from utils.log_config import configure_logging
from utils.media_pool import AUDIO_DIR, ensure_dirs

log = logging.getLogger(__name__)

JAMENDO_API_URL = "https://api.jamendo.com/v3.0/tracks"
MAX_PER_TERM = 2
MAX_POOL_SIZE = 40
# Fracao do pool evictada (as faixas mais antigas por mtime) quando o pool
# esta cheio, pra abrir espaco pra faixas novas a cada sync. Sem isso, uma
# vez que o pool atingia MAX_POOL_SIZE ele congelava para sempre - as
# mesmas 200 faixas eram reusadas indefinidamente, nunca "fresco" de fato.
_POOL_ROTATION_FRACTION = 0.1


def _evict_oldest(directory: Path, glob_pattern: str, count: int) -> int:
    """Remove os `count` arquivos mais antigos (por mtime) que casam com
    `glob_pattern`, junto com o .json de metadata correspondente, se houver.
    Retorna quantos foram removidos."""
    if count <= 0:
        return 0
    files = sorted(directory.glob(glob_pattern), key=lambda p: p.stat().st_mtime)
    evicted = 0
    for f in files[:count]:
        try:
            f.unlink(missing_ok=True)
            f.with_suffix(".json").unlink(missing_ok=True)
            evicted += 1
        except OSError as exc:
            log.warning("Falha ao remover %s do pool: %s", f.name, exc)
    return evicted


def _client_id() -> str:
    return os.environ.get("JAMENDO_CLIENT_ID", "")


def _music_descriptors() -> tuple[str, ...]:
    """Descritores permitidos para filtrar hits do Jamendo pelo gênero jazz."""
    return (
        "jazz", "bossa", "smooth", "bebop", "swing", "fusion", "lofi",
        "ambient", "piano", "acoustic", "classical",
    )


def _is_jazz(hit: dict) -> bool:
    text = " ".join(str(hit.get(k, "")) for k in ["name", "artist_name", "album_name", "tags", "musicinfo"]).lower()
    return any(descriptor in text for descriptor in _music_descriptors())


def _download(url: str, dest: Path) -> bool:
    # Faz download em streaming com retries. Isso evita IncompleteRead em arquivos grandes.
    # Timeout reduzido (45s) pois as previews Jamendo sao pequenas (mp32).
    for attempt in range(2):
        try:
            with requests.get(url, timeout=45, stream=True) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            f.write(chunk)
            return True
        except Exception as exc:
            log.warning("Falha ao baixar audio %s (tentativa %d/2): %s", url, attempt + 1, exc)
            if attempt < 1:
                import time

                time.sleep(2**attempt)
    return False


def search_and_download(term: str, max_results: int = 5, client_id: str = "") -> int:
    params: dict[str, str | int] = {
        "client_id": client_id,
        "search": term,
        "limit": max(10, max_results * 3),
        "include": "musicinfo",
        "audioformat": "mp32",
        "ccmixter": "no",
        # Filtra apenas musicas com licenca Creative Commons que permite
        # uso comercial (para o canal poder monetizar sem risco legal).
        "license_cc": "yes",
        "commercialuse": "yes",
        # Mesmo raciocinio do Pixabay (order=popular em sync_animal_broll.py):
        # sem ordenar, o Jamendo devolve em ordem essencialmente arbitraria -
        # faixas mais populares tendem a ter producao/mixagem melhor.
        "order": "popularity_total",
    }
    try:
        r = requests.get(JAMENDO_API_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.error("Erro na busca Jamendo para '%s': %s", term, exc)
        return 0

    hits = data.get("results", [])
    downloaded = 0
    for idx, hit in enumerate(hits):
        if downloaded >= max_results:
            break
        if not _is_jazz(hit):
            continue
        audio_url = hit.get("audio") or hit.get("audio_download")
        if not audio_url:
            continue
        name = re.sub(r"[^a-zA-Z0-9_\-]", "_", hit.get("name", "track"))[:40]
        dest = AUDIO_DIR / f"jamendo_{name}_{hit.get('id', idx)}.mp3"
        meta_dest = dest.with_suffix(".json")
        if dest.exists():
            continue
        if _download(audio_url, dest):
            try:
                hit["license_verified_for_youtube"] = True
                hit["license_url"] = hit.get("license_ccurl") or hit.get("license_url") or hit.get("shorturl")
                meta_dest.write_text(json.dumps(hit, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            downloaded += 1
            log.info("Baixado %s", dest.name)
    return downloaded


def main() -> int:
    configure_logging()
    client_id = _client_id()
    if not client_id:
        log.error("JAMENDO_CLIENT_ID nao configurada.")
        return 1

    ensure_dirs()
    existing = len(list(AUDIO_DIR.glob("*.mp3")))
    if existing >= MAX_POOL_SIZE:
        rotate_count = max(1, int(MAX_POOL_SIZE * _POOL_ROTATION_FRACTION))
        evicted = _evict_oldest(AUDIO_DIR, "*.mp3", rotate_count)
        log.info("Pool de audio cheio (%d faixas) - rotacionadas %d mais antigas para abrir espaco.", existing, evicted)

    total = 0
    current_count = len(list(AUDIO_DIR.glob("*.mp3")))
    search_terms = JAMENDO_SEARCH_TERMS
    log.info(
        "Sync de audio para Pata Jazz com %d termos de busca.",
        len(search_terms),
    )
    for term in search_terms:
        if current_count >= MAX_POOL_SIZE:
            log.info("Pool de audio atingiu o tamanho alvo (%d); parando sync.", MAX_POOL_SIZE)
            break
        # Nao baixamos mais do que o espaco disponivel no pool.
        remaining = MAX_POOL_SIZE - current_count
        to_download = min(MAX_PER_TERM, remaining)
        downloaded = search_and_download(term, to_download, client_id=client_id)
        total += downloaded
        current_count += downloaded

    log.info("Sync finalizado. Total de novas faixas: %d", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
