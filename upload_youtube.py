"""
upload_youtube.py — faz upload de videos gravados no YouTube.

Antes tratava tambem da criacao de transmissao ao vivo (liveBroadcast /
liveStream); essa responsabilidade foi movida para live_broadcast.py. O
modo `--mode live` ainda funciona chamando live_broadcast.create_live_stream(),
e os simbolos de live continuam re-exportados aqui (ver final do arquivo)
para nao quebrar imports existentes (scripts/run_live.py e testes).

Depende do token OAuth em youtube_token.json ou das variaveis YOUTUBE_TOKEN / YOUTUBE_CLIENT_SECRET.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from utils import ffmpeg_helpers
from utils.channel_config import active_channel, set_channel_from_env
from utils.log_config import configure_logging, log_exception_to_file
from utils.state_lock import state_lock
from utils.youtube_oauth import get_youtube_service
from utils.youtube_post_upload import add_to_playlists, apply_captions, apply_thumbnail
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

# Ativa o canal via YOUTUBE_CHANNEL env var (multi-canal: Pata Lofi, etc).
set_channel_from_env()

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
LIVE_META_DIR = ROOT / "_data"

log = logging.getLogger(__name__)


def _latest_video_meta(prefix: str = "pata_jazz_") -> tuple[Path, dict] | None:
    candidates = sorted(OUTPUT_DIR.glob(f"{prefix}*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
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


_VIDEO_TAGS_FILE = LIVE_META_DIR / "video_tags.json"
_MAX_VIDEO_TAGS = 500


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
    with state_lock(_VIDEO_TAGS_FILE):
        try:
            existing = json.loads(_VIDEO_TAGS_FILE.read_text(encoding="utf-8")) if _VIDEO_TAGS_FILE.exists() else {}
        except Exception:
            existing = {}
        existing[video_id] = {
            "scene": scene,
            "hook": meta.get("hook", ""),
            "mood": meta.get("mood", ""),
            "kind": meta.get("kind", ""),
            "title_pattern": meta.get("title_pattern", ""),
            "uploaded_at": datetime.now(UTC).isoformat(),
            "thumbnails": meta.get("thumbnails", []),
            "thumbnail_variant": "A",
        }
        # Mantem so as N mais recentes (por ordem de insercao) pra nao crescer pra sempre.
        if len(existing) > _MAX_VIDEO_TAGS:
            for old_key in list(existing.keys())[: len(existing) - _MAX_VIDEO_TAGS]:
                del existing[old_key]
        try:
            _VIDEO_TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            _VIDEO_TAGS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar video_tags: %s", exc)


def upload_video(language: str = "en", privacy: str = "public", prefix: str = "pata_jazz_") -> str | None:
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

    title = str(meta.get("title", "Pata Jazz"))[:100]
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
            video_id, actual_privacy, privacy,
        )

    _record_video_tags(video_id, meta)

    apply_thumbnail(service, video_id, thumbnail, _retry_youtube_call)
    apply_captions(service, video_id, meta, _retry_youtube_call)
    add_to_playlists(service, video_id, meta)

    return video_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload Pata Jazz para YouTube")
    parser.add_argument("--mode", choices=["upload", "live"], default="upload")
    parser.add_argument("--language", default="en")
    parser.add_argument("--privacy", default=os.environ.get("YOUTUBE_PRIVACY", "public"),
                        choices=["public", "unlisted", "private"])
    parser.add_argument("--title", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--resolution", default="1080p", choices=["1080p", "720p", "480p"])
    parser.add_argument("--broadcast-id", default="")
    parser.add_argument("--transition", choices=["live", "complete"], default="")
    parser.add_argument("--prefix", default="pata_jazz_", help="Prefixo dos arquivos de video a enviar")
    args = parser.parse_args()

    configure_logging()

    try:
        if args.transition:
            if not args.broadcast_id:
                log.error("--broadcast-id obrigatorio com --transition")
                return 1
            # transition_broadcast/delete_broadcast foram movidos para
            # live_broadcast.py mas continuam acessiveis aqui via re-export.
            transition_broadcast(args.broadcast_id, args.transition)
            return 0

        if args.mode == "upload":
            video_id = upload_video(language=args.language, privacy=args.privacy, prefix=args.prefix)
            if not video_id:
                return 1
            # video_id e publico (esta na URL publica do YouTube), seguro de imprimir.
            print(video_id)
        else:
            meta = create_live_stream(
                title=args.title,
                description=args.description,
                privacy=args.privacy,
                resolution=args.resolution,
            )
            if not meta:
                return 1
            # stream_name e a credencial efetiva do RTMP - quem tem ela pode
            # iniciar uma transmissao no canal. So repassa para scripts/run_live.py
            # via arquivo de estado (_data/live_state.json), nunca para o log
            # publico do GitHub Actions. log.info usa o logger (que vai para
            # stderr em CI), mas o print abaixo ia para o stdout do job, que e
            # visivel em Actions > logs sem mascara de segredo. Imprime so o
            # broadcast_id (publico) e a URL publica de watch.
            broadcast_id = meta.get("broadcast_id", "")
            log.info("Live criada: broadcast=%s url=https://youtu.be/%s", broadcast_id, broadcast_id)
        return 0
    except HttpError as exc:
        log.exception("Erro da YouTube API: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1
    except Exception as exc:
        log.exception("Falha no upload: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1


# ---------------------------------------------------------------------------
# Backward-compat: re-export dos simbolos de live movidos para live_broadcast.py.
#
# Scripts e testes que antes importavam de upload_youtube (scripts/run_live.py,
# tests/test_live_stream_activation.py, tests/test_upload_youtube.py) continuam
# funcionando sem mudanca. Nao use estes nomes em codigo novo - importe direto
# de live_broadcast.
# ---------------------------------------------------------------------------
from live_broadcast import (  # noqa: E402,F401
    _LIVE_STATE_FILE,
    _MAX_ACTIVE_AGE_MINUTES,
    _MAX_READY_AGE_MINUTES,
    _MAX_VIEWER_SNAPSHOTS,
    _RESUMABLE_LIFECYCLE_STATUSES,
    LIVE_TAGS,
    LIVE_VIEWER_HISTORY_FILE,
    _broadcast_age_minutes,
    _generate_live_title,
    _try_resume_existing_broadcast,
    cleanup_orphan_broadcasts,
    create_live_stream,
    delete_broadcast,
    record_live_viewer_snapshot,
    transition_broadcast,
    wait_for_stream_active,
)

if __name__ == "__main__":
    sys.exit(main())
