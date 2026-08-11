"""Verifica se a conta do Pata Jazz pode usar a API de transmissao ao vivo.

Nao cria broadcast, stream nem altera configuracoes do canal. O relatorio
serve como pre-flight antes de uma live real, evitando deixar um evento vazio
ou quebrado publicado por falta de habilitacao do YouTube Live.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.paths import data_dir
from utils.youtube_oauth import get_youtube_service
from utils.youtube_retry import retry_youtube_call

log = logging.getLogger(__name__)


def check_live_readiness(service) -> dict[str, object]:
    """Read the live endpoints and return an actionable readiness report."""
    broadcasts = retry_youtube_call(
        service.liveBroadcasts().list(part="id,snippet,status", mine=True, maxResults=50).execute
    )
    streams = retry_youtube_call(service.liveStreams().list(part="id,snippet,status", mine=True, maxResults=50).execute)
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "api_access": True,
        "existing_broadcasts": len(broadcasts.get("items") or []),
        "existing_streams": len(streams.get("items") or []),
        "ready_for_live_setup": True,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        report = check_live_readiness(get_youtube_service())
    except Exception as exc:
        report = {
            "checked_at": datetime.now(UTC).isoformat(),
            "api_access": False,
            "ready_for_live_setup": False,
            "error": str(exc),
        }
        log.error("Live pre-flight falhou: %s", exc)

    output = data_dir() / "live_readiness.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["ready_for_live_setup"]:
        log.info("Live pre-flight aprovado.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
