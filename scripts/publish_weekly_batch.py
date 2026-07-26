"""
scripts/publish_weekly_batch.py — publica proximos 6 videos gerados como publicos.

Le os metadados em _videos/*.json, encontra videos ainda nao publicados,
faz upload de ate 6 por vez (limite de quota do YouTube) e os marca como
publicos. Se ja foram feitos upload como private, apenas atualiza o
privacyStatus para public (custa bem menos que um insert novo). Na pratica
isso so vale para os PRIMEIROS 6 videos do lote (uploaded como private no
job "generate" do workflow) - os outros 29 nunca tem video_id ainda, entao
os proximos ~5 dias de publish fazem inserts normais mesmo, nao updates.

Este script e parte do lote semanal: e disparado uma vez por dia pelo
workflow pata-jazz-weekly.yml ate que todos os 35 videos estejam publicos.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from googleapiclient.http import MediaFileUpload

from upload_youtube import _build_tags, _meta_path, _retry_youtube_call
from utils.log_config import configure_logging, log_exception_to_file
from utils.youtube_oauth import get_youtube_service

log = logging.getLogger(__name__)

OUTPUT_DIR = ROOT / "_videos"
MAX_UPLOADS_PER_RUN = 6
UPLOAD_DELAY_SECONDS = 5  # pausa entre uploads para nao saturar a API


def _find_unpublished_videos(prefix: str = "pata_jazz_") -> list[tuple[Path, dict]]:
    """Encontra videos gerados que ainda nao foram publicados.

    Um video e considerado 'nao publicado' se seu .json de metadados
    nao contem a chave 'published=True' ou 'video_id'.
    """
    candidates = sorted(OUTPUT_DIR.glob(f"{prefix}*.json"), key=lambda p: p.stat().st_mtime)
    unpublished: list[tuple[Path, dict]] = []
    for meta_path in candidates:
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if data.get("published") or data.get("video_id"):
                continue
            video_path = meta_path.with_suffix(".mp4")
            if video_path.exists():
                unpublished.append((video_path, data))
        except Exception:
            continue
    return unpublished


def _publish_video(service, video_path: Path, meta: dict, language: str = "en") -> str | None:
    """Faz upload de um video como publico e retorna o video_id.

    Se o video ja tem um video_id no metadata (upload previo como private),
    apenas atualiza o privacyStatus para public (custa ~50 unidades).
    """
    privacy = os.environ.get("YOUTUBE_PRIVACY", "public")
    title = str(meta.get("title", "Pata Jazz"))[:100]
    description = str(meta.get("description", ""))[:5000]
    tags = _build_tags(meta.get("scene", ""), meta.get("hashtags"))

    existing_id = meta.get("video_id")

    if existing_id:
        # Ja tem upload: apenas atualiza privacy para public.
        log.info("Video %s ja tem upload; atualizando privacy para public...", existing_id)
        try:
            body = {
                "id": existing_id,
                "status": {"privacyStatus": privacy},
            }
            _retry_youtube_call(
                service.videos().update(part="status", body=body).execute
            )
            log.info("Video %s atualizado para publico.", existing_id)
            return existing_id
        except Exception as exc:
            log.warning("Falha ao atualizar privacy do video %s: %s. Fazendo novo upload.", existing_id, exc)

    # Novo upload
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "15",
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }

    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True),
    )
    response = _retry_youtube_call(request.execute)
    video_id = response["id"]
    log.info("Video enviado: https://youtu.be/%s", video_id)

    # Thumbnail
    thumbnail = _meta_path(meta, "thumbnail")
    if thumbnail and thumbnail.exists():
        try:
            thumb_media = MediaFileUpload(str(thumbnail))
            _retry_youtube_call(service.thumbnails().set(videoId=video_id, media_body=thumb_media).execute)
            log.info("Thumbnail aplicada.")
        except Exception as exc:
            hint = " (canal sem verificacao por telefone bloqueia thumbnail customizada - confira em youtube.com/verify)" if "403" in str(exc) else ""
            log.warning("Falha ao aplicar thumbnail: %s%s", exc, hint)

    # Legenda
    caption_path = _meta_path(meta, "caption")
    if caption_path and caption_path.exists():
        try:
            caption_body = {
                "snippet": {
                    "videoId": video_id,
                    "language": "en",
                    "name": "English",
                    "isDraft": False,
                }
            }
            cap_mimetype = "text/vtt" if caption_path.suffix.lower() == ".vtt" else "application/x-subrip"
            _retry_youtube_call(
                service.captions().insert(
                    part="snippet",
                    body=caption_body,
                    media_body=MediaFileUpload(str(caption_path), mimetype=cap_mimetype),
                ).execute
            )
            log.info("Legenda aplicada.")
        except Exception as exc:
            log.warning("Falha ao aplicar legenda: %s", exc)

    # Playlist: por formato (kind) e por mood (chamadas separadas - ver
    # comentario equivalente em upload_youtube.py:upload_video).
    try:
        from utils.playlist_manager import add_video_to_playlist
        add_video_to_playlist(service, video_id, kind=meta.get("kind", ""))
        if meta.get("mood"):
            add_video_to_playlist(service, video_id, mood=meta["mood"])
    except Exception as exc:
        log.warning("Falha ao adicionar a playlist: %s", exc)

    return video_id


def main() -> int:
    configure_logging()
    privacy = os.environ.get("YOUTUBE_PRIVACY", "public")

    try:
        service = get_youtube_service()
    except Exception as exc:
        log.error("Erro ao autenticar YouTube: %s", exc)
        return 1

    unpublished = _find_unpublished_videos()
    if not unpublished:
        log.info("Nenhum video aguardando publicacao. Lote semanal concluido!")
        return 0

    log.info("Videos aguardando publicacao: %d (publicando ate %d agora)", len(unpublished), MAX_UPLOADS_PER_RUN)

    published = 0
    for video_path, meta in unpublished[:MAX_UPLOADS_PER_RUN]:
        try:
            video_id = _publish_video(service, video_path, meta)
            if video_id:
                # Marca como publicado no metadata
                meta["published"] = True
                meta["video_id"] = video_id
                meta["privacy_status"] = privacy
                video_path.with_suffix(".json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                published += 1
                log.info("Publicado %d/%d: %s", published, min(len(unpublished), MAX_UPLOADS_PER_RUN), video_id)
                if published < MAX_UPLOADS_PER_RUN:
                    time.sleep(UPLOAD_DELAY_SECONDS)
        except Exception as exc:
            log.error("Falha ao publicar %s: %s", video_path.name, exc)
            log_exception_to_file(exc, OUTPUT_DIR)
            continue

    log.info("Lote de publicacao concluido: %d videos publicados.", published)

    # Conta quantos restam
    remaining = len(unpublished) - published
    if remaining > 0:
        log.info("Ainda restam %d videos para publicar nos proximos dias.", remaining)
    else:
        log.info("Todos os videos do lote semanal foram publicados!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
