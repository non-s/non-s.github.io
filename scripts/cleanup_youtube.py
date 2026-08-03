"""
scripts/cleanup_youtube.py — remove do canal os vídeos legados de
horizontal/live, agora que o pipeline é 100% Shorts.

Classifica cada vídeo do canal como "legado" (candidato a remoção) quando:
  - tem `liveStreamingDetails` (foi criado como liveBroadcast, mesmo que a
    transmissão já tenha terminado), OU
  - a duração excede `_SHORT_MAX_SECONDS` (Shorts deste pipeline duram
    ~35s; qualquer coisa acima de 90s é sobra de horizontal/longform).

Roda em modo `--dry-run` por padrão: só lista os candidatos, não deleta
nada. Passe `--dry-run=false` (ou defina a env var DRY_RUN=false) para
efetivamente remover.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_config import configure_logging
from utils.youtube_oauth import get_youtube_service
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

log = logging.getLogger(__name__)

# Shorts deste pipeline duram ~35s (short_spec default); 90s da uma margem
# generosa sem arriscar confundir com horizontal (240-300s) ou live/longform
# (3600s+). YouTube trata ate 180s como "Shorts" oficialmente, mas nada
# gerado por generate_pata_jazz_short.py passa de ~60s mesmo com folga.
_SHORT_MAX_SECONDS = 90
_MAX_VIDEOS = 5000  # guard contra loop infinito de paginacao
_DELETE_PAUSE_SECONDS = 1.0  # espaco entre deletes (videos.delete custa 50 unidades/chamada)

_ISO8601_DURATION_RE = re.compile(r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$")


def _parse_iso8601_duration(value: str) -> float:
    """Converte duração ISO 8601 (ex.: 'PT4M13S') em segundos.

    Retorna 0.0 se o valor estiver vazio/malformado - nunca levanta excecao
    para nao derrubar a limpeza inteira por um video com metadata estranha.
    """
    if not value:
        return 0.0
    match = _ISO8601_DURATION_RE.match(value)
    if not match:
        return 0.0
    parts = match.groupdict()
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return float(hours * 3600 + minutes * 60 + seconds)


def _uploads_playlist_id(service) -> str | None:
    channels = _retry_youtube_call(service.channels().list(part="contentDetails", mine=True).execute)
    items = channels.get("items", [])
    if not items:
        log.error("Nenhum canal encontrado para as credenciais atuais.")
        return None
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def _list_all_video_ids(service, uploads_playlist: str) -> list[str]:
    """Pagina a playlist de uploads inteira (sem cap de 50, ao contrario de
    collect_analytics.py) - a limpeza precisa enxergar vídeos antigos que já
    saíram da janela dos "mais recentes"."""
    video_ids: list[str] = []
    page_token = ""
    while len(video_ids) < _MAX_VIDEOS:
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
        for item in resp.get("items", []):
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = resp.get("nextPageToken") or ""
        if not page_token:
            break
    return video_ids


def _fetch_video_details(service, video_ids: list[str]) -> list[dict]:
    details: list[dict] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = _retry_youtube_call(
            service.videos()
            .list(
                part="snippet,contentDetails,liveStreamingDetails",
                id=",".join(batch),
            )
            .execute
        )
        details.extend(resp.get("items", []))
    return details


def classify_video(video: dict) -> tuple[bool, str]:
    """Retorna (is_legacy, motivo) para um item de videos().list().

    is_legacy=True marca o video como candidato a remocao (horizontal/live).
    """
    video_id = video.get("id", "?")
    is_live = bool(video.get("liveStreamingDetails"))
    if is_live:
        return True, f"{video_id}: tem liveStreamingDetails (gravacao de live)"

    duration_raw = video.get("contentDetails", {}).get("duration", "")
    duration_seconds = _parse_iso8601_duration(duration_raw)
    if duration_seconds > _SHORT_MAX_SECONDS:
        return True, f"{video_id}: duracao {duration_seconds:.0f}s > {_SHORT_MAX_SECONDS}s (horizontal/longform)"

    return False, f"{video_id}: Short valido ({duration_seconds:.0f}s)"


def find_legacy_videos(service) -> list[dict]:
    """Lista todos os vídeos do canal e retorna os classificados como legado."""
    uploads_playlist = _uploads_playlist_id(service)
    if not uploads_playlist:
        return []

    video_ids = _list_all_video_ids(service, uploads_playlist)
    log.info("Total de videos no canal: %d", len(video_ids))
    if not video_ids:
        return []

    details = _fetch_video_details(service, video_ids)
    legacy: list[dict] = []
    for video in details:
        is_legacy, reason = classify_video(video)
        log.info("%s%s", "[LEGADO] " if is_legacy else "", reason)
        if is_legacy:
            legacy.append(video)
    return legacy


def delete_videos(service, videos: list[dict], dry_run: bool) -> int:
    """Deleta os vídeos passados (ou só loga, se dry_run=True). Retorna a
    quantidade efetivamente deletada (0 em dry-run)."""
    if not videos:
        log.info("Nenhum video legado encontrado - nada a fazer.")
        return 0

    titles = [f"  - {v['id']}: {v.get('snippet', {}).get('title', '(sem titulo)')}" for v in videos]
    log.info("Candidatos a remocao (%d):\n%s", len(videos), "\n".join(titles))

    if dry_run:
        log.info("[DRY-RUN] Nenhum video foi deletado. Rode com --dry-run=false para remover de verdade.")
        return 0

    deleted = 0
    for video in videos:
        video_id = video["id"]
        try:
            _retry_youtube_call(service.videos().delete(id=video_id).execute)
            deleted += 1
            log.info("Deletado: %s", video_id)
        except Exception as exc:
            log.error("Falha ao deletar %s: %s", video_id, exc)
        time.sleep(_DELETE_PAUSE_SECONDS)

    log.info("Limpeza concluida: %d/%d videos deletados.", deleted, len(videos))
    return deleted


def _write_github_output(candidates: int, deleted: int, dry_run: bool) -> None:
    env = os.environ.get("GITHUB_OUTPUT")
    if not env:
        return
    try:
        with open(env, "a", encoding="utf-8") as f:
            f.write(f"candidates={candidates}\n")
            f.write(f"deleted={deleted}\n")
            f.write(f"dry_run={'true' if dry_run else 'false'}\n")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove videos legados (horizontal/live) do canal Pata Jazz")
    parser.add_argument(
        "--dry-run",
        default=os.environ.get("DRY_RUN", "true"),
        choices=["true", "false"],
        help="'true' (default) so lista candidatos; 'false' deleta de verdade.",
    )
    args = parser.parse_args(argv)
    dry_run = args.dry_run == "true"

    configure_logging()
    log.info("Modo: %s", "DRY-RUN (nada sera deletado)" if dry_run else "EXECUCAO REAL (videos serao deletados)")

    service = get_youtube_service()
    legacy_videos = find_legacy_videos(service)
    deleted = delete_videos(service, legacy_videos, dry_run=dry_run)
    _write_github_output(len(legacy_videos), deleted, dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
