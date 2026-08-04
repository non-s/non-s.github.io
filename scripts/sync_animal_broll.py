"""
scripts/sync_animal_broll.py — baixa clips de gatos e cachorros do Pixabay.

Apenas queries permitidas por utils.animal_branding.BROLL_QUERIES sao usadas.
O filtro local garante que o arquivo tenha palavras-chave de gato/cachorro.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.animal_branding import BROLL_QUERIES, is_allowed_animal_text
from utils.log_config import configure_logging
from utils.media_pool import VIDEO_DIR, ensure_dirs

log = logging.getLogger(__name__)

PIXABAY_API_URL = "https://pixabay.com/api/videos/"
MAX_PER_QUERY = 3
MAX_POOL_SIZE = 80
MIN_WIDTH = 640
MIN_HEIGHT = 360
# Fracao do pool evictada (os clips mais antigos por mtime) quando o pool
# esta cheio, pra abrir espaco pra clips novos a cada sync. Sem isso, uma
# vez que o pool atingia MAX_POOL_SIZE ele congelava para sempre - os
# mesmos 300 clips eram reusados indefinidamente, nunca "fresco" de fato.
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


def _safe_name(query: str, idx: int, url: str, ext: str) -> str:
    base = re.sub(r"[^a-z0-9]", "_", query.lower())
    # usedforsecurity=False: so gera um sufixo curto pra nome de arquivo
    # (evitar colisao), nao ha nada criptografico ou sensivel aqui.
    url_hash = hashlib.sha1(url.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
    return f"{base}_{idx:02d}_{url_hash}.{ext}"


def _download_video(url: str, dest: Path) -> bool:
    try:
        with requests.get(url, timeout=120, stream=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as exc:
        log.warning("Falha ao baixar %s: %s", url, exc)
        return False


def search_and_download(api_key: str, query: str, max_results: int = 5, orientation: str = "vertical") -> int:
    headers = {"User-Agent": "PataJazz-Bot/1.0"}
    params: dict[str, str | int] = {
        "key": api_key,
        "q": query,
        "per_page": max(6, max_results * 3),
        "safesearch": "true",
        "orientation": orientation,
        "video_type": "film",  # exclui animacao/cartoon — so video real
        "order": "popular",  # prioriza os clips mais apreciados (geralmente mais fofos)
    }
    try:
        r = requests.get(PIXABAY_API_URL, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.error("Erro na busca Pixabay para '%s': %s", query, exc)
        return 0

    hits = data.get("hits", [])
    # Ordena por "likes" (desc) para favorecer os clips mais fofos/populares.
    hits = sorted(hits, key=lambda h: int(h.get("likes", 0) or 0), reverse=True)

    downloaded = 0
    for idx, hit in enumerate(hits):
        if downloaded >= max_results:
            break
        tags = hit.get("tags", "")
        user = hit.get("user", "")
        page_url = hit.get("pageURL", "")
        text_signal = f"{page_url} {tags} {user}"
        if not is_allowed_animal_text(text_signal):
            log.info("Ignorando hit nao permitido (filtro de texto): %s", tags)
            continue
        # Filtro extra: verifica o campo type do video (film = real, animation = cartoon)
        videos = hit.get("videos", {})
        video = videos.get("large") or videos.get("medium") or videos.get("small")
        if not video:
            continue
        # Rejeita clips abaixo da resolucao minima - qualidade baixa demais pra
        # thumbnail/frame extraction e pra encher a tela no Short vertical.
        # Compara por lado maior/menor (nao w/h direto): um clipe vertical
        # legitimo (ex.: 480x854) tem width < MIN_WIDTH mas e uma resolucao
        # perfeitamente boa - so esta orientado diferente. Campos ausentes
        # (API mudou ou hit incompleto) nao bloqueiam o clip - so pula a
        # checagem em vez de descartar por falta de dado.
        w, h = video.get("width"), video.get("height")
        if w and h:
            long_side, short_side = max(int(w), int(h)), min(int(w), int(h))
            if long_side < MIN_WIDTH or short_side < MIN_HEIGHT:
                log.info("Ignorando hit de baixa resolucao (%sx%s): %s", w, h, tags)
                continue
        # Rejeita explicitamente videos marcados como animacao
        video_type = str(hit.get("type", "")).lower()
        if video_type and "animat" in video_type:
            log.info("Ignorando hit de animacao (type=%s): %s", video_type, tags)
            continue
        # Prefere clips que parecam "fofinhos" pelas tags (kitten/puppy/cute/sleepy).
        lower_tags = tags.lower()
        is_extra_cute = any(kw in lower_tags for kw in ("kitten", "puppy", "cute", "sleepy", "adorable", "baby"))
        url = video.get("url", "")
        raw_ext = Path(urlparse(url).path).suffix.lstrip(".").lower() or "mp4"
        # Valida extensao contra whitelist para evitar path traversal / formatos inesperados.
        if raw_ext not in ("mp4", "webm", "mov", "m4v"):
            raw_ext = "mp4"
        ext = raw_ext
        dest = VIDEO_DIR / _safe_name(query, idx, url, ext)
        if dest.exists():
            continue
        if _download_video(url, dest):
            try:
                # Salva metadados Pixabay para futura triagem por popularidade.
                meta_dest = dest.with_suffix(".json")
                meta_dest.write_text(json.dumps(hit, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            downloaded += 1
            log.info("Baixado %s (likes=%s, cute=%s)", dest.name, hit.get("likes"), is_extra_cute)
    return downloaded


def main() -> int:
    configure_logging()
    api_key = os.environ.get("PIXABAY_API_KEY")
    if not api_key:
        log.error("PIXABAY_API_KEY nao configurada.")
        return 1

    ensure_dirs()
    existing = len(list(VIDEO_DIR.glob("*.mp4")))
    if existing >= MAX_POOL_SIZE:
        rotate_count = max(1, int(MAX_POOL_SIZE * _POOL_ROTATION_FRACTION))
        evicted = _evict_oldest(VIDEO_DIR, "*.mp4", rotate_count)
        log.info("Pool cheio (%d clips) - rotacionados %d mais antigos para abrir espaco.", existing, evicted)

    total = 0
    current_count = len(list(VIDEO_DIR.glob("*.mp4")))
    # Prioriza queries mais fofas primeiro.
    prioritized_queries = sorted(
        BROLL_QUERIES,
        key=lambda q: (0 if any(kw in q for kw in ("kitten", "puppy", "adorable", "cute")) else 1, q),
    )
    start_time = time.time()
    max_sync_seconds = 300  # 5 minutos: sync nao pode dominar o CI
    for i, query in enumerate(prioritized_queries):
        if current_count >= MAX_POOL_SIZE:
            log.info("Pool atingiu %d clips; parando sync.", MAX_POOL_SIZE)
            break
        # Canal e 100% Shorts verticais - crop_filter em video_builder.short_spec
        # ("crop='ih*9/16:ih:...'") e essencialmente um no-op num clipe ja
        # vertical, mas descarta ~68% da largura de um clipe horizontal 16:9
        # (corta pra so ih*9/16 de largura) - risco real de cortar o
        # bichinho fora do quadro. Pixabay tem menos oferta vertical de pets
        # que horizontal, entao 2 a cada 3 queries buscam vertical e 1 busca
        # horizontal, mantendo o pool crescendo mesmo quando um termo
        # especifico nao tem vertical suficiente.
        orientation = "horizontal" if i % 3 == 2 else "vertical"
        remaining = MAX_POOL_SIZE - current_count
        to_download = min(MAX_PER_QUERY, remaining)
        downloaded = search_and_download(api_key, query, to_download, orientation=orientation)
        total += downloaded
        current_count += downloaded
        if time.time() - start_time > max_sync_seconds:
            log.info("Timeout de sync b-roll atingido (%ds); parando.", max_sync_seconds)
            break

    log.info("Sync finalizado. Total de novos clips: %d", total)
    return 0 if total >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
