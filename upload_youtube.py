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
import sys
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from utils.ai_helper import ai_text
from utils.youtube_oauth import get_youtube_service

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
LIVE_META_DIR = ROOT / "_data"

log = logging.getLogger(__name__)


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


def _build_tags(scene: str) -> list[str]:
    base = ["Pata Jazz", "gato", "cachorro", "jazz", "fofo", "relaxante"]
    if "cat" in scene or "kitten" in scene:
        base.extend(["gatinho", "cat", "kitten"])
    if "dog" in scene or "puppy" in scene:
        base.extend(["cachorrinho", "dog", "puppy"])
    return list(dict.fromkeys(base))[:15]


def upload_video(language: str = "pt", privacy: str = "public", prefix: str = "pata_jazz_") -> str | None:
    found = _latest_video_meta(prefix=prefix)
    if not found:
        log.error("Nenhum video com metadata encontrado em %s", OUTPUT_DIR)
        return None
    video_path, meta = found

    title = str(meta.get("title", "Pata Jazz"))[:100]
    description = str(meta.get("description", ""))[:5000]
    tags = _build_tags(meta.get("scene", ""))
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
    response = request.execute()
    video_id = response["id"]
    log.info("Video enviado: https://youtu.be/%s", video_id)

    if thumbnail.exists():
        try:
            service.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail))).execute()
            log.info("Thumbnail aplicada.")
        except HttpError as exc:
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

    broadcast = service.liveBroadcasts().insert(part="snippet,status,contentDetails", body=broadcast_body).execute()
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

    stream = service.liveStreams().insert(part="snippet,cdn", body=stream_body).execute()
    stream_id = stream["id"]
    ingestion_info = stream["cdn"]["ingestionInfo"]
    stream_name = ingestion_info["streamName"]
    ingestion_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_name}"

    service.liveBroadcasts().bind(part="id,contentDetails", id=broadcast_id, streamId=stream_id).execute()

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
    service.liveBroadcasts().transition(id=broadcast_id, part="status", broadcastStatus=status).execute()
    log.info("Broadcast %s transicionado para %s", broadcast_id, status)


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

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
        return 1
    except Exception as exc:
        log.exception("Falha no upload: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
