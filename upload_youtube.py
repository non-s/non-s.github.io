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
            "title":       meta["title"],
            "description": meta["description"],
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
            # Marca como enviado
            done_file = meta_file.with_suffix(".done")
            done_file.write_text(json.dumps({
                "video_id":   video_id,
                "url":        f"https://youtube.com/watch?v={video_id}",
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "title":      meta["title"],
            }, indent=2))
            meta_file.unlink()   # remove metadata original
            uploaded += 1

    log.info(f"\n🏁 {uploaded} vídeo(s) publicado(s) no YouTube.")


if __name__ == "__main__":
    main()
