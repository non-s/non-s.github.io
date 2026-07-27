"""
live_broadcast.py — cria e gerencia transmissões ao vivo (liveBroadcast /
liveStream) no YouTube.

Separado de upload_youtube.py, que agora trata apenas do upload de videos
gravados. Os dois modos compartilham o mesmo cliente OAuth
(utils.youtube_oauth.get_youtube_service) e o mesmo retry
(utils.youtube_retry.retry_youtube_call), mas sao responsabilidades
distintas: este modulo nunca importa MediaFileUpload.

Depende do token OAuth em youtube_token.json ou das variaveis
YOUTUBE_TOKEN / YOUTUBE_CLIENT_SECRET (ver utils.youtube_oauth).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from utils.ai_helper import ai_text, is_safe_ai_text
from utils.channel_config import active_channel
from utils.state_lock import state_lock
from utils.youtube_oauth import get_youtube_service
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

ROOT = Path(__file__).resolve().parent
LIVE_META_DIR = ROOT / "_data"

log = logging.getLogger(__name__)


def _generate_live_title() -> str:
    # Em ingles: o formato "ambient pet livestream 24/7" e um genero dominado
    # por busca em ingles (ex.: canais como Relax My Dog tem milhoes de
    # inscritos com esse exato formato), com volume de busca muito maior que
    # os equivalentes em portugues para o mesmo conteudo (visual/musical,
    # sem dependencia de idioma).
    prompt = active_channel.live_title_prompt
    out = ai_text(prompt, task="live_title")
    title = out.strip().replace('"', "") if out else ""
    if title and not is_safe_ai_text(title):
        log.warning("Titulo de live da IA rejeitado (padrao suspeito): %r", title)
        title = ""
    brand_emoji = active_channel.emojis['brand']
    return title or f"{active_channel.name} {brand_emoji} | Calming Music for Cats & Dogs - 24/7 Live"


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
        with state_lock(_LIVE_STATE_FILE):
            _LIVE_STATE_FILE.write_text(json.dumps(resumed, ensure_ascii=False, indent=2), encoding="utf-8")
        return resumed

    title = title or _generate_live_title()
    description = description or (
        active_channel.default_description + "\n\n"
        + " ".join(f"#{t.replace(' ', '')}" for t in active_channel.live_tags[:8])
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

    broadcast = _retry_youtube_call(
        service.liveBroadcasts().insert(part="snippet,status,contentDetails", body=broadcast_body).execute
    )
    broadcast_id = broadcast["id"]

    stream_body = {
        "snippet": {
            "title": f"{active_channel.name} stream {datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
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

    _retry_youtube_call(
        service.liveBroadcasts().bind(part="id,contentDetails", id=broadcast_id, streamId=stream_id).execute
    )

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
    with state_lock(_LIVE_STATE_FILE):
        _LIVE_STATE_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Live criada: broadcast=%s stream=%s url=%s", broadcast_id, stream_id, ingestion_url)
    return meta


def transition_broadcast(broadcast_id: str, status: str) -> None:
    service = get_youtube_service()
    _retry_youtube_call(
        service.liveBroadcasts().transition(id=broadcast_id, part="status", broadcastStatus=status).execute
    )
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
    with state_lock(LIVE_VIEWER_HISTORY_FILE):
        try:
            history = (
                json.loads(LIVE_VIEWER_HISTORY_FILE.read_text(encoding="utf-8"))
                if LIVE_VIEWER_HISTORY_FILE.exists() else []
            )
        except Exception:
            history = []
        history.append(snapshot)
        history = history[-_MAX_VIEWER_SNAPSHOTS:]
        try:
            LIVE_VIEWER_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            LIVE_VIEWER_HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar historico de viewers: %s", exc)


# Referenciado em main() de upload_youtube.py para que os workflows que
# chamam `python upload_youtube.py --mode live` continuem funcionando sem
# mudanca; os tambem re-exportados por upload_youtube para backward compat
# com scripts/run_live.py e testes que ainda importam de upload_youtube.
__all__ = [
    "LIVE_TAGS",
    "LIVE_VIEWER_HISTORY_FILE",
    "_MAX_ACTIVE_AGE_MINUTES",
    "_MAX_READY_AGE_MINUTES",
    "_MAX_VIEWER_SNAPSHOTS",
    "_RESUMABLE_LIFECYCLE_STATUSES",
    "_LIVE_STATE_FILE",
    "_broadcast_age_minutes",
    "_generate_live_title",
    "_try_resume_existing_broadcast",
    "cleanup_orphan_broadcasts",
    "create_live_stream",
    "delete_broadcast",
    "record_live_viewer_snapshot",
    "transition_broadcast",
    "wait_for_stream_active",
]


