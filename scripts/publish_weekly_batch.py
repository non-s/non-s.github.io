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
workflow liquid-wire-weekly.yml ate que todos os 35 videos estejam publicos.
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

from upload_youtube import _build_tags, _meta_path, _record_video_tags
from utils import ffmpeg_helpers
from utils.content_funnel import record_funnel_candidate
from utils.log_config import configure_logging, log_exception_to_file
from utils.youtube_oauth import get_youtube_service
from utils.youtube_post_upload import add_to_playlists, apply_captions, apply_thumbnail
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

log = logging.getLogger(__name__)

OUTPUT_DIR = ROOT / "_videos"
MAX_UPLOADS_PER_RUN = 6
UPLOAD_DELAY_SECONDS = 5  # pausa entre uploads para nao saturar a API
# Maximo de tentativas de publicacao por video antes de desistir: evita
# loop infinito em arquivo corrompido (duracao 0, metadata invalida) que
# nunca vai publicar mas continua sendo re-tentado todo dia.
_MAX_PUBLISH_ATTEMPTS = 3


def _find_unpublished_videos(prefix: str = "") -> list[tuple[Path, dict]]:
    """Encontra videos gerados que ainda nao foram publicados.

    Um video e considerado 'nao publicado' se seu .json de metadados
    nao contem a chave 'published=True' ou 'video_id'.

    Videos com 'publish_attempts >= _MAX_PUBLISH_ATTEMPTS' sao ignorados:
    antes, um arquivo corrompido (duracao 0, metadata invalida, etc) era
    re-tentado todo dia infinitamente, gastando quota e enchendo o log de
    erros repetidos. Apos atingir o limite, o video e considerado
    "permanentemente falhado" e skipado.
    """
    pattern = f"{prefix}*.json" if prefix else "liquid_wire_*.json"
    candidates = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    unpublished: list[tuple[Path, dict]] = []
    for meta_path in candidates:
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if data.get("published") or data.get("video_id"):
                continue
            if data.get("publish_attempts", 0) >= _MAX_PUBLISH_ATTEMPTS:
                log.warning(
                    "Video %s descartado: %d tentativas de publicacao sem sucesso (limite %d).",
                    meta_path.name,
                    data.get("publish_attempts", 0),
                    _MAX_PUBLISH_ATTEMPTS,
                )
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
    title = str(meta.get("title", "Liquid Wire"))[:100]
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
            _retry_youtube_call(service.videos().update(part="status", body=body).execute)
            log.info("Video %s atualizado para publico.", existing_id)
            return existing_id
        except Exception as exc:
            log.warning("Falha ao atualizar privacy do video %s: %s. Fazendo novo upload.", existing_id, exc)

    # Sanity check antes de gastar quota da API: ver comentario equivalente
    # em upload_youtube.py:upload_video.
    duration = ffmpeg_helpers.get_video_duration(str(video_path))
    if duration <= 0:
        log.error("Video %s com duracao invalida (%.1fs) - upload abortado.", video_path.name, duration)
        return None

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

    # Ver comentario equivalente em upload_youtube.py:upload_video.
    actual_privacy = response.get("status", {}).get("privacyStatus")
    if actual_privacy != privacy:
        log.error(
            "Video %s saiu com privacyStatus=%r, esperado %r - confira manualmente.",
            video_id,
            actual_privacy,
            privacy,
        )

    _record_video_tags(video_id, meta)
    record_funnel_candidate(video_id, meta)

    apply_thumbnail(service, video_id, _meta_path(meta, "thumbnail"), _retry_youtube_call)
    apply_captions(service, video_id, meta, _retry_youtube_call)
    add_to_playlists(service, video_id, meta)

    return video_id


def main() -> int:
    configure_logging()
    privacy = os.environ.get("YOUTUBE_PRIVACY", "public")

    try:
        service = get_youtube_service()
    except Exception as exc:
        log.error("Erro ao autenticar YouTube (liquid_wire): %s", exc)
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
            else:
                # _publish_video retornou None (duracao invalida, etc):
                # incrementa o contador de tentativas para que o video seja
                # skipado apos _MAX_PUBLISH_ATTEMPTS falhas consecutivas.
                attempts = meta.get("publish_attempts", 0) + 1
                meta["publish_attempts"] = attempts
                video_path.with_suffix(".json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                log.warning(
                    "Video %s falhou (tentativa %d/%d).",
                    video_path.name,
                    attempts,
                    _MAX_PUBLISH_ATTEMPTS,
                )
        except Exception as exc:
            log.error("Falha ao publicar %s: %s", video_path.name, exc)
            log_exception_to_file(exc, OUTPUT_DIR)
            attempts = meta.get("publish_attempts", 0) + 1
            meta["publish_attempts"] = attempts
            try:
                video_path.with_suffix(".json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass
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
