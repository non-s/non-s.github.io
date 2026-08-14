"""
utils/playlist_manager.py — cria e gerencia playlists do YouTube.

Playlists aumentam watch time e session duration. Cria playlists por mood
(relax, fofura, diversao) e adiciona videos automaticamente.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from utils.channel_config import active_channel
from utils.paths import data_dir
from utils.state_lock import state_lock
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

log = logging.getLogger(__name__)


def _cache_file() -> Path:
    """Caminho de playlist_cache.json no diretorio de dados do canal ativo."""
    return data_dir() / "playlist_cache.json"


# Cache de playlist IDs (criadas sob demanda). Persistido em _data/ para
# sobreviver entre runs do workflow e evitar re-buscar/recriar playlists.
_playlist_cache: dict[str, str] = {}


def _load_cache() -> None:
    """Carrega o cache de playlist IDs do disco, se existir."""
    global _playlist_cache
    cache_file = _cache_file()
    if cache_file.exists():
        try:
            _playlist_cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            log.debug("playlist_cache.json corrompido: %s", exc)
            _playlist_cache = {}


def _save_cache() -> None:
    """Persiste o cache de playlist IDs no disco."""
    cache_file = _cache_file()
    with state_lock(cache_file):
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(_playlist_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar cache de playlists: %s", exc)


def _find_or_create_playlist(service: Any, title: str) -> str:
    """Busca uma playlist pelo titulo ou cria nova. Retorna playlist ID."""
    if not _playlist_cache:
        _load_cache()
    if title in _playlist_cache:
        return _playlist_cache[title]

    # Busca playlists existentes (pagina todas, com guard contra loop
    # infinito - se a playlist buscada nunca for encontrada, o unico jeito
    # de sair do loop e o pageToken acabar; um guard por numero de paginas
    # evita depender so disso, igual ao mesmo padrao em collect_analytics.py).
    #
    # So cria nova playlist se a busca foi bem-sucedida E nao encontrou:
    # antes, um erro transitório de API (timeout, 503) caia no except e
    # criava uma playlist duplicada toda vez que falhava - gerando canais
    # com 5+ copias da mesma playlist "Liquid Wire | Shorts" e afins.
    found_pid: str | None = None
    try:
        page_token = ""
        pages = 0
        while pages < 20:
            pages += 1
            resp = _retry_youtube_call(
                service.playlists().list(part="id,snippet", mine=True, maxResults=50, pageToken=page_token).execute
            )
            for item in resp.get("items", []):
                if item.get("snippet", {}).get("title", "") == title:
                    found_pid = item["id"]
                    _playlist_cache[title] = found_pid
                    _save_cache()
                    return found_pid
            page_token = resp.get("nextPageToken", "")
            if not page_token:
                break
    except Exception as exc:
        # Erro de rede/API: NAO cria playlist nova - se a busca falhou por
        # motivo transitório, criar duplicata e pior. Retorna "" para o
        # chamador pular silenciosamente (ja logado aqui).
        log.warning("Erro ao buscar playlists (nao criando duplicata): %s", exc)
        return ""

    if found_pid is not None:
        return found_pid

    # Cria nova (so quando a busca rodou completa e nao achou a playlist)
    try:
        body = {
            "snippet": {"title": title, "description": "Original procedural visuals and lo-fi music by Liquid Wire."},
            "status": {"privacyStatus": "public"},
        }
        resp = _retry_youtube_call(service.playlists().insert(part="snippet,status", body=body).execute)
        pid = resp["id"]
        _playlist_cache[title] = pid
        _save_cache()
        log.info("Playlist criada: %s (id=%s)", title, pid)
        return pid
    except Exception as exc:
        log.warning("Erro ao criar playlist %s: %s", title, exc)
        return ""


def add_video_to_playlist(service: Any, video_id: str, mood: str = "", kind: str = "") -> None:
    """Adiciona um video a playlist apropriada baseada em mood/kind."""
    target_title = ""
    by_mood = active_channel.playlists_by_mood
    by_kind = active_channel.playlists_by_kind
    if mood and mood in by_mood:
        target_title = by_mood[mood]
    elif kind and kind in by_kind:
        target_title = by_kind[kind]

    if not target_title:
        return

    pid = _find_or_create_playlist(service, target_title)
    if not pid:
        return

    try:
        body = {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
        _retry_youtube_call(service.playlistItems().insert(part="snippet", body=body).execute)
        log.info("Video %s adicionado a playlist '%s'", video_id, target_title)
    except Exception as exc:
        log.warning("Erro ao adicionar video a playlist: %s", exc)
