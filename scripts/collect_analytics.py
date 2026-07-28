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
from utils.state_lock import state_lock
from utils.youtube_oauth import get_youtube_service
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

log = logging.getLogger(__name__)

DATA_DIR = ROOT / "_data"
MAX_VIDEOS = 50
HISTORY_FILE = DATA_DIR / "analytics_history.json"
MAX_HISTORY_ENTRIES = 104  # ~2 anos de snapshots semanais
VIDEO_TAGS_FILE = DATA_DIR / "video_tags.json"
SCENE_PERFORMANCE_FILE = DATA_DIR / "scene_performance.json"
_MIN_SCENE_SAMPLES = 3  # cena com poucos videos ainda: peso fica neutro (nao ha o suficiente pra confiar)
_MIN_SCENE_WEIGHT = 0.4
_MAX_SCENE_WEIGHT = 2.5

TITLE_PATTERN_PERFORMANCE_FILE = DATA_DIR / "title_pattern_performance.json"
_MIN_TITLE_PATTERN_SAMPLES = 3
_MIN_TITLE_PATTERN_WEIGHT = 0.4
_MAX_TITLE_PATTERN_WEIGHT = 2.5

# Thumbnail A/B testing: apos _THUMBNAIL_ROTATION_DAYS dias, se o video
# performar abaixo de _THUMBNAIL_ROTATION_THRESHOLD x a mediana de views do
# canal, troca a thumbnail ativa (variante A) pela variante B via
# thumbnails.set. A YouTube Data API so aceita 1 thumbnail por video (nao
# suporta A/B nativamente); essa rotacao e a alternativa pratica.
_THUMBNAIL_ROTATION_DAYS = 7
_THUMBNAIL_ROTATION_THRESHOLD = 0.5


def _to_int(value) -> int:
    """Converte string/int/None para int de forma segura."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


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
    video_ids: list[str] = []
    page_token = ""
    pages = 0
    while len(video_ids) < MAX_VIDEOS and pages < 20:
        pages += 1
        resp = _retry_youtube_call(
            service.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist,
                maxResults=50,
                pageToken=page_token,
            ).execute
        )
        if not resp.get("items"):
            break
        for item in resp.get("items", []):
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = resp.get("nextPageToken") or ""
        if not page_token:
            break

    if not video_ids:
        log.info("Nenhum video encontrado.")
        return [], channel_stats

    # Busca estatisticas detalhadas
    stats: list[dict] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = _retry_youtube_call(
            service.videos().list(
                part="statistics,snippet,contentDetails",
                id=",".join(batch),
            ).execute
        )
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content = item.get("contentDetails", {})
            stats.append({
                "video_id": item["id"],
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt", ""),
                "duration": content.get("duration", ""),
                "views": _to_int(statistics.get("viewCount")),
                "likes": _to_int(statistics.get("likeCount")),
                "comments": _to_int(statistics.get("commentCount")),
            })

    return stats, channel_stats


def _load_video_tags() -> dict:
    try:
        return json.loads(VIDEO_TAGS_FILE.read_text(encoding="utf-8")) if VIDEO_TAGS_FILE.exists() else {}
    except Exception:
        return {}


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
            next_variant, thumb_next, video_id,
        )
        return False

    try:
        _retry_youtube_call(
            service.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(str(thumb_next))
            ).execute
        )
    except Exception as exc:
        log.warning("maybe_rotate_thumbnail: falha ao trocar thumbnail de %s: %s", video_id, exc)
        return False

    log.info(
        "Thumbnail de %s rotacionada %s->%s (views=%d < %.1f%% da mediana %.0f).",
        video_id, current_variant, next_variant, views,
        _THUMBNAIL_ROTATION_THRESHOLD * 100, median_views,
    )
    video_tags_entry["thumbnail_variant"] = next_variant
    video_tags_entry["rotated_at"] = now.isoformat()
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
            if TITLE_PATTERN_PERFORMANCE_FILE.exists() else {}
        )
    except Exception:
        return {}


def _compute_weighted_performance(
    stats: list[dict], video_tags: dict, tag_key: str,
    min_samples: int, min_weight: float, max_weight: float,
) -> dict[str, float]:
    """Calcula um peso relativo por valor de tag_key (ex: 'scene' ou
    'title_pattern' em video_tags.json) a partir das views reais coletadas.

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
    views_by_key: dict[str, list[int]] = {}
    for video in stats:
        tag = video_tags.get(video["video_id"])
        key = tag.get(tag_key) if tag else ""
        if not key:
            continue
        views_by_key.setdefault(key, []).append(video["views"])

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
        stats, video_tags, "title_pattern",
        _MIN_TITLE_PATTERN_SAMPLES, _MIN_TITLE_PATTERN_WEIGHT, _MAX_TITLE_PATTERN_WEIGHT,
    )


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
    # Estimativa grossa de watch time: total_views * duracao_media.
    # Sem YouTube Analytics API (que daria o valor exato), usamos a media
    # de duracao dos videos coletados como proxy.
    avg_duration_seconds = 0.0
    if video_stats:
        durations = []
        for _v in video_stats:
            # duration vem em ISO 8601 (PT#M#S); estimativa simples via views
            # Como nao temos a duracao parseada aqui, usa 30s para Shorts
            # (media do canal) como fallback conservador.
            durations.append(30.0)
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


def main() -> int:
    configure_logging()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

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

    video_tags = _load_video_tags()

    scene_weights = _compute_scene_performance(stats, video_tags)
    if scene_weights:
        _update_scene_performance(scene_weights)

    title_pattern_weights = _compute_title_pattern_performance(stats, video_tags)
    if title_pattern_weights:
        _update_title_pattern_performance(title_pattern_weights)

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
    if rotated_any:
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
                TITLE_PATTERN_PERFORMANCE_FILE, len(merged),
            )
        except Exception as exc:
            log.warning("Falha ao salvar performance por padrao de titulo: %s", exc)


if __name__ == "__main__":
    sys.exit(main())
