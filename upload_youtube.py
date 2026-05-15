#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload_youtube.py — Faz upload dos vídeos gerados para o YouTube
=================================================================
Requer: token.json (gerado pelo auth_youtube.py uma única vez)
"""

import os, json, logging
from pathlib import Path
from datetime import datetime, timezone

PLAYLIST_DATA_FILE = Path("_data/yt_playlists.json")

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

LOG_FILE   = "upload_youtube.log"
VIDEOS_DIR = Path("_videos")
TOKEN_FILE = Path("token.json")
SCOPES     = ["https://www.googleapis.com/auth/youtube.upload",
               "https://www.googleapis.com/auth/youtube"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def _load_playlist_ids() -> dict:
    if PLAYLIST_DATA_FILE.exists():
        try:
            return json.loads(PLAYLIST_DATA_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_playlist_ids(data: dict) -> None:
    PLAYLIST_DATA_FILE.parent.mkdir(exist_ok=True)
    PLAYLIST_DATA_FILE.write_text(json.dumps(data, indent=2))


def _get_or_create_playlist(youtube, category: str, playlist_ids: dict) -> str | None:
    """Get existing playlist ID or create a new one for the category."""
    key = category.lower() if category else "general"
    if key in playlist_ids:
        return playlist_ids[key]

    title_map = {
        "world": "🌍 World News — GlobalBR News",
        "technology": "💻 Tech News — GlobalBR News",
        "politics": "🏛️ Politics — GlobalBR News",
        "business": "💼 Business & Economy — GlobalBR News",
        "science": "🔬 Science — GlobalBR News",
        "health": "🏥 Health — GlobalBR News",
        "environment": "🌱 Environment — GlobalBR News",
        "ai": "🤖 AI & Machine Learning — GlobalBR News",
        "sports": "⚽ Sports — GlobalBR News",
        "roundup": "📰 News Roundups — GlobalBR News",
        "shorts": "⚡ News Shorts — GlobalBR News",
    }
    playlist_title = title_map.get(key, f"📺 {category.capitalize()} — GlobalBR News")

    try:
        resp = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": playlist_title,
                    "description": f"Latest {category} news from GlobalBR News — world news every hour.\n\n🌐 https://non-s.github.io",
                    "defaultLanguage": "en",
                },
                "status": {"privacyStatus": "public"},
            }
        ).execute()
        pid = resp["id"]
        playlist_ids[key] = pid
        _save_playlist_ids(playlist_ids)
        log.info(f"  📋 Created playlist '{playlist_title}': {pid}")
        return pid
    except Exception as e:
        log.warning(f"  Could not create playlist for {category}: {e}")
        return None


def _add_to_playlist(youtube, video_id: str, playlist_id: str) -> None:
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            }
        ).execute()
        log.info(f"  📋 Added to playlist")
    except Exception as e:
        log.warning(f"  Could not add to playlist: {e}")


def get_youtube_client():
    """Autentica usando token salvo."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "token.json não encontrado! Execute auth_youtube.py primeiro."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
        log.info("Token renovado automaticamente.")
    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, meta: dict) -> str | None:
    """Faz upload de um vídeo com thumbnail e metadados SEO."""
    video_path = Path(meta["video"])
    thumb_path = Path(meta["thumbnail"])

    if not video_path.exists():
        log.error(f"Vídeo não encontrado: {video_path}")
        return None

    log.info(f"📤 Uploading: {meta['title'][:60]}...")

    body = {
        "snippet": {
            "title":       meta["title"][:100],   # YouTube limit: 100 chars
            "description": meta["description"][:5000],  # YouTube limit: 5000 chars
            "tags":        meta["tags"][:500],   # YouTube limit
            "categoryId":  meta.get("category_id", "28"),
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus":           meta.get("privacy", "public"),
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=1024*1024,   # 1MB chunks
        resumable=True,
        mimetype="video/mp4",
    )

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log.info(f"  Upload: {pct}%")

        video_id = response["id"]
        yt_url   = f"https://youtube.com/watch?v={video_id}"
        log.info(f"  ✅ Publicado: {yt_url}")

        # Faz upload da thumbnail
        if thumb_path.exists():
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg"),
            ).execute()
            log.info(f"  🖼  Thumbnail aplicada")

        # Add to category playlist
        playlist_ids = _load_playlist_ids()
        category = meta.get("category", "roundup")
        playlist_id = _get_or_create_playlist(youtube, category, playlist_ids)
        if playlist_id:
            _add_to_playlist(youtube, video_id, playlist_id)

        return video_id

    except HttpError as e:
        log.error(f"  ❌ Erro HTTP {e.resp.status}: {e.content}")
        if e.resp.status == 403:
            log.error("  Cota da API atingida. Tente amanhã.")
        return None


def main():
    try:
        youtube = get_youtube_client()
    except FileNotFoundError as e:
        log.error(str(e))
        return

    # Busca vídeos com metadata JSON prontos para upload
    pending = sorted(VIDEOS_DIR.glob("*.json"))
    if not pending:
        log.info("Nenhum vídeo pendente para upload.")
        return

    uploaded = 0
    for meta_file in pending:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))

        video_id = upload_video(youtube, meta)
        if video_id:
            # Marca como enviado com metadados completos para cross-posting
            done_file = meta_file.with_suffix(".done")
            done_file.write_text(json.dumps({
                "video_id":    video_id,
                "url":         f"https://youtube.com/watch?v={video_id}",
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "title":       meta["title"],
                "description": meta.get("description", ""),
                "tags":        meta.get("tags", []),
                "thumbnail":   meta.get("thumbnail", ""),
                "category":    meta.get("category", ""),
                "is_short":    meta.get("is_short", False),
            }, indent=2))
            meta_file.unlink()   # remove metadata original
            uploaded += 1

    log.info(f"\n🏁 {uploaded} vídeo(s) publicado(s) no YouTube.")


if __name__ == "__main__":
    main()
