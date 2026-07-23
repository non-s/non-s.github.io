"""
scripts/sync_jazz_music.py — baixa faixas jazz do Jamendo.

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
from utils.media_pool import AUDIO_DIR, ensure_dirs

log = logging.getLogger(__name__)

JAMENDO_API_URL = "https://api.jamendo.com/v3.0/tracks"
CLIENT_ID = os.environ.get("JAMENDO_CLIENT_ID", "")
MAX_PER_TERM = 25
MAX_POOL_SIZE = 150


def _is_jazz(hit: dict) -> bool:
    text = " ".join(
        str(hit.get(k, "")) for k in ["name", "artist_name", "album_name", "tags", "musicinfo"]
    ).lower()
    return "jazz" in text or "bossa" in text or "smooth" in text


def _download(url: str, dest: Path) -> bool:
    # Faz download em streaming com retries. Isso evita IncompleteRead em arquivos grandes.
    for attempt in range(3):
        try:
            with requests.get(url, timeout=120, stream=True) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            f.write(chunk)
            return True
        except Exception as exc:
            log.warning("Falha ao baixar audio %s (tentativa %d/3): %s", url, attempt + 1, exc)
            if attempt < 2:
                import time

                time.sleep(2 ** attempt)
    return False


def search_and_download(term: str, max_results: int = 5) -> int:
    params = {
        "client_id": CLIENT_ID,
        "search": term,
        "limit": max(10, max_results * 3),
        "include": "musicinfo",
        "audioformat": "mp32",
        "ccmixter": "no",
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
                meta_dest.write_text(json.dumps(hit, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            downloaded += 1
            log.info("Baixado %s", dest.name)
    return downloaded


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not CLIENT_ID:
        log.error("JAMENDO_CLIENT_ID nao configurada.")
        return 1

    ensure_dirs()
    existing = len(list(AUDIO_DIR.glob("*.mp3")))
    if existing >= MAX_POOL_SIZE:
        log.info("Pool de audio ja esta cheio (%d faixas).", existing)
        return 0

    total = 0
    for term in JAMENDO_SEARCH_TERMS:
        if len(list(AUDIO_DIR.glob("*.mp3"))) >= MAX_POOL_SIZE:
            break
        total += search_and_download(term, MAX_PER_TERM)

    log.info("Sync finalizado. Total de novas faixas: %d", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
