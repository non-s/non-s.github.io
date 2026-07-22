"""
scripts/sync_animal_broll.py — baixa clips de gatos e cachorros do Pixabay.

Apenas queries permitidas por utils.animal_branding.BROLL_QUERIES sao usadas.
O filtro local garante que o arquivo tenha palavras-chave de gato/cachorro.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.animal_branding import BROLL_QUERIES, is_allowed_animal_text
from utils.media_pool import VIDEO_DIR, ensure_dirs

log = logging.getLogger(__name__)

PIXABAY_API_URL = "https://pixabay.com/api/videos/"
MAX_PER_QUERY = 15
MAX_POOL_SIZE = 300


def _safe_name(query: str, idx: int, url: str, ext: str) -> str:
    base = re.sub(r"[^a-z0-9]", "_", query.lower())
    return f"{base}_{idx:02d}_{hash(url) % 10000:04d}.{ext}"


def _download_video(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception as exc:
        log.warning("Falha ao baixar %s: %s", url, exc)
        return False


def search_and_download(api_key: str, query: str, max_results: int = 5) -> int:
    headers = {"User-Agent": "PataJazz-Bot/1.0"}
    params = {
        "key": api_key,
        "q": query,
        "per_page": max(3, max_results * 2),
        "safesearch": "true",
        "orientation": "horizontal",
    }
    try:
        r = requests.get(PIXABAY_API_URL, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.error("Erro na busca Pixabay para '%s': %s", query, exc)
        return 0

    hits = data.get("hits", [])
    downloaded = 0
    for idx, hit in enumerate(hits):
        if downloaded >= max_results:
            break
        tags = hit.get("tags", "")
        user = hit.get("user", "")
        text_signal = f"{hit.get('pageURL', '')} {tags} {user}"
        if not is_allowed_animal_text(text_signal):
            log.info("Ignorando hit nao permitido: %s", tags)
            continue
        videos = hit.get("videos", {})
        video = videos.get("large") or videos.get("medium") or videos.get("small")
        if not video:
            continue
        url = video.get("url", "")
        ext = Path(urlparse(url).path).suffix.lstrip(".") or "mp4"
        dest = VIDEO_DIR / _safe_name(query, idx, url, ext)
        if dest.exists():
            continue
        if _download_video(url, dest):
            downloaded += 1
            log.info("Baixado %s", dest.name)
    return downloaded


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    api_key = os.environ.get("PIXABAY_API_KEY")
    if not api_key:
        log.error("PIXABAY_API_KEY nao configurada.")
        return 1

    ensure_dirs()
    existing = len(list(VIDEO_DIR.glob("*.mp4")))
    if existing >= MAX_POOL_SIZE:
        log.info("Pool ja esta cheio (%d clips).", existing)
        return 0

    total = 0
    for query in BROLL_QUERIES:
        if len(list(VIDEO_DIR.glob("*.mp4"))) >= MAX_POOL_SIZE:
            break
        total += search_and_download(api_key, query, MAX_PER_QUERY)

    log.info("Sync finalizado. Total de novos clips: %d", total)
    return 0 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
