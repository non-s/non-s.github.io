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

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = ROOT / "_data"
_CACHE_FILE = _DATA_DIR / "playlist_cache.json"

# Playlists por mood
PLAYLISTS_BY_MOOD: dict[str, str] = {
    "relax": "Pata Jazz | Relaxar e Dormir",
    "fofura": "Pata Jazz | Fofura Diaria",
    "diversao": "Pata Jazz | Pets Felizes",
}

# Playlist por formato
PLAYLISTS_BY_KIND: dict[str, str] = {
    "short": "Pata Jazz | Shorts",
    "horizontal": "Pata Jazz | Videos Completos",
}

# Cache de playlist IDs (criadas sob demanda). Persistido em _data/ para
# sobreviver entre runs do workflow e evitar re-buscar/recriar playlists.
_playlist_cache: dict[str, str] = {}


def _load_cache() -> None:
    """Carrega o cache de playlist IDs do disco, se existir."""
    global _playlist_cache
    if _CACHE_FILE.exists():
        try:
            _playlist_cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _playlist_cache = {}


def _save_cache() -> None:
    """Persiste o cache de playlist IDs no disco."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(_playlist_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Falha ao salvar cache de playlists: %s", exc)


def _find_or_create_playlist(service: Any, title: str) -> str:
    """Busca uma playlist pelo titulo ou cria nova. Retorna playlist ID."""
    if not _playlist_cache:
        _load_cache()
    if title in _playlist_cache:
        return _playlist_cache[title]

    # Busca playlists existentes (pagina todas, ate 200).
    try:
        found_ids: list[str] = []
        page_token = ""
        while len(found_ids) < 200:
            resp = service.playlists().list(
                part="id,snippet", mine=True, maxResults=50, pageToken=page_token
            ).execute()
            for item in resp.get("items", []):
                if item.get("snippet", {}).get("title", "") == title:
                    pid = item["id"]
                    _playlist_cache[title] = pid
                    _save_cache()
                    return pid
            page_token = resp.get("nextPageToken", "")
            if not page_token:
                break
    except Exception as exc:
        log.warning("Erro ao buscar playlists: %s", exc)

    # Cria nova
    try:
        body = {
            "snippet": {"title": title, "description": "Playlist automatica do canal Pata Jazz"},
            "status": {"privacyStatus": "public"},
        }
        resp = service.playlists().insert(part="snippet,status", body=body).execute()
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
    if mood and mood in PLAYLISTS_BY_MOOD:
        target_title = PLAYLISTS_BY_MOOD[mood]
    elif kind and kind in PLAYLISTS_BY_KIND:
        target_title = PLAYLISTS_BY_KIND[kind]

    if not target_title:
        return

    pid = _find_or_create_playlist(service, target_title)
    if not pid:
        return

    try:
        body = {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
        service.playlistItems().insert(part="snippet", body=body).execute()
        log.info("Video %s adicionado a playlist '%s'", video_id, target_title)
    except Exception as exc:
        log.warning("Erro ao adicionar video a playlist: %s", exc)
