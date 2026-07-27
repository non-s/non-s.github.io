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
from datetime import UTC, datetime
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from utils import ffmpeg_helpers
from utils.ai_helper import ai_text, is_safe_ai_text
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
    base = ["Pata Jazz", "cat", "dog", "jazz", "cute", "relaxing"]
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

    if thumbnail and thumbnail.exists():
        try:
            # Re-verifica existencia (TOCTOU) e instancia MediaFileUpload dentro do try.
            thumb_media = MediaFileUpload(str(thumbnail))
            _retry_youtube_call(service.thumbnails().set(videoId=video_id, media_body=thumb_media).execute)
            log.info("Thumbnail aplicada.")
        except Exception as exc:
            # Nao so (HttpError, MediaUploadSizeError): _retry_youtube_call
            # levanta RuntimeError quando esgota as tentativas em erros
            # retryable persistentes (ex: 503 repetido), e isso escapava
            # sem ser pego aqui - derrubando upload_video() inteiro (pulando
            # legenda e playlist) mesmo com o video ja publicado com sucesso
            # (confirmado em producao: run 30155769151, thumbnail falhou
            # apos esgotar retries e o RuntimeError nao pego matou o job,
            # que ficou "failure" apesar do upload ja ter ido ao ar).
            hint = " (canal sem verificacao por telefone bloqueia thumbnail customizada - confira em youtube.com/verify)" if "403" in str(exc) else ""
            log.warning("Falha ao aplicar thumbnail: %s%s", exc, hint)

    # Upload de legenda SRT se existir
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
            # .srt usa mimetype application/x-subrip; .vtt usa text/vtt.
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
            # Ver comentario equivalente no bloco de thumbnail acima.
            log.warning("Falha ao aplicar legenda: %s", exc)

    # Adiciona as playlists automaticas: por formato (kind) e por mood.
    # add_video_to_playlist so adiciona a UMA playlist por chamada (mood tem
    # prioridade se os dois forem passados juntos), entao sao duas chamadas
    # separadas - senao as playlists por mood (PLAYLISTS_BY_MOOD) nunca sao
    # populadas, ja que meta["mood"] nunca era passado antes.
    try:
        from utils.playlist_manager import add_video_to_playlist
        add_video_to_playlist(service, video_id, kind=meta.get("kind", ""))
        if meta.get("mood"):
            add_video_to_playlist(service, video_id, mood=meta["mood"])
    except Exception as exc:
        log.warning("Falha ao adicionar a playlist: %s", exc)

    return video_id


LIVE_VIEWER_HISTORY_FILE = LIVE_META_DIR / "live_viewer_history.json"
_MAX_VIEWER_SNAPSHOTS = 500


def record_live_viewer_snapshot(video_id: str) -> None:
    """Consulta liveStreamingDetails.concurrentViewers e acrescenta um
    snapshot a LIVE_VIEWER_HISTORY_FILE.

    Chamado por run_live.py uma vez por segmento de FFmpeg (a cada poucos
    minutos, ja que segmentos costumam durar so alguns minutos antes de
    reconectar - ver _SEGMENT_WATCHDOG_GRACE_SECONDS em run_live.py) em vez
    de rodar dentro do proprio loop de espera do FFmpeg: assim nao acopla
    uma chamada de API/rede ao watchdog que supervisiona o processo, que ja
    teve historico de causar quedas quando sobrecarregado.

    O id de um liveBroadcast tambem serve como id de video no endpoint
    videos.list (mesma entidade), entao nao precisamos de nenhuma chamada
    extra so para descobrir o video_id.
    """
    try:
        service = get_youtube_service()
        resp = _retry_youtube_call(
            service.videos().list(part="liveStreamingDetails", id=video_id).execute
        )
        items = resp.get("items", [])
        if not items:
            return
        viewers = items[0].get("liveStreamingDetails", {}).get("concurrentViewers")
        if viewers is None:
            return
        viewers = int(viewers)
    except Exception as exc:
        log.warning("Falha ao consultar concurrentViewers da live %s: %s", video_id, exc)
        return

    snapshot = {"collected_at": datetime.now(UTC).isoformat(), "video_id": video_id, "concurrent_viewers": viewers}
    try:
        history = json.loads(LIVE_VIEWER_HISTORY_FILE.read_text(encoding="utf-8")) if LIVE_VIEWER_HISTORY_FILE.exists() else []
    except Exception:
        history = []
    history.append(snapshot)
    history = history[-_MAX_VIEWER_SNAPSHOTS:]
    try:
        LIVE_VIEWER_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        LIVE_VIEWER_HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Falha ao salvar historico de viewers: %s", exc)


def _generate_live_title() -> str:
    # Em ingles: o formato "ambient pet livestream 24/7" e um genero dominado
    # por busca em ingles (ex.: canais como Relax My Dog tem milhoes de
    # inscritos com esse exato formato), com volume de busca muito maior que
    # os equivalentes em portugues para o mesmo conteudo (visual/musical,
    # sem dependencia de idioma).
    prompt = (
        "Create a short, warm YouTube live stream title (max 80 characters) for a "
        "24/7 looping live stream of cats and dogs with relaxing jazz music playing. "
        "Target searches like 'calming music for dogs' or 'relaxing music for cats'. "
        "Return ONLY the title text, no quotes."
    )
    out = ai_text(prompt, task="live_title")
    title = out.strip().replace('"', "") if out else ""
    if title and not is_safe_ai_text(title):
        log.warning("Titulo de live da IA rejeitado (padrao suspeito): %r", title)
        title = ""
    return title or "Pata Jazz 🐾🎷 | Calming Music for Cats & Dogs - 24/7 Live"


LIVE_TAGS = [
    "relaxing music for dogs", "calming music for cats", "jazz for pets",
    "dog anxiety music", "cat sleep music", "music for pets",
    "background music for cats and dogs", "study jazz music",
    "cats and dogs live stream", "24/7 live stream", "Pata Jazz",
]

# Uma sessao normal (run_live.py) dura ate LIVE_DURATION_MINUTES (~320) +
# folga de preparo/limpeza, tudo dentro do timeout-minutes:355 do job. Uma
# margem generosa acima disso (6h) separa "sessao normal ainda rodando" de
# "run crashou sem chamar _end_broadcast" (ex: falha de infra do runner que
# nao da nem chance do bloco finally rodar).
_MAX_ACTIVE_AGE_MINUTES = 360
# 'ready' que nunca virou 'live' em ~20min quase certamente nunca vai virar -
# o proprio run_live.py desiste e chama _end_broadcast bem antes disso
# (wait_for_stream_active tem timeout de 120s).
_MAX_READY_AGE_MINUTES = 20


def _broadcast_age_minutes(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    try:
        published = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(UTC) - published).total_seconds() / 60


def cleanup_orphan_broadcasts(service) -> int:
    """Limpa broadcasts orfaos deixados por uma run anterior que crashou
    sem rodar o finally de run_live.py (_end_broadcast).

    Duas categorias, cada uma com sua propria nocao de "orfao":
    - 'ready' (upcoming) ha mais que _MAX_READY_AGE_MINUTES: nunca foi ao
      ar e nao vai mais - apaga (mesma logica de delete_broadcast).
    - 'active' ha mais que _MAX_ACTIVE_AGE_MINUTES: sessao rodando muito
      alem do esperado - forca transition('complete').

    Nunca levanta excecao: chamado no inicio de create_live_stream() e uma
    falha aqui nao deveria impedir a criacao da nova live.
    """
    cleaned = 0
    try:
        upcoming = _retry_youtube_call(
            service.liveBroadcasts().list(part="id,snippet", broadcastStatus="upcoming", mine=True).execute
        )
        for item in upcoming.get("items", []):
            age = _broadcast_age_minutes(item.get("snippet", {}).get("scheduledStartTime"))
            if age is not None and age > _MAX_READY_AGE_MINUTES:
                log.warning("Broadcast orfao %s preso em 'ready' ha %.0fmin - apagando.", item["id"], age)
                try:
                    delete_broadcast(item["id"])
                    cleaned += 1
                except Exception as exc:
                    log.warning("Falha ao apagar broadcast orfao %s: %s", item["id"], exc)

        active = _retry_youtube_call(
            service.liveBroadcasts().list(part="id,snippet", broadcastStatus="active", mine=True).execute
        )
        for item in active.get("items", []):
            age = _broadcast_age_minutes(item.get("snippet", {}).get("actualStartTime"))
            if age is not None and age > _MAX_ACTIVE_AGE_MINUTES:
                log.warning("Broadcast orfao %s preso em 'active' ha %.0fmin - encerrando.", item["id"], age)
                try:
                    transition_broadcast(item["id"], "complete")
                    cleaned += 1
                except Exception as exc:
                    log.warning("Falha ao encerrar broadcast orfao %s: %s", item["id"], exc)
    except Exception as exc:
        log.warning("Falha ao verificar broadcasts orfaos (nao bloqueia a nova live): %s", exc)

    if cleaned:
        log.info("Limpeza de broadcasts orfaos: %d encerrado(s)/apagado(s).", cleaned)
    return cleaned


_LIVE_STATE_FILE = LIVE_META_DIR / "live_state.json"
# lifeCycleStatus que ainda valem a pena reaproveitar em vez de criar um
# broadcast novo. 'complete' e 'revoked' sao terminais - nunca voltam a
# aceitar video. Os demais (mesmo 'ready'/'created', que run_live.py nunca
# deveria deixar parado por muito tempo gracas a cleanup_orphan_broadcasts)
# ainda podem receber um bind/stream novo de video sem erro.
_RESUMABLE_LIFECYCLE_STATUSES = {"created", "ready", "testStarting", "testing", "liveStarting", "live"}


def _try_resume_existing_broadcast(service) -> dict | None:
    """Tenta reaproveitar o broadcast/stream da sessao anterior (salvo em
    _data/live_state.json por esta mesma funcao) em vez de criar um novo.

    Sem isso, toda sessao do GitHub Actions criava um broadcast do zero -
    mesmo com o encadeamento entre sessoes tendo um gap real de poucos
    minutos (run_live.py so finaliza no fim natural da sessao ou em erro
    irrecuperavel), o broadcast anterior virava VOD e um link novo aparecia
    no canal a cada ~5h20, quebrando a impressao de "1 live que nunca para"
    mesmo com a infraestrutura de CI funcionando corretamente por baixo.

    So reaproveita se o broadcast salvo ainda existir e seu lifeCycleStatus
    nao for terminal - qualquer falha (arquivo ausente/invalido, broadcast
    nao encontrado, stream nao encontrado, erro de rede) cai no fallback
    seguro de criar um broadcast novo, que e exatamente o comportamento de
    antes desta funcao existir.
    """
    if not _LIVE_STATE_FILE.exists():
        return None
    try:
        saved = json.loads(_LIVE_STATE_FILE.read_text(encoding="utf-8"))
        broadcast_id = saved["broadcast_id"]
        stream_id = saved["stream_id"]
    except Exception:
        return None

    try:
        broadcasts = _retry_youtube_call(
            service.liveBroadcasts().list(part="status", id=broadcast_id).execute
        )
        items = broadcasts.get("items", [])
        if not items:
            log.info("Broadcast salvo %s nao existe mais; criando um novo.", broadcast_id)
            return None
        lifecycle = items[0].get("status", {}).get("lifeCycleStatus")
        if lifecycle not in _RESUMABLE_LIFECYCLE_STATUSES:
            log.info("Broadcast salvo %s em lifecycle=%s (terminal); criando um novo.", broadcast_id, lifecycle)
            return None

        streams = _retry_youtube_call(
            service.liveStreams().list(part="cdn", id=stream_id).execute
        )
        stream_items = streams.get("items", [])
        if not stream_items:
            log.info("Stream salvo %s nao existe mais; criando um broadcast novo.", stream_id)
            return None
        stream_name = stream_items[0]["cdn"]["ingestionInfo"]["streamName"]
    except Exception as exc:
        log.info("Falha ao verificar broadcast salvo (%s); criando um novo.", exc)
        return None

    meta = {
        "broadcast_id": broadcast_id,
        "stream_id": stream_id,
        "stream_name": stream_name,
        "ingestion_url": f"rtmp://a.rtmp.youtube.com/live2/{stream_name}",
        "title": saved.get("title", ""),
        "description": saved.get("description", ""),
        "privacy": saved.get("privacy", "public"),
    }
    log.info("Reaproveitando broadcast existente %s (lifecycle=%s) em vez de criar um novo.", broadcast_id, lifecycle)
    return meta


def create_live_stream(
    title: str = "",
    description: str = "",
    privacy: str = "public",
    resolution: str = "1080p",
) -> dict | None:
    service = get_youtube_service()
    cleanup_orphan_broadcasts(service)

    resumed = _try_resume_existing_broadcast(service)
    if resumed:
        _LIVE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LIVE_STATE_FILE.write_text(json.dumps(resumed, ensure_ascii=False, indent=2), encoding="utf-8")
        return resumed

    title = title or _generate_live_title()
    description = description or (
        "A 24/7 live stream of cats and dogs with relaxing jazz music - great "
        "background sound for calming an anxious pet, studying, working or sleeping.\n\n"
        + " ".join(f"#{t.replace(' ', '')}" for t in LIVE_TAGS[:8])
    )

    broadcast_body = {
        "snippet": {
            "title": title,
            "description": description,
            "scheduledStartTime": datetime.now(UTC).isoformat(),
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
            "title": f"Pata Jazz stream {datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
        },
        "cdn": {
            "resolution": resolution,
            # A API rejeita "variable" com HTTP 400 invalidFrameRate (confirmado
            # em producao) - so "resolution" aceita "variable", frameRate exige
            # um valor fixo. "30fps" e apenas metadado/hint para o YouTube; nao
            # precisa bater exatamente com o fps real do encode do FFmpeg.
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
    _LIVE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LIVE_STATE_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Live criada: broadcast=%s stream=%s url=%s", broadcast_id, stream_id, ingestion_url)
    return meta


def transition_broadcast(broadcast_id: str, status: str) -> None:
    service = get_youtube_service()
    _retry_youtube_call(service.liveBroadcasts().transition(id=broadcast_id, part="status", broadcastStatus=status).execute)
    log.info("Broadcast %s transicionado para %s", broadcast_id, status)


def delete_broadcast(broadcast_id: str) -> None:
    """Apaga um broadcast que nunca chegou a ficar 'live'.

    transition(..., 'complete') so e valido a partir de 'testing'/'live';
    chamado sobre um broadcast ainda em 'ready' (stream nunca confirmou
    active) provavelmente tambem 403. Usado como fallback de limpeza para
    nao deixar broadcasts orfaos "ready" acumulando no canal.
    """
    service = get_youtube_service()
    _retry_youtube_call(service.liveBroadcasts().delete(id=broadcast_id).execute)
    log.info("Broadcast %s (nunca ficou ativo) apagado.", broadcast_id)


def wait_for_stream_active(stream_id: str, timeout: int = 90, interval: int = 3) -> bool:
    """Aguarda o liveStream ficar com status.streamStatus == 'active'.

    Confirma que o YouTube esta de fato recebendo video do FFmpeg. Com
    enableAutoStart=True (ver create_live_stream), o proprio YouTube promove
    o broadcast de 'ready' para 'live' assim que isso acontece - nao chame
    transition_broadcast(..., 'testing') nesse fluxo: broadcasts criados com
    enableMonitorStream=False sempre rejeitam a fase de testing (403
    invalidTransition), independente de quando a chamada e feita, pois essa
    fase exige monitor stream habilitado.

    Se a API retornar items vazio repetidamente, o stream_id provavelmente
    esta errado - aborta cedo para nao esperar o timeout inteiro.
    """
    service = get_youtube_service()
    deadline = time.time() + timeout
    empty_count = 0
    while time.time() < deadline:
        response = _retry_youtube_call(
            service.liveStreams().list(part="status", id=stream_id).execute
        )
        items = (response or {}).get("items", [])
        if not items:
            empty_count += 1
            if empty_count >= 3:
                log.error("Stream %s nao encontrado apos %d consultas; abortando.", stream_id, empty_count)
                return False
        else:
            empty_count = 0
            status = items[0].get("status", {}).get("streamStatus")
            if status == "active":
                return True
            log.info("Aguardando stream %s ficar ativo (status atual: %s)...", stream_id, status)
        time.sleep(interval)
    log.error("Stream %s nao ficou ativo apos %ss.", stream_id, timeout)
    return False


def _retry_youtube_call(func, *args, **kwargs):
    """Executa chamada YouTube API com retry e backoff exponencial.

    Sem circuit breaker (ao contrario de utils.ai_helper.ai_text, que tem
    um de verdade para o Gemini) - cada chamada tenta ate _YOUTUBE_MAX_RETRIES
    vezes independente de falhas anteriores nesta run.
    """
    for attempt in range(_YOUTUBE_MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            status = e.resp.status if hasattr(e, 'resp') else 0
            if status in (409, 429, 500, 502, 503, 504):
                # Rate limit, conflito temporario (409) ou erro de servidor: retry com backoff
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
