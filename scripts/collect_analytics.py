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
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_config import configure_logging
from utils.youtube_oauth import get_youtube_service

log = logging.getLogger(__name__)

DATA_DIR = ROOT / "_data"
MAX_VIDEOS = 50


def collect_video_stats(service) -> list[dict]:
    """Busca estatisticas dos videos mais recentes do canal."""
    # Primeiro: lista IDs dos videos recentes
    channels = service.channels().list(part="contentDetails,statistics", mine=True).execute()
    if not channels.get("items"):
        log.error("Nenhum canal encontrado.")
        return []

    channel_id = channels["items"][0]["id"]
    uploads_playlist = channels["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # Lista videos da playlist de uploads
    video_ids: list[str] = []
    page_token = ""
    while len(video_ids) < MAX_VIDEOS:
        resp = service.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist,
            maxResults=50,
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = resp.get("nextPageToken", "")
        if not page_token:
            break

    if not video_ids:
        log.info("Nenhum video encontrado.")
        return []

    # Busca estatisticas detalhadas
    stats: list[dict] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = service.videos().list(
            part="statistics,snippet,contentDetails",
            id=",".join(batch),
        ).execute()
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content = item.get("contentDetails", {})
            stats.append({
                "video_id": item["id"],
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt", ""),
                "duration": content.get("duration", ""),
                "views": int(statistics.get("viewCount", 0)),
                "likes": int(statistics.get("likeCount", 0)),
                "comments": int(statistics.get("commentCount", 0)),
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

    stats = collect_video_stats(service)
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
        "collected_at": datetime.now(timezone.utc).isoformat(),
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
    return 0


if __name__ == "__main__":
    sys.exit(main())