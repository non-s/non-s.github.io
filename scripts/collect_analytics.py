"""
scripts/collect_analytics.py — coleta metricas dos videos do canal Pata Jazz.

Usa a YouTube Data API para buscar views, likes, comentarios e duracao dos
videos recentes. Salva um relatorio em _data/analytics.json para analise.

Este script e disparado por um workflow semanal e alimenta o feedback loop:
cenas e hooks com melhor performance sao priorizados na geracao futura.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from upload_youtube import _retry_youtube_call
from utils.log_config import configure_logging
from utils.youtube_oauth import get_youtube_service

log = logging.getLogger(__name__)

DATA_DIR = ROOT / "_data"
MAX_VIDEOS = 50
HISTORY_FILE = DATA_DIR / "analytics_history.json"
MAX_HISTORY_ENTRIES = 104  # ~2 anos de snapshots semanais


def _to_int(value) -> int:
    """Converte string/int/None para int de forma segura."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def collect_video_stats(service) -> list[dict]:
    """Busca estatisticas dos videos mais recentes do canal."""
    # Primeiro: lista IDs dos videos recentes
    channels = _retry_youtube_call(service.channels().list(part="contentDetails,statistics", mine=True).execute)
    if not channels.get("items"):
        log.error("Nenhum canal encontrado.")
        return []

    channel_id = channels["items"][0]["id"]
    uploads_playlist = channels["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
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
        for item in resp.get("items", []):
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = resp.get("nextPageToken") or ""
        if not page_token:
            break

    if not video_ids:
        log.info("Nenhum video encontrado.")
        return []

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

    return stats


def main() -> int:
    configure_logging()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        service = get_youtube_service()
    except Exception as exc:
        log.error("Erro ao autenticar YouTube: %s", exc)
        return 1

    try:
        stats = collect_video_stats(service)
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
    }

    out_path = DATA_DIR / "analytics.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Analytics salvo: %s (%d videos, %d views total)", out_path, len(stats), total_views)

    _append_history(report)
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


if __name__ == "__main__":
    sys.exit(main())
