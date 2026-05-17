#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload_youtube.py — Faz upload dos vídeos gerados para o YouTube
=================================================================
Requer: token.json (gerado pelo auth_youtube.py uma única vez)
"""

import os, json, logging, time
from pathlib import Path
from datetime import datetime, timezone

PLAYLIST_DATA_FILE = Path("_data/yt_playlists.json")

from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

LOG_FILE   = "upload_youtube.log"
VIDEOS_DIR = Path("_videos")
TOKEN_FILE = Path("token.json")
SCOPES     = ["https://www.googleapis.com/auth/youtube.upload",
               "https://www.googleapis.com/auth/youtube"]
MAX_RETRIES = 4
RETRYABLE_STATUSES = {500, 502, 503, 504}

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
    """Autentica usando token salvo, com diagnóstico claro de falhas comuns."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "token.json não encontrado! Execute auth_youtube.py primeiro "
            "(ou defina o secret YOUTUBE_TOKEN no GitHub)."
        )
    raw = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        raise RuntimeError(
            "token.json está vazio. O secret YOUTUBE_TOKEN provavelmente "
            "não foi configurado. Rode auth_youtube.py localmente e copie o "
            "conteúdo de token.json para o secret YOUTUBE_TOKEN."
        )
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"token.json malformado ({exc}). Recrie com auth_youtube.py."
        ) from exc

    if not creds.refresh_token:
        raise RuntimeError(
            "token.json não contém refresh_token. Re-autorize com "
            "auth_youtube.py (a primeira autorização gera o refresh_token)."
        )
    if creds.expired:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise RuntimeError(
                f"Falha ao renovar token YouTube: {exc}. "
                "Causa provável: refresh_token revogado/expirado. "
                "Solução: rodar auth_youtube.py localmente e atualizar o "
                "secret YOUTUBE_TOKEN."
            ) from exc
        TOKEN_FILE.write_text(creds.to_json())
        log.info("✅ Access token renovado via refresh_token.")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(youtube, meta: dict) -> str | None:
    """Faz upload de um vídeo com thumbnail e metadados SEO."""
    video_field = meta.get("video")
    if not video_field:
        log.error("Metadata sem campo 'video' — pulando.")
        return None
    video_path = Path(video_field)
    # Thumbnail is optional — Shorts metadata sometimes omits it, in which
    # case we just skip the thumbnail upload step.
    thumb_field = meta.get("thumbnail") or ""
    thumb_path = Path(thumb_field) if thumb_field else None

    if not video_path.exists():
        log.error(f"Vídeo não encontrado: {video_path}")
        return None

    title = (meta.get("title") or "").strip()
    if not title:
        log.error("Metadata sem 'title' — YouTube exige um título.")
        return None
    description = (meta.get("description") or "").strip()
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    log.info(f"📤 Uploading: {title[:60]}...")

    # YouTube limits tags to ~500 *characters* total across the list,
    # not 500 items. Pack greedily until the budget runs out.
    packed_tags: list[str] = []
    char_budget = 0
    for raw_tag in tags or []:
        tag = str(raw_tag).strip()
        if not tag:
            continue
        # Account for commas between tags (YouTube counts them).
        cost = len(tag) + (1 if packed_tags else 0)
        if char_budget + cost > 480:  # leave 20-char safety margin
            break
        packed_tags.append(tag)
        char_budget += cost

    body = {
        "snippet": {
            "title":       title[:100],   # YouTube limit: 100 chars
            "description": description[:5000],  # YouTube limit: 5000 chars
            "tags":        packed_tags,
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

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    # ── Chunked upload with retry/backoff on transient errors ───────
    response = None
    attempt = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log.info(f"  Upload: {pct}%")
        except HttpError as e:
            code = getattr(e.resp, "status", 0)
            if code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                attempt += 1
                wait = 2 ** attempt
                log.warning(f"  ⚠️ HTTP {code} on chunk; retry {attempt}/{MAX_RETRIES} in {wait}s")
                time.sleep(wait)
                continue
            log.error(f"  ❌ Erro HTTP {code}: {e.content!r}")
            if code == 403:
                log.error("  Causa provável: cota diária esgotada (10.000/dia, 1600/upload)")
                log.error("  ou OAuth client/refresh_token revogado.")
            elif code == 401:
                log.error("  Auth inválida — refresh_token expirou. Re-rode auth_youtube.py.")
            return None
        except (TimeoutError, ConnectionError) as e:
            if attempt < MAX_RETRIES:
                attempt += 1
                wait = 2 ** attempt
                log.warning(f"  ⚠️ {type(e).__name__}: retry {attempt}/{MAX_RETRIES} in {wait}s")
                time.sleep(wait)
                continue
            log.error(f"  ❌ Falha de conexão após {MAX_RETRIES} tentativas: {e}")
            return None

    video_id = response["id"]
    yt_url   = f"https://youtube.com/watch?v={video_id}"
    log.info(f"  ✅ Publicado: {yt_url}")

    # Faz upload da thumbnail (não-crítico — vídeo já foi publicado)
    if thumb_path and thumb_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg"),
            ).execute()
            log.info(f"  🖼  Thumbnail aplicada")
        except HttpError as e:
            log.warning(f"  ⚠️ Não foi possível aplicar thumbnail: HTTP {e.resp.status}")
    else:
        log.info("  ℹ️ Sem thumbnail — pulando upload de thumbnail.")

    # Add to category playlist
    try:
        playlist_ids = _load_playlist_ids()
        category = meta.get("category", "roundup")
        playlist_id = _get_or_create_playlist(youtube, category, playlist_ids)
        if playlist_id:
            _add_to_playlist(youtube, video_id, playlist_id)
    except Exception as e:
        log.warning(f"  ⚠️ Playlist association failed: {e}")

    return video_id


def main():
    try:
        youtube = get_youtube_client()
    except FileNotFoundError as e:
        log.error("❌ %s", e)
        return
    except RuntimeError as e:
        # Surfaceia o erro com instruções acionáveis (ver get_youtube_client).
        log.error("❌ %s", e)
        return

    # Busca vídeos com metadata JSON prontos para upload
    pending = sorted(VIDEOS_DIR.glob("*.json"))
    if not pending:
        log.info("Nenhum vídeo pendente para upload.")
        return
    log.info("📋 %d vídeo(s) pendente(s) para upload", len(pending))

    uploaded = 0
    for meta_file in pending:
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.error("Falha ao ler %s: %s", meta_file.name, e)
            continue

        video_id = upload_video(youtube, meta)
        if video_id:
            done_file = meta_file.with_suffix(".done")
            done_file.write_text(json.dumps({
                "video_id":    video_id,
                "url":         f"https://youtube.com/watch?v={video_id}",
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "title":       meta.get("title", ""),
                "description": meta.get("description", ""),
                "tags":        meta.get("tags", []),
                "thumbnail":   meta.get("thumbnail", ""),
                "category":    meta.get("category", ""),
                "is_short":    meta.get("is_short", False),
            }, indent=2))
            meta_file.unlink()
            uploaded += 1

    log.info("🏁 %d/%d vídeo(s) publicado(s) no YouTube.", uploaded, len(pending))


if __name__ == "__main__":
    main()
