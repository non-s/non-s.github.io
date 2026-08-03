"""
upload_youtube.py — faz upload de videos gravados no YouTube.

Depende do token OAuth em youtube_token.json ou das variaveis YOUTUBE_TOKEN / YOUTUBE_CLIENT_SECRET.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from utils import ffmpeg_helpers
from utils.channel_config import active_channel, set_channel_from_env
from utils.log_config import configure_logging, log_exception_to_file
from utils.paths import data_dir
from utils.pipeline_metrics import record_pipeline_run
from utils.state_lock import state_lock
from utils.youtube_oauth import get_youtube_service
from utils.youtube_post_upload import add_to_playlists, apply_captions, apply_thumbnail
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

# Ativa o canal via YOUTUBE_CHANNEL env var (multi-canal: Pata Lofi, etc).
set_channel_from_env()

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"

log = logging.getLogger(__name__)


def _latest_video_meta(prefix: str = "") -> tuple[Path, dict] | None:
    pattern = f"{prefix}*.mp4" if prefix else "*.mp4"
    candidates = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    # Restringe ao slug do canal ativo quando nenhum prefixo e explicitado,
    # evitando que Pata Lofi suba um video do Pata Jazz se ambos geraram
    # arquivos no mesmo diretorio _videos.
    active_slug = active_channel.slug
    if not prefix:
        candidates = [p for p in candidates if p.name.startswith(f"{active_slug}_")]
    skipped = 0
    for video in candidates:
        meta_path = video.with_suffix(".json")
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                if skipped:
                    log.warning("Video mais recente (%d) sem metadata foi pulado; usando %s.", skipped, video.name)
                return video, data
            except Exception:
                continue
        skipped += 1
    return None


def _meta_path(meta: dict, key: str) -> Path | None:
    """Path(meta.get(key, "")) para uma chave ausente/vazia vira Path("") ==
    Path(".") - e .exists() no diretorio atual e sempre True, entao codigo
    como MediaFileUpload(str(thumbnail)) tenta abrir um diretorio como
    arquivo e explode com IsADirectoryError em vez de so pular o upload
    opcional. So constroi o Path se o valor for realmente uma string nao-vazia.
    """
    value = meta.get(key)
    return Path(value) if value else None


def _build_tags(scene: str, hashtags: list[str] | None = None) -> list[str]:
    base = list(active_channel.base_tags)
    if "cat" in scene or "kitten" in scene:
        base.extend(["kitten", "cute cat"])
    if "dog" in scene or "puppy" in scene:
        base.extend(["puppy", "cute dog"])
    if hashtags:
        # Remove o # para normalizar e junta com as tags base
        cleaned = [h.lstrip("#") for h in hashtags]
        base.extend(cleaned)
    return list(dict.fromkeys(base))[:15]


_MAX_VIDEO_TAGS = 500


def _video_tags_file() -> Path:
    """Retorna o path do video_tags.json isolado por canal.

    Expoe como atributo de modulo (`_VIDEO_TAGS_FILE`) para testes poderem
    monkeypatchar o path sem reimportar o modulo.
    """
    return _VIDEO_TAGS_FILE


_VIDEO_TAGS_FILE: Path = data_dir() / "video_tags.json"


def _record_video_tags(video_id: str, meta: dict) -> None:
    """Persiste scene/hook/mood/title_pattern do video enviado, indexado por video_id.

    collect_analytics.py so tinha views agregadas sem nenhuma pista de qual
    cena/hook/padrao de titulo gerou qual video - o "feedback loop"
    mencionado no docstring daquele modulo nunca existiu de verdade. Esse
    mapeamento e o que falta pra cruzar performance real (views) com o que
    gerou cada video.
    """
    scene = meta.get("scene", "")
    if not scene:
        return
    tags_file = _video_tags_file()
    with state_lock(tags_file):
        try:
            existing = json.loads(tags_file.read_text(encoding="utf-8")) if tags_file.exists() else {}
        except Exception:
            existing = {}
        existing[video_id] = {
            "scene": scene,
            "hook": meta.get("hook", ""),
            "mood": meta.get("mood", ""),
            "kind": meta.get("kind", ""),
            "title": meta.get("title", ""),
            "title_pattern": meta.get("title_pattern", ""),
            "uploaded_at": datetime.now(UTC).isoformat(),
            "thumbnails": meta.get("thumbnails", []),
            "thumbnail_variant": meta.get("thumbnail_variant", "A"),
        }
        # Mantem so as N mais recentes (por ordem de insercao) pra nao crescer pra sempre.
        if len(existing) > _MAX_VIDEO_TAGS:
            for old_key in list(existing.keys())[: len(existing) - _MAX_VIDEO_TAGS]:
                del existing[old_key]
        try:
            tags_file.parent.mkdir(parents=True, exist_ok=True)
            tags_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar video_tags: %s", exc)


def upload_video(language: str = "en", privacy: str = "public", prefix: str = "") -> str | None:
    start_time = time.time()
    success = False
    try:
        video_id = _upload_video_inner(language=language, privacy=privacy, prefix=prefix)
        if video_id is not None:
            success = True
        return video_id
    finally:
        kind = prefix.rstrip("_") or active_channel.slug
        record_pipeline_run(
            stage="upload",
            success=success,
            duration_seconds=time.time() - start_time,
            kind=kind,
        )


def _upload_video_inner(language: str = "en", privacy: str = "public", prefix: str = "") -> str | None:
    found = _latest_video_meta(prefix=prefix)
    if not found:
        log.error("Nenhum video com metadata encontrado em %s", OUTPUT_DIR)
        return None
    video_path, meta = found

    # Sanity check antes de gastar quota da API: um .mp4 com duracao 0 (ffprobe
    # nao consegue ler, encode truncado, etc) sempre indica arquivo corrompido -
    # nunca um video legitimo de 0s. Aborta cedo em vez de subir lixo pro canal.
    duration = ffmpeg_helpers.get_video_duration(str(video_path))
    if duration <= 0:
        log.error("Video %s com duracao invalida (%.1fs) - upload abortado.", video_path.name, duration)
        return None

    title = str(meta.get("title", active_channel.name))[:100]
    description = str(meta.get("description", ""))[:5000]
    tags = _build_tags(meta.get("scene", ""), meta.get("hashtags"))
    thumbnail = _meta_path(meta, "thumbnail")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "15",  # Pets & Animals
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }

    service = get_youtube_service()
    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True),
    )
    response = _retry_youtube_call(request.execute)
    video_id = response["id"]
    log.info("Video enviado: https://youtu.be/%s", video_id)

    # A resposta do insert() ja inclui "status" (pedido no part= acima) - da
    # pra conferir se o vídeo saiu mesmo com o privacyStatus pedido sem gastar
    # outra chamada. Vídeo preso em "private"/"processing" quando devia ser
    # público some do canal em silêncio; melhor logar alto do que descobrir
    # dias depois.
    actual_privacy = response.get("status", {}).get("privacyStatus")
    if actual_privacy != privacy:
        log.error(
            "Video %s saiu com privacyStatus=%r, esperado %r - confira manualmente.",
            video_id,
            actual_privacy,
            privacy,
        )

    _record_video_tags(video_id, meta)

    apply_thumbnail(service, video_id, thumbnail, _retry_youtube_call)
    apply_captions(service, video_id, meta, _retry_youtube_call)
    add_to_playlists(service, video_id, meta)

    return video_id


def main() -> int:
    default_prefix = f"{active_channel.slug}_"
    parser = argparse.ArgumentParser(description=f"Upload {active_channel.name} para YouTube")
    parser.add_argument("--mode", choices=["upload"], default="upload")
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--privacy", default=os.environ.get("YOUTUBE_PRIVACY", "public"), choices=["public", "unlisted", "private"]
    )
    parser.add_argument("--prefix", default=default_prefix, help="Prefixo dos arquivos de video a enviar")
    args = parser.parse_args()

    configure_logging()

    try:
        video_id = upload_video(language=args.language, privacy=args.privacy, prefix=args.prefix)
        if not video_id:
            return 1
        # video_id e publico (esta na URL publica do YouTube), seguro de imprimir.
        print(video_id)
        return 0
    except HttpError as exc:
        log.exception("Erro da YouTube API: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1
    except Exception as exc:
        log.exception("Falha no upload: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1


if __name__ == "__main__":
    sys.exit(main())
