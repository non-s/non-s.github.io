"""
utils/playlist_manager.py — cria e gerencia playlists do YouTube.

Playlists aumentam watch time e session duration. Cria playlists por mood
(relax, fofura, diversao) e adiciona videos automaticamente.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

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

# Cache de playlist IDs (criadas sob demanda)
_playlist_cache: dict[str, str] = {}


def _find_or_create_playlist(service: Any, title: str) -> str:
    """Busca uma playlist pelo titulo ou cria nova. Retorna playlist ID."""
    if title in _playlist_cache:
        return _playlist_cache[title]

    # Busca playlists existentes
    try:
        resp = service.playlists().list(part="id,snippet", mine=True, maxResults=50).execute()
        for item in resp.get("items", []):
            if item.get("snippet", {}).get("title", "") == title:
                pid = item["id"]
                _playlist_cache[title] = pid
                return pid
    except Exception as exc:
        log.warning("Erro ao buscar playlists: %s", exc)

    # Cria nova
    try:
        body = {
            "snippet": {"title": title, "description": f"Playlist automatica do canal Pata Jazz"},
            "status": {"privacyStatus": "public"},
        }
        resp = service.playlists().insert(part="snippet,status", body=body).execute()
        pid = resp["id"]
        _playlist_cache[title] = pid
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