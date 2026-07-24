"""
upload_youtube.py — faz upload de videos ou cria transmissao ao vivo no YouTube.

Modos:
  --mode upload       (padrao) Envia o ultimo video gerado em _videos.
  --mode live         Cria liveBroadcast + liveStream, faz bind e imprime a URL RTMP.

Depende do token OAuth em youtube_token.json ou das variaveis YOUTUBE_TOKEN / YOUTUBE_CLIENT_SECRET.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.errors import HttpError, MediaUploadSizeError
from googleapiclient.http import MediaFileUpload

from utils.ai_helper import ai_text
from utils.log_config import configure_logging, log_exception_to_file
from utils.youtube_oauth import get_youtube_service

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
LIVE_META_DIR = ROOT / "_data"

log = logging.getLogger(__name__)

# Retry config para YouTube API
_YOUTUBE_MAX_RETRIES = 3
_YOUTUBE_BASE_BACKOFF = 2.0


def _latest_video_meta(prefix: str = "pata_jazz_") -> tuple[Path, dict] | None:
    candidates = sorted(OUTPUT_DIR.glob(f"{prefix}*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    for video in candidates:
        meta_path = video.with_suffix(".json")
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                return video, data
            except Exception:
                continue
    return None


def _build_tags(scene: str, hashtags: list[str] | None = None) -> list[str]:
    base = ["Pata Jazz", "gato", "cachorro", "jazz", "fofo", "relaxante"]
    if "cat" in scene or "kitten" in scene:
        base.extend(["gatinho", "cat", "kitten"])
    if "dog" in scene or "puppy" in scene:
        base.extend(["cachorrinho", "dog", "puppy"])
    if hashtags:
        # Remove o # para normalizar e junta com as tags base
        cleaned = [h.lstrip("#") for h in hashtags]
        base.extend(cleaned)
    return list(dict.fromkeys(base))[:15]


def upload_video(language: str = "pt", privacy: str = "public", prefix: str = "pata_jazz_") -> str | None:
    found = _latest_video_meta(prefix=prefix)
    if not found:
        log.error("Nenhum video com metadata encontrado em %s", OUTPUT_DIR)
        return None
    video_path, meta = found

    title = str(meta.get("title", "Pata Jazz"))[:100]
    description = str(meta.get("description", ""))[:5000]
    tags = _build_tags(meta.get("scene", ""), meta.get("hashtags"))
    thumbnail = Path(meta.get("thumbnail", ""))

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

    if thumbnail.exists():
        try:
            _retry_youtube_call(service.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail))).execute)
            log.info("Thumbnail aplicada.")
        except (HttpError, MediaUploadSizeError) as exc:
            log.warning("Falha ao aplicar thumbnail: %s", exc)

    return video_id


def _generate_live_title() -> str:
    prompt = (
        "Crie um titulo curto e fofo (maximo 80 caracteres) para uma live do YouTube "
        "de gatinhos e cachorrinhos com jazz de fundo, em loop infinito. "
        "Retorne APENAS o texto do titulo, sem aspas."
    )
    out = ai_text(prompt, task="live_title")
    title = out.strip().replace('"', "") if out else ""
    return title or "Pata Jazz 🐾🎷 | Gatinhos e Cachorrinhos Fofos ao Vivo"


def create_live_stream(
    title: str = "",
    description: str = "",
    privacy: str = "public",
    resolution: str = "1080p",
) -> dict | None:
    service = get_youtube_service()

    title = title or _generate_live_title()
    description = description or "Live relaxante com gatinhos e cachorrinhos fofos e jazz de fundo."

    broadcast_body = {
        "snippet": {
            "title": title,
            "description": description,
            "scheduledStartTime": datetime.now(timezone.utc).isoformat(),
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        "contentDetails": {
            "monitorStream": {"enableMonitorStream": False},
            "enableAutoStart": True,
            "enableAutoStop": False,
            "latencyPreference": "normal",
        },
    }

    broadcast = _retry_youtube_call(service.liveBroadcasts().insert(part="snippet,status,contentDetails", body=broadcast_body).execute)
    broadcast_id = broadcast["id"]

    stream_body = {
        "snippet": {
            "title": f"Pata Jazz stream {datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        },
        "cdn": {
            "resolution": resolution,
            "frameRate": "30fps",
            "ingestionType": "rtmp",
        },
    }

    stream = _retry_youtube_call(service.liveStreams().insert(part="snippet,cdn", body=stream_body).execute)
    stream_id = stream["id"]
    ingestion_info = stream["cdn"]["ingestionInfo"]
    stream_name = ingestion_info["streamName"]
    ingestion_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_name}"

    _retry_youtube_call(service.liveBroadcasts().bind(part="id,contentDetails", id=broadcast_id, streamId=stream_id).execute)

    meta = {
        "broadcast_id": broadcast_id,
        "stream_id": stream_id,
        "stream_name": stream_name,
        "ingestion_url": ingestion_url,
        "title": title,
        "description": description,
        "privacy": privacy,
    }
    LIVE_META_DIR.mkdir(parents=True, exist_ok=True)
    LIVE_META_DIR.joinpath("live_state.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Live criada: broadcast=%s stream=%s url=%s", broadcast_id, stream_id, ingestion_url)
    return meta


def transition_broadcast(broadcast_id: str, status: str) -> None:
    service = get_youtube_service()
    _retry_youtube_call(service.liveBroadcasts().transition(id=broadcast_id, part="status", broadcastStatus=status).execute)
    log.info("Broadcast %s transicionado para %s", broadcast_id, status)


def wait_for_stream_active(stream_id: str, timeout: int = 90, interval: int = 3) -> bool:
    """Aguarda o liveStream ficar com status.streamStatus == 'active'.

    A API do YouTube rejeita a transicao do broadcast para 'testing' (403
    invalidTransition) enquanto o stream vinculado nao estiver recebendo
    dados de video de verdade. E preciso comecar a enviar o FFmpeg antes
    de chamar transition_broadcast().
    """
    service = get_youtube_service()
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = _retry_youtube_call(
            service.liveStreams().list(part="status", id=stream_id).execute
        )
        items = (response or {}).get("items", [])
        status = items[0].get("status", {}).get("streamStatus") if items else None
        if status == "active":
            return True
        log.info("Aguardando stream %s ficar ativo (status atual: %s)...", stream_id, status)
        time.sleep(interval)
    log.error("Stream %s nao ficou ativo apos %ss.", stream_id, timeout)
    return False


def _retry_youtube_call(func, *args, **kwargs):
    """Executa chamada YouTube API com retry exponencial e circuit breaker."""
    for attempt in range(_YOUTUBE_MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            status = e.resp.status if hasattr(e, 'resp') else 0
            if status in (429, 500, 502, 503, 504):
                # Rate limit ou server error: retry com backoff
                wait = _YOUTUBE_BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 1)
                log.warning("YouTube API %s - retry em %ss (tentativa %d/%d)", status, wait, attempt + 1, _YOUTUBE_MAX_RETRIES)
                time.sleep(wait)
                continue
            # Erro nao retryable (4xx exceto 429)
            log.error("YouTube API HTTP %s - nao retryable: %s", status, e)
            raise
        except Exception as e:
            log.warning("YouTube API erro inesperado (tentativa %d/%d): %s", attempt + 1, _YOUTUBE_MAX_RETRIES, e)
            if attempt < _YOUTUBE_MAX_RETRIES - 1:
                wait = _YOUTUBE_BASE_BACKOFF * (2 ** attempt)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("YouTube API: maximo de tentativas excedido sem resposta.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload Pata Jazz para YouTube")
    parser.add_argument("--mode", choices=["upload", "live"], default="upload")
    parser.add_argument("--language", default="pt")
    parser.add_argument("--privacy", default=os.environ.get("YOUTUBE_PRIVACY", "public"))
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
            transition_broadcast(args.broadcast_id, args.transition)
            return 0

        if args.mode == "upload":
            video_id = upload_video(language=args.language, privacy=args.privacy, prefix=args.prefix)
            if not video_id:
                return 1
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
            print(json.dumps(meta, ensure_ascii=False))
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
