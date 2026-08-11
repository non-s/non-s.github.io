"""
scripts/collect_analytics.py — coleta metricas dos videos do canal Pata Jazz.

Usa a YouTube Data API para buscar views, likes, comentarios e duracao dos
videos recentes. Salva um relatorio em _data/analytics.json para analise.

Este script e disparado por um workflow semanal e alimenta dois feedback
loops com o mesmo mecanismo: cruza video_tags.json (cena/padrao de titulo
que gerou cada video, gravado no upload) com as views coletadas aqui e
grava um peso relativo em scene_performance.json / title_pattern_performance.json,
que utils.content_strategy.scene_for_mood e utils.seo_keywords.pick_title_pattern
usam pra priorizar o que performa melhor na geracao futura (nunca eliminando
as demais opcoes - ver pesos min/max).
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_config import configure_logging
from utils.paths import data_dir, ensure_data_dir
from utils.state_lock import state_lock
from utils.youtube_oauth import get_youtube_analytics_service, get_youtube_service
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

log = logging.getLogger(__name__)

DATA_DIR = data_dir()
ensure_data_dir()
MAX_VIDEOS = 50
HISTORY_FILE = DATA_DIR / "analytics_history.json"
MAX_HISTORY_ENTRIES = 104  # ~2 anos de snapshots semanais
VIDEO_TAGS_FILE = DATA_DIR / "video_tags.json"
SCENE_PERFORMANCE_FILE = DATA_DIR / "scene_performance.json"
_MIN_SCENE_SAMPLES = 3  # cena com poucos videos ainda: peso fica neutro (nao ha o suficiente pra confiar)
# Faixa alargada (era 0.4-2.5): com o piso do Wilson score ja protegendo
# contra amostras pequenas/virais isolados, a faixa anterior deixava o
# feedback loop timido demais - uma cena vencedora ficava so ~6x mais
# provavel que uma perdedora. 0.3-3.0 reage mais rapido ao que realmente
# performa melhor, sem nunca zerar nenhuma opcao.
_MIN_SCENE_WEIGHT = 0.3
_MAX_SCENE_WEIGHT = 3.0

TITLE_PATTERN_PERFORMANCE_FILE = DATA_DIR / "title_pattern_performance.json"
_MIN_TITLE_PATTERN_SAMPLES = 3
_MIN_TITLE_PATTERN_WEIGHT = 0.3
_MAX_TITLE_PATTERN_WEIGHT = 3.0

# Detecao de virais: um video e "viral" se suas views ultrapassam
# _VIRAL_THRESHOLD x a mediana de views do conjunto coletado. Esses sinais
# alimentam viral_signals.json, lido por content_strategy.viral_boosted_scenes
# pra ponderar cenas que geraram virais recentes (ultimos 14 dias). O boost
# e conservador: so aplica se a cena estiver na lista do mood (nao inventa
# cena nova) e multiplica o peso ja existente (nao substitui).
# Caminho isolado por canal via data_dir() (channel isolation).
VIRAL_SIGNALS_FILE = data_dir() / "viral_signals.json"
_VIRAL_THRESHOLD = 8.0

# Thumbnail A/B testing: apos _THUMBNAIL_ROTATION_DAYS dias, se o video
# performar abaixo de _THUMBNAIL_ROTATION_THRESHOLD x a mediana de views do
# canal, troca a thumbnail ativa (variante A) pela variante B via
# thumbnails.set. A YouTube Data API so aceita 1 thumbnail por video (nao
# suporta A/B nativamente); essa rotacao e a alternativa pratica.
_THUMBNAIL_ROTATION_DAYS = 7
_THUMBNAIL_ROTATION_THRESHOLD = 0.5

# A/B testing de TÍTULO: apos _TITLE_ROTATION_DAYS dias, se o video
# performar abaixo de _TITLE_ROTATION_THRESHOLD x a mediana de views e
# ainda estiver com o título original (title_rotated=False), troca o
# título via videos.update para title_alt (gerado no upload e guardado em
# video_tags.json). Diferente de thumbnail (que so tem 3 variantes
# fixas), o título so tem 1 alternativo - depois da rotacao, nao rotaciona
# mais. videos.update custa ~50 unidades de quota (vs 0 de nao fazer
# nada), mas so roda em modo full (semanal) e so para videos abaixo da
# mediana - raramente mais que alguns por run.
_TITLE_ROTATION_DAYS = 5
_TITLE_ROTATION_THRESHOLD = 0.5


def _to_int(value) -> int:
    """Converte string/int/None para int de forma segura."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


# #10: Analytics diferencial - rastreia o ultimo video_id coletado para
# parar de paginar quando nao ha novos videos, economizando quota.
_LAST_COLLECTED_FILE = DATA_DIR / "last_analytics_video_id.json"


def _load_last_collected_video_id() -> str:
    """Le o ultimo video_id coletado (ou '' se nao houver)."""
    try:
        data = json.loads(_LAST_COLLECTED_FILE.read_text(encoding="utf-8"))
        return str(data.get("video_id", "")) if isinstance(data, dict) else ""
    except Exception:
        return ""


def _save_last_collected_video_id(video_id: str) -> None:
    """Salva o ultimo video_id coletado para a proxima run."""
    try:
        _LAST_COLLECTED_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_COLLECTED_FILE.write_text(
            json.dumps({"video_id": video_id, "at": datetime.now(UTC).isoformat()}),
            encoding="utf-8",
        )
    except Exception as exc:
        log.debug("Falha ao salvar last_collected_video_id: %s", exc)


def collect_video_stats(service) -> tuple[list[dict], dict]:
    """Busca estatisticas dos videos mais recentes do canal.

    Retorna (videos, channel_stats) onde channel_stats contem
    subscriberCount, viewCount e videoCount do canal (usado para
    tracking de elegibilidade YPP no dashboard).
    """
    # Primeiro: lista IDs dos videos recentes
    channels = _retry_youtube_call(service.channels().list(part="contentDetails,statistics", mine=True).execute)
    if not channels.get("items"):
        log.error("Nenhum canal encontrado.")
        return [], {}

    channel_id = channels["items"][0]["id"]
    uploads_playlist = channels["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # 3.3 - Coleta estatisticas do canal para tracking de elegibilidade YPP
    # (1k inscritos / 4k horas de watch time nos ultimos 12 meses).
    channel_stats_raw = channels["items"][0].get("statistics", {})
    channel_stats = {
        "subscriber_count": _to_int(channel_stats_raw.get("subscriberCount")),
        "total_views": _to_int(channel_stats_raw.get("viewCount")),
        "video_count": _to_int(channel_stats_raw.get("videoCount")),
    }
    _ = channel_id  # disponível para debug futuro

    # Lista videos da playlist de uploads (com guard contra loop infinito)
    # #10: Analytics diferencial - para de paginar quando encontra o ultimo
    # video ja coletado (last_analytics_video_id.json), economizando quota.
    # Sempre busca pelo menos 20 videos para manter a mediana estavel.
    last_collected_id = _load_last_collected_video_id()
    _MIN_VIDEOS_FOR_MEDIAN = 20
    video_ids: list[str] = []
    page_token = ""
    pages = 0
    stop = False
    while len(video_ids) < MAX_VIDEOS and pages < 20 and not stop:
        pages += 1
        resp = _retry_youtube_call(
            service.playlistItems()
            .list(
                part="snippet",
                playlistId=uploads_playlist,
                maxResults=50,
                pageToken=page_token,
            )
            .execute
        )
        if not resp.get("items"):
            break
        for item in resp.get("items", []):
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                video_ids.append(vid)
                # #10: para quando encontra o ultimo coletado E ja tem
                # videos suficientes para a mediana (>=20).
                if last_collected_id and vid == last_collected_id and len(video_ids) >= _MIN_VIDEOS_FOR_MEDIAN:
                    stop = True
                    break
        if not stop:
            page_token = resp.get("nextPageToken") or ""
            if not page_token:
                break

    # #10: salva o video mais recente como o novo "ultimo coletado"
    if video_ids:
        _save_last_collected_video_id(video_ids[0])

    if not video_ids:
        log.info("Nenhum video encontrado.")
        return [], channel_stats

    # Busca estatisticas detalhadas
    stats: list[dict] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = _retry_youtube_call(
            service.videos()
            .list(
                part="statistics,snippet,contentDetails",
                id=",".join(batch),
            )
            .execute
        )
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content = item.get("contentDetails", {})
            stats.append(
                {
                    "video_id": item["id"],
                    "title": snippet.get("title", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "duration": content.get("duration", ""),
                    "views": _to_int(statistics.get("viewCount")),
                    "likes": _to_int(statistics.get("likeCount")),
                    "comments": _to_int(statistics.get("commentCount")),
                }
            )

    return stats, channel_stats


def _collect_retention_metrics(service, video_ids: list[str]) -> dict:
    """Consulta o YouTube Analytics API por retention/CTR/impressions dos video_ids.

    Busca `averageViewDuration`, `averageViewPercentage` (retention), `ctr`,
    `impressions` e `subscribersGained` via
    `youtubeAnalytics.reports().query(ids='channel==mine', ...)`. A API so
    permite filtrar por um video por vez em `filters==video==<id>`, entao faz
    uma chamada por video (MAX_VIDEOS no maximo - dentro do budget do Analytics
    API, separado da Data API v3).

    Retorna um dict {video_id: {averageViewDuration, averageViewPercentage,
    ctr, impressions, subscribersGained}}. Em qualquer erro (403 por scope
    ausente, canal inelegivel, API indisponivel), loga warning e retorna {} -
    a Analytics API pode nao estar disponivel para todos os canais (ex.:
    canal novo sem dados suficientes), e isso nao deve derrubar o resto da
    coleta.

    `service` e o Resource do youtubeAnalytics v2 (ver
    get_youtube_analytics_service); passamos como argumento para permitir
    injecao em testes sem construir credenciais reais.
    """
    if not video_ids:
        return {}
    # Janela de 90 dias ate hoje: a Analytics API exige startDate/endDate e
    # nao aceita intervalo aberto. 90 dias cobre a janela dos videos recentes
    # (MAX_VIDEOS=50) sem inflar demais o numero de chamadas.
    end = datetime.now(UTC).date()
    start = end - timedelta(days=90)
    # Metricas validas na YouTube Analytics API v2 (targeted queries).
    # Ver: https://developers.google.com/youtube/analytics/metrics
    #
    # IMPORTANTE: a Analytics API v2 (targeted queries / reports.query) usa
    # nomes DIFERENTES da Reporting API (bulk reports). Tentativas anteriores
    # usaram "ctr", "impressions", "videoThumbnailImpressions" e
    # "videoThumbnailImpressionsCtr" — nenhum desses existe na Analytics API
    # v2 (sao da Reporting API) e todos retornavam 400 "Unknown identifier".
    #
    # Metricas disponiveis na Analytics API v2 para filtragem por video:
    # - averageViewDuration: duracao media (segundos) - core
    # - averageViewPercentage: % media assistida - core
    # - subscribersGained: inscritos ganhos - core
    # - likes: likes - core
    # - comments: comentarios - core
    # - estimatedMinutesWatched: minutos assistidos - core
    #
    # CTR de thumbnail e impressoes NAO estao disponiveis na Analytics API
    # v2 (só na Reporting API bulk, que usa um endpoint diferente).
    _METRICS = (
        "averageViewDuration,averageViewPercentage,"
        "subscribersGained,likes,comments,estimatedMinutesWatched"
    )
    _METRIC_KEYS = [
        "averageViewDuration",
        "averageViewPercentage",
        "subscribersGained",
        "likes",
        "comments",
        "estimatedMinutesWatched",
    ]
    result: dict[str, dict] = {}
    for vid in video_ids:
        try:
            resp = _retry_youtube_call(
                service.reports()
                .query(
                    ids="channel==mine",
                    startDate=start.isoformat(),
                    endDate=end.isoformat(),
                    metrics=_METRICS,
                    filters=f"video=={vid}",
                )
                .execute
            )
        except Exception as exc:
            # 403 (scope ausente / canal inelegivel) ou outro erro da API -
            # Analytics nao esta disponivel para todos os canais; nao e fatal.
            log.warning(
                "_collect_retention_metrics: Analytics indisponivel para %s: %s",
                vid,
                exc,
            )
            continue
        rows = resp.get("rows", []) if isinstance(resp, dict) else []
        if not rows:
            continue
        # rows e lista de listas; a ordem dos valores segue a ordem de metrics.
        row = rows[0]
        if len(row) >= len(_METRIC_KEYS):
            metrics = {key: float(row[i]) for i, key in enumerate(_METRIC_KEYS)}
            result[vid] = metrics
    if result:
        log.info("Retencion/CTR/impressions coletados para %d videos.", len(result))
    return result


def _load_video_tags() -> dict:
    try:
        return json.loads(VIDEO_TAGS_FILE.read_text(encoding="utf-8")) if VIDEO_TAGS_FILE.exists() else {}
    except Exception:
        return {}


def _record_thumbnail_variant_in_stats(stats: list[dict], video_tags: dict) -> list[dict]:
    """Mescla `thumbnail_variant` (de video_tags.json) em cada stat dict.

    Fechar o loop de feedback de variante de thumbnail: quando um video
    depois tem views altas, queremos saber qual variante estava ativa no
    momento da coleta (A/B/C). O valor vem de video_tags[video_id]
    ["thumbnail_variant"] (gravado no upload e atualizado por
    maybe_rotate_thumbnail); ausente = "A" (default de upload).

    Retorna uma NOVA lista de stats (nao muta a original) para evitar
    efeitos colaterais em callers que reutilizam `stats`.
    """
    enriched: list[dict] = []
    for video in stats:
        tag = video_tags.get(video["video_id"])
        variant = "A"
        if isinstance(tag, dict):
            variant = str(tag.get("thumbnail_variant", "A") or "A")
        enriched.append({**video, "thumbnail_variant": variant})
    return enriched


def _save_video_tags(tags: dict) -> None:
    """Salva o mapeamento video_tags.json atomico (state_lock) - usado por
    maybe_rotate_thumbnail pra marcar thumbnail_variant="B" apos trocar."""
    with state_lock(VIDEO_TAGS_FILE):
        try:
            VIDEO_TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            VIDEO_TAGS_FILE.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar video_tags: %s", exc)


def _median_views(stats: list[dict]) -> float:
    """Mediana de views do conjunto de videos coletados. Usada como baseline
    para decidir se um video esta 'abaixo da mediana' e merece rotacao de
    thumbnail."""
    views = sorted(v["views"] for v in stats if "views" in v)
    if not views:
        return 0.0
    mid = len(views) // 2
    if len(views) % 2 == 1:
        return float(views[mid])
    return (views[mid - 1] + views[mid]) / 2


def maybe_rotate_thumbnail(
    service,
    video_id: str,
    video_tags_entry: dict,
    *,
    median_views: float = 0.0,
    now: datetime | None = None,
) -> bool:
    """Rotaciona a thumbnail de um video pela sequencia A -> B -> C se o
    video performar abaixo de _THUMBNAIL_ROTATION_THRESHOLD x a mediana apos
    _THUMBNAIL_ROTATION_DAYS dias.

    A YouTube Data API v3 `thumbnails.set` aceita apenas 1 thumbnail por
    chamada e sobrescreve a anterior - nao suporta A/B nativamente. Esta
    rotacao e a alternativa pratica: publica A no upload, e se apos N dias o
    video nao decolar, troca para B (paleta/impacto diferentes) e marca
    `thumbnail_variant: "B"` no video_tags.json; se ainda assim continuar
    underperforming apos mais _THUMBNAIL_ROTATION_DAYS dias, troca para C
    (emoji gigante, hook truncado) e marca `thumbnail_variant: "C"`.

    Retorna True se trocou, False caso contrario (ja e C/ultima variante,
    nao tem proxima variante, < N dias, ou views ainda acima do threshold).
    """
    current_variant = video_tags_entry.get("thumbnail_variant", "A")
    # Sequencia de rotacao A -> B -> C. Se ja estamos na ultima, nao rotaciona.
    sequence = ["A", "B", "C"]
    try:
        idx = sequence.index(current_variant)
    except ValueError:
        idx = 0
    if idx >= len(sequence) - 1:
        return False

    thumbnails = video_tags_entry.get("thumbnails") or []
    next_variant = sequence[idx + 1]
    # A proxima variante precisa estar na lista de thumbnails gravadas. Indexa
    # pela posicao na sequencia (0=A, 1=B, 2=C).
    next_index = idx + 1
    if len(thumbnails) <= next_index:
        return False

    now = now or datetime.now(UTC)
    # Para a primeira rotacao (A->B), conta desde uploaded_at; para B->C,
    # conta desde a ultima rotacao (rotated_at gravado quando A->B ocorreu).
    rotation_anchor_field = "rotated_at" if current_variant != "A" else "uploaded_at"
    anchor = video_tags_entry.get(rotation_anchor_field) or video_tags_entry.get("uploaded_at")
    if anchor:
        try:
            anchor_dt = datetime.fromisoformat(anchor)
        except Exception:
            anchor_dt = None
        if anchor_dt is not None:
            age = now - anchor_dt
            if age < timedelta(days=_THUMBNAIL_ROTATION_DAYS):
                return False

    if median_views <= 0:
        return False
    views = _to_int(video_tags_entry.get("views"))
    if views >= median_views * _THUMBNAIL_ROTATION_THRESHOLD:
        return False

    # A proxima thumbnail e a variante seguinte (index next_index).
    thumb_next = Path(thumbnails[next_index])
    if not thumb_next.exists():
        log.warning(
            "maybe_rotate_thumbnail: variante %s ausente (%s) para %s",
            next_variant,
            thumb_next,
            video_id,
        )
        return False

    try:
        _retry_youtube_call(
            service.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumb_next))).execute
        )
    except Exception as exc:
        log.warning("maybe_rotate_thumbnail: falha ao trocar thumbnail de %s: %s", video_id, exc)
        return False

    log.info(
        "Thumbnail de %s rotacionada %s->%s (views=%d < %.1f%% da mediana %.0f).",
        video_id,
        current_variant,
        next_variant,
        views,
        _THUMBNAIL_ROTATION_THRESHOLD * 100,
        median_views,
    )
    video_tags_entry["thumbnail_variant"] = next_variant
    video_tags_entry["rotated_at"] = now.isoformat()
    return True


def maybe_rotate_title(
    service,
    video_id: str,
    video_tags_entry: dict,
    *,
    median_views: float = 0.0,
    now: datetime | None = None,
) -> bool:
    """Rotaciona o título de um vídeo para title_alt (A/B testing) se o
    vídeo performar abaixo de _TITLE_ROTATION_THRESHOLD x a mediana apos
    _TITLE_ROTATION_DAYS dias desde o upload.

    Diferente da rotação de thumbnail (que tem 3 variantes e pode
    rotacionar A->B->C), o título tem apenas 1 alternativo: depois da
    rotacao, title_rotated=True e a funcao nao rotaciona mais.

    Pré-requisitos para rotacionar:
    - title_alt nao vazio (gerado no upload; alguns vídeos podem nao ter).
    - title_rotated != True (ainda nao rotacionado).
    - idade >= _TITLE_ROTATION_DAYS desde uploaded_at.
    - views < median_views * _TITLE_ROTATION_THRESHOLD.

    Usa videos.update (part=snippet) para trocar o título - custa ~50
    unidades de quota do pool compartilhado, bem abaixo do limite.

    Retorna True se trocou, False caso contrario.
    """
    if video_tags_entry.get("title_rotated"):
        return False
    title_alt = video_tags_entry.get("title_alt")
    if not title_alt or not isinstance(title_alt, str) or not title_alt.strip():
        return False

    now = now or datetime.now(UTC)
    anchor = video_tags_entry.get("uploaded_at")
    if anchor:
        try:
            anchor_dt = datetime.fromisoformat(anchor)
        except Exception:
            anchor_dt = None
        if anchor_dt is not None:
            age = now - anchor_dt
            if age < timedelta(days=_TITLE_ROTATION_DAYS):
                return False

    if median_views <= 0:
        return False
    views = _to_int(video_tags_entry.get("views"))
    if views >= median_views * _TITLE_ROTATION_THRESHOLD:
        return False

    # Pega o snippet atual para preservar categoryId/tags/description e so
    # trocar o title - videos.update exige o snippet completo (senao
    # apaga campos nao enviados).
    try:
        resp = _retry_youtube_call(
            service.videos().list(part="snippet", id=video_id).execute
        )
        items = resp.get("items", []) if isinstance(resp, dict) else []
        if not items:
            log.warning("maybe_rotate_title: vídeo %s não encontrado.", video_id)
            return False
        snippet = items[0].get("snippet", {})
        snippet["title"] = title_alt[:100]
        _retry_youtube_call(
            service.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}).execute
        )
    except Exception as exc:
        log.warning("maybe_rotate_title: falha ao trocar título de %s: %s", video_id, exc)
        return False

    log.info(
        "Título de %s rotacionado para alt (%d views < %.1f%% da mediana %.0f).",
        video_id,
        views,
        _TITLE_ROTATION_THRESHOLD * 100,
        median_views,
    )
    video_tags_entry["title_rotated"] = True
    video_tags_entry["title_rotated_at"] = now.isoformat()
    video_tags_entry["title"] = title_alt
    return True


def _load_scene_performance() -> dict[str, float]:
    try:
        return json.loads(SCENE_PERFORMANCE_FILE.read_text(encoding="utf-8")) if SCENE_PERFORMANCE_FILE.exists() else {}
    except Exception:
        return {}


def _load_title_pattern_performance() -> dict[str, float]:
    try:
        return (
            json.loads(TITLE_PATTERN_PERFORMANCE_FILE.read_text(encoding="utf-8"))
            if TITLE_PATTERN_PERFORMANCE_FILE.exists()
            else {}
        )
    except Exception:
        return {}


def _performance_signal(video: dict, now: datetime | None = None) -> float:
    """Retorna um sinal comparável entre vídeos de idades e retenções diferentes.

    Views acumuladas favorecem automaticamente vídeos antigos. O feedback loop
    precisa comparar velocidade de visualizações e dar uma vantagem moderada à
    retenção, sem depender de CTR (que não existe para todas as superfícies de
    Shorts). Registros legados sem data/retencao preservam o comportamento de
    views brutas para não descartar o histórico já coletado.
    """
    views = float(_to_int(video.get("views")))
    if views <= 0:
        return 0.0

    published_raw = str(video.get("published_at", "")).strip()
    if published_raw:
        try:
            value = published_raw[:-1] + "+00:00" if published_raw.endswith("Z") else published_raw
            published = datetime.fromisoformat(value)
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            age_days = max(1.0, ((now or datetime.now(UTC)) - published.astimezone(UTC)).total_seconds() / 86400)
            views /= age_days
        except (TypeError, ValueError):
            pass

    try:
        retention = float(video.get("averageViewPercentage", 0) or 0)
    except (TypeError, ValueError):
        retention = 0.0
    if retention > 0:
        # A API retorna percentual (0-100); aceitar 0-1 deixa fixtures legadas
        # e integrações que já normalizam a métrica funcionarem também.
        retention_ratio = retention / 100 if retention > 1 else retention
        retention_ratio = max(0.0, min(1.5, retention_ratio))
        views *= 0.75 + 0.25 * retention_ratio
    return views


def _compute_weighted_performance(
    stats: list[dict],
    video_tags: dict,
    tag_key: str,
    min_samples: int,
    min_weight: float,
    max_weight: float,
) -> dict[str, float]:
    """Calcula um peso relativo por valor de tag_key (ex: 'scene' ou
    'title_pattern' em video_tags.json) a partir de velocidade de views e
    retenção quando disponíveis.

    upload_youtube.py::_record_video_tags grava, por video_id, qual valor
    gerou o video; aqui cruzamos isso com as views desse video_id pra saber
    o que performa melhor que a media. video_tags so tem os uploads mais
    recentes (_MAX_VIDEO_TAGS), entao videos antigos sem tag no mapeamento
    sao ignorados no calculo - nao ha problema, o peso e so uma tendencia
    recente, nao um historico completo.

    Peso 1.0 = na media. >1.0 = performa acima da media (mais provavel de
    ser escolhido de volta). Limitado a [min_weight, max_weight] pra nunca
    zerar nem monopolizar uma opcao so por causa de uma amostra pequena ou
    um video viral isolado.

    Usa o lower bound do Wilson score interval (95% confianca) sobre a
    proporcao de videos acima da mediana geral: mais conservador que a
    media simples com amostras pequenas - um viral isolado nao infla o
    peso de uma cena inconsistente.
    """
    views_by_key: dict[str, list[float]] = {}
    for video in stats:
        tag = video_tags.get(video["video_id"])
        key = tag.get(tag_key) if tag else ""
        if not key:
            continue
        views_by_key.setdefault(key, []).append(_performance_signal(video))

    all_views = [v for views in views_by_key.values() for v in views]
    if not all_views:
        return {}
    if sum(all_views) <= 0:
        return {}
    all_views_sorted = sorted(all_views)
    mid = len(all_views_sorted) // 2
    if len(all_views_sorted) % 2 == 1:
        median: float = float(all_views_sorted[mid])
    else:
        median = (all_views_sorted[mid - 1] + all_views_sorted[mid]) / 2

    z = 1.96
    raw_lower_bounds: dict[str, float] = {}
    for key, views in views_by_key.items():
        n = len(views)
        if n < min_samples:
            continue
        successes = sum(1 for v in views if v > median)
        p = successes / n
        denom = 1 + z * z / n
        lower = (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
        raw_lower_bounds[key] = lower

    if not raw_lower_bounds:
        return {}
    avg_lower = sum(raw_lower_bounds.values()) / len(raw_lower_bounds)

    weights: dict[str, float] = {}
    for key, lower in raw_lower_bounds.items():
        weight = lower / avg_lower if avg_lower > 0 else 1.0
        weights[key] = max(min_weight, min(max_weight, weight))

    return weights


def _compute_scene_performance(stats: list[dict], video_tags: dict) -> dict[str, float]:
    """Calcula um peso relativo por cena a partir das views reais coletadas
    (ver content_strategy.scene_for_mood). Generalizacao em
    _compute_weighted_performance."""
    return _compute_weighted_performance(
        stats, video_tags, "scene", _MIN_SCENE_SAMPLES, _MIN_SCENE_WEIGHT, _MAX_SCENE_WEIGHT
    )


def _compute_title_pattern_performance(stats: list[dict], video_tags: dict) -> dict[str, float]:
    """Calcula um peso relativo por padrao de titulo a partir das views
    reais coletadas (ver seo_keywords.pick_title_pattern). Generalizacao em
    _compute_weighted_performance."""
    return _compute_weighted_performance(
        stats,
        video_tags,
        "title_pattern",
        _MIN_TITLE_PATTERN_SAMPLES,
        _MIN_TITLE_PATTERN_WEIGHT,
        _MAX_TITLE_PATTERN_WEIGHT,
    )


def detect_viral_videos(
    stats: list[dict],
    video_tags: dict,
    *,
    threshold: float = _VIRAL_THRESHOLD,
    now: datetime | None = None,
) -> list[dict]:
    """Detecta videos "virais": aqueles cujas views excedem `threshold` x a
    mediana de views do conjunto coletado.

    Cruza stats (views por video_id) com video_tags (scene/title_pattern que
    gerou cada video) e devolve uma lista de sinais para viral_signals.json:

        [{"video_id": ..., "scene": ..., "title_pattern": ..., "views": N,
          "viral_factor": 12.5, "detected_at": "iso", "ctr": 0.05, "avp": 0.55}]

    `viral_factor` e a razao views/mediana (quanto acima da mediana o video
    esta). A mediana e calculada sobre todas as views em `stats` (mesmo as
    sem tag), pra evitar que um conjunto so de virais eleve o baseline e
    mascara a deteccao. Videos sem tag (fora do mapeamento video_tags) ainda
    sao detectados como virais, mas com scene/title_pattern vazios - o boost
    de cena so se aplica quando a tag existe.

    Retencao/CTR do video (quando presentes em stats, enriquecidos por
    _collect_retention_metrics) sao copiados para o sinal viral, permitindo
    comparar nao so "quem bombou" mas "quem reteve/converteu melhor".
    """
    median = _median_views(stats)
    if median <= 0:
        return []
    now = now or datetime.now(UTC)
    virals: list[dict] = []
    for video in stats:
        views = _to_int(video.get("views"))
        if views <= 0:
            continue
        factor = views / median
        if factor <= threshold:
            continue
        tag = video_tags.get(video["video_id"]) or {}
        signal: dict = {
            "video_id": video["video_id"],
            "scene": tag.get("scene", "") if isinstance(tag, dict) else "",
            "title_pattern": tag.get("title_pattern", "") if isinstance(tag, dict) else "",
            "views": views,
            "viral_factor": round(factor, 3),
            "detected_at": now.isoformat(),
        }
        if "ctr" in video:
            signal["ctr"] = video["ctr"]
        if "averageViewPercentage" in video:
            signal["avp"] = video["averageViewPercentage"]
        virals.append(signal)
    return virals


def _save_viral_signals(virals: list[dict], path: Path | None = None) -> None:
    """Grava a lista de sinais virais em viral_signals.json (atomico via
    state_lock). Sobrescreve a cada run: o conjunto e recalculado a partir
    das views atuais, entao virais antigos que perderam forca saem naturalmente."""
    out_path = path if path is not None else VIRAL_SIGNALS_FILE
    with state_lock(out_path):
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(virals, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("Sinais virais salvos: %s (%d virais)", out_path, len(virals))
        except Exception as exc:
            log.warning("Falha ao salvar sinais virais: %s", exc)


def _parse_iso8601_duration(duration: str) -> float:
    """Converte duracao ISO 8601 do YouTube (ex: 'PT1M30S', 'PT2H') em segundos.

    Retorna 0.0 para valores vazios/invalidos. Usada para estimar watch time
    real no tracking de elegibilidade YPP em vez de assumir 30s para tudo.
    """
    if not duration:
        return 0.0
    import re

    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration.strip())
    if not m:
        return 0.0
    hours, minutes, seconds = (int(g) if g else 0 for g in m.groups())
    return float(hours * 3600 + minutes * 60 + seconds)


def _ypp_eligibility(channel_stats: dict, video_stats: list[dict]) -> dict:
    """Calcula o progresso do canal em direcao a elegibilidade YPP.

    Requisitos YPP (YouTube Partner Program):
    - 1.000 inscritos
    - 4.000 horas de watch time nos ultimos 12 meses
    (ou 10M views de Shorts em 90 dias - alternativa nao calculavel aqui).

    Retorna {subscribers, subscriber_progress, watch_hours_estimate,
    watch_hours_progress, eligible, missing}.
    """
    subs = channel_stats.get("subscriber_count", 0)
    total_views = channel_stats.get("total_views", 0)
    # Estimativa de watch time: total_views * duracao_media real dos videos
    # coletados (parseada do ISO 8601 do YouTube). Sem a Analytics API (que
    # daria o valor exato), a media de duracao dos videos e o melhor proxy.
    avg_duration_seconds = 0.0
    if video_stats:
        durations = [_parse_iso8601_duration(v.get("duration", "")) for v in video_stats]
        durations = [d for d in durations if d > 0]
        if durations:
            avg_duration_seconds = sum(durations) / len(durations)
    watch_hours_estimate = (total_views * avg_duration_seconds) / 3600.0
    return {
        "subscribers": subs,
        "subscriber_progress": min(1.0, subs / 1000.0),
        "watch_hours_estimate": int(watch_hours_estimate),
        "watch_hours_progress": min(1.0, watch_hours_estimate / 4000.0),
        "eligible": subs >= 1000 and watch_hours_estimate >= 4000,
        "subscriber_target": 1000,
        "watch_hours_target": 4000,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    configure_logging()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Coleta analytics do canal Pata Jazz")
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Modo leve diario: coleta so stats + channel stats e grava o "
        "historico. Pula a computacao pesada de cena/title_pattern e a "
        "rotacao de thumbnails (~2 min em vez de ~10).",
    )
    args = parser.parse_args(argv)

    try:
        service = get_youtube_service()
    except Exception as exc:
        log.error("Erro ao autenticar YouTube: %s", exc)
        return 1

    try:
        stats, channel_stats = collect_video_stats(service)
    except Exception as exc:
        # collect_video_stats ja usa _retry_youtube_call (retry+backoff) em
        # cada chamada - chegar aqui significa que esgotou as tentativas
        # (ex: erro nao-retryable ou instabilidade persistente). Falha
        # graciosa em vez de traceback nao tratado derrubando o workflow.
        log.error("Falha ao coletar estatisticas do YouTube: %s", exc)
        return 1
    if not stats:
        log.warning("Nenhum dado coletado.")
        return 0

    # Ordena por views (desc)
    stats.sort(key=lambda v: v["views"], reverse=True)

    # Fechar o loop de variante de thumbnail: registra qual variante (A/B/C)
    # estava ativa no momento da coleta, lendo video_tags.json. Assim, quando
    # um video depois tem views altas, vemos qual variante gerou a performance.
    video_tags = _load_video_tags()
    stats = _record_thumbnail_variant_in_stats(stats, video_tags)

    # Estatisticas agregadas
    total_views = sum(v["views"] for v in stats)
    total_likes = sum(v["likes"] for v in stats)
    total_comments = sum(v["comments"] for v in stats)

    report = {
        "collected_at": datetime.now(UTC).isoformat(),
        "total_videos": len(stats),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "avg_views": total_views // len(stats) if stats else 0,
        "top_10": stats[:10],
        "bottom_10": stats[-10:] if len(stats) > 10 else [],
        "all_videos": stats,
        # 3.3 - Tracking de elegibilidade YPP (1k inscritos / 4k horas).
        "channel_stats": channel_stats,
        "ypp_eligibility": _ypp_eligibility(channel_stats, stats),
    }

    out_path = DATA_DIR / "analytics.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Analytics salvo: %s (%d videos, %d views total)", out_path, len(stats), total_views)

    _append_history(report)

    # Modo snapshot-only: so coleta stats + historico. Pula a computacao
    # pesada de cena/title_pattern, deteccao de virais e rotacao de
    # thumbnails - rodando diariamente (06:00 UTC) alimenta um historico
    # mais fino pro predict_views sem gastar quota nem tempo de CI.
    if args.snapshot_only:
        log.info(
            "Modo snapshot-only: pulando computacao de cena/title_pattern, deteccao de virais e rotacao de thumbnails."
        )
        return 0

    scene_weights = _compute_scene_performance(stats, video_tags)
    if scene_weights:
        _update_scene_performance(scene_weights)

    title_pattern_weights = _compute_title_pattern_performance(stats, video_tags)
    if title_pattern_weights:
        _update_title_pattern_performance(title_pattern_weights)

    # YouTube Analytics API: retencao (averageViewDuration /
    # averageViewPercentage) e CTR. So roda em modo full (nao snapshot-only)
    # pois exige um service separado (youtubeAnalytics v2) e pode nao estar
    # disponivel para todos os canais - em caso de erro, segue sem gravar o
    # bloco retention_metrics (nao e fatal).
    video_ids = [v["video_id"] for v in stats]
    try:
        analytics_service = get_youtube_analytics_service()
    except Exception as exc:
        log.warning("Analytics indisponivel (autenticacao): %s", exc)
        analytics_service = None
    if analytics_service is not None:
        retention = _collect_retention_metrics(analytics_service, video_ids)
        if retention:
            report["retention_metrics"] = retention
            # Enriquece all_videos/top_10/bottom_10 com as metricas de
            # retention, CTR, impressions e subscribersGained para o dashboard
            # e para o feedback loop de thumbnail/titulo/cena.
            enriched_stats = []
            for video in stats:
                enriched = dict(video)
                metrics = retention.get(video["video_id"], {})
                enriched.update(metrics)
                enriched_stats.append(enriched)
            stats = enriched_stats
            report["all_videos"] = stats
            report["top_10"] = stats[:10]
            report["bottom_10"] = stats[-10:] if len(stats) > 10 else []
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Detecao de virais: apos computar performance por cena/title_pattern,
    # identifica videos cujas views excedem _VIRAL_THRESHOLD x a mediana e
    # grava sinais em viral_signals.json. content_strategy.viral_boosted_scenes
    # le isso pra ponderar cenas que geraram virais recentes.
    virals = detect_viral_videos(stats, video_tags)
    _save_viral_signals(virals)

    # Thumbnail A/B/C rotation: videos elegiveis (>=2 variantes, >=7 dias desde
    # o upload ou desde a ultima rotacao, abaixo da mediana) tem a thumbnail
    # trocada para a proxima variante da sequencia A->B->C. So roda se houver
    # videos com variantes registradas no video_tags; caso contrario e no-op.
    views_by_id = {v["video_id"]: v["views"] for v in stats}
    median = _median_views(stats)
    rotated_any = False
    for vid, entry in video_tags.items():
        if not isinstance(entry, dict):
            continue
        if len(entry.get("thumbnails") or []) < 2:
            continue
        entry_with_views = {**entry, "views": views_by_id.get(vid, 0)}
        if maybe_rotate_thumbnail(service, vid, entry_with_views, median_views=median):
            # entry_with_views e uma copia; atualiza a entrada real e persiste.
            entry["thumbnail_variant"] = entry_with_views.get("thumbnail_variant", "B")
            if "rotated_at" in entry_with_views:
                entry["rotated_at"] = entry_with_views["rotated_at"]
            rotated_any = True

    # A/B testing de TÍTULO: videos com title_alt e views < mediana apos
    # _TITLE_ROTATION_DAYS dias tem o título trocado por title_alt via
    # videos.update. So roda uma vez por vídeo (title_rotated=True apos).
    title_rotated_any = False
    for vid, entry in video_tags.items():
        if not isinstance(entry, dict):
            continue
        entry_with_views = {**entry, "views": views_by_id.get(vid, 0)}
        if maybe_rotate_title(service, vid, entry_with_views, median_views=median):
            entry["title_rotated"] = entry_with_views.get("title_rotated", True)
            if "title_rotated_at" in entry_with_views:
                entry["title_rotated_at"] = entry_with_views["title_rotated_at"]
            if "title" in entry_with_views:
                entry["title"] = entry_with_views["title"]
            title_rotated_any = True
    if rotated_any or title_rotated_any:
        _save_video_tags(video_tags)

    return 0


def _append_history(report: dict) -> None:
    """Acrescenta um snapshot compacto (so os agregados, nao all_videos) ao
    historico - analytics.json sozinho sobrescreve toda semana, entao sem
    isso nao da pra ver tendencia nenhuma ao longo do tempo depois."""
    snapshot = {
        "collected_at": report["collected_at"],
        "total_videos": report["total_videos"],
        "total_views": report["total_views"],
        "total_likes": report["total_likes"],
        "total_comments": report["total_comments"],
        "avg_views": report["avg_views"],
    }
    with state_lock(HISTORY_FILE):
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8")) if HISTORY_FILE.exists() else []
        except Exception:
            history = []
        history.append(snapshot)
        history = history[-MAX_HISTORY_ENTRIES:]
        try:
            HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("Historico de analytics atualizado: %s (%d snapshots)", HISTORY_FILE, len(history))
        except Exception as exc:
            log.warning("Falha ao salvar historico de analytics: %s", exc)


def _update_scene_performance(scene_weights: dict[str, float]) -> None:
    """Grava scene_weights em SCENE_PERFORMANCE_FILE, mesclando com o
    conteudo ja existente em vez de sobrescrever.

    Com MAX_VIDEOS=50 dividido entre as ~11 cenas possiveis, e comum uma
    cena cair abaixo de _MIN_SCENE_SAMPLES so por azar de amostragem numa
    semana especifica - sobrescrever o arquivo inteiro apagaria o peso ja
    calculado dessa cena (revertendo pra neutro) em vez de so manter o
    ultimo valor confiavel ate a proxima amostra suficiente.
    """
    merged = {**_load_scene_performance(), **scene_weights}
    with state_lock(SCENE_PERFORMANCE_FILE):
        try:
            SCENE_PERFORMANCE_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("Performance por cena atualizada: %s (%d cenas)", SCENE_PERFORMANCE_FILE, len(merged))
        except Exception as exc:
            log.warning("Falha ao salvar performance por cena: %s", exc)


def _update_title_pattern_performance(title_pattern_weights: dict[str, float]) -> None:
    """Grava title_pattern_weights em TITLE_PATTERN_PERFORMANCE_FILE,
    mesclando com o conteudo ja existente em vez de sobrescrever - mesmo
    raciocinio de _update_scene_performance (um padrao pode cair abaixo de
    _MIN_TITLE_PATTERN_SAMPLES so por azar de amostragem numa semana
    especifica, e sobrescrever apagaria o peso ja calculado dele).
    """
    merged = {**_load_title_pattern_performance(), **title_pattern_weights}
    with state_lock(TITLE_PATTERN_PERFORMANCE_FILE):
        try:
            TITLE_PATTERN_PERFORMANCE_FILE.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            log.info(
                "Performance por padrao de titulo atualizada: %s (%d padroes)",
                TITLE_PATTERN_PERFORMANCE_FILE,
                len(merged),
            )
        except Exception as exc:
            log.warning("Falha ao salvar performance por padrao de titulo: %s", exc)


if __name__ == "__main__":
    sys.exit(main())
