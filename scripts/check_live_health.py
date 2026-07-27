"""
scripts/check_live_health.py — verifica se a live 24/7 do Pata Jazz esta
realmente "active" no YouTube.

Chamado por um workflow agendado (pata-jazz-live-healthcheck.yml) que abre
uma Issue automatica no GitHub se nao encontrar nenhum broadcast active -
a live ja reconecta sozinha em falhas curtas (Broken pipe a cada poucos
minutos no runner gratuito, ver scripts/run_live.py), entao um "active"
ausente numa checagem periodica (a cada poucas horas) indica falha real e
persistente que merece atencao humana, nao so mais uma reconexao normal.

Erro de autenticacao/rede AO VERIFICAR e diferente de "a live esta fora do
ar de verdade" - nesse caso o script sai com codigo != 0 sem escrever
GITHUB_OUTPUT, e o workflow simplesmente nao abre nem fecha nenhuma issue
(evita falso positivo por instabilidade transiente da propria checagem).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_config import configure_logging
from utils.youtube_oauth import get_youtube_service
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

log = logging.getLogger(__name__)

LAST_HEALTH_FILE = ROOT / "_data" / "last_health.json"


def is_live_active(service) -> bool:
    """Retorna True se ha pelo menos um broadcast 'active' no canal."""
    resp = _retry_youtube_call(
        service.liveBroadcasts().list(part="id", broadcastStatus="active", mine=True).execute
    )
    return bool(resp.get("items"))


def _write_last_health(active: bool) -> dict:
    """Persiste o ultimo status conhecido em _data/last_health.json (timestamp
    + status) para que workflows futuros possam incluir na issue mesmo sem
    restaurar caches (o healthcheck nao restaura caches). Retorna o payload
    gravado para reuso no GITHUB_OUTPUT."""
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "live_active": active,
    }
    try:
        LAST_HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_HEALTH_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log.warning("Falha ao gravar %s: %s", LAST_HEALTH_FILE, exc)
    return payload


def _write_github_output(active: bool, last_health: dict) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        return
    last_known_status = json.dumps(last_health, ensure_ascii=False).replace("\n", " ")
    with open(github_output, "a", encoding="utf-8") as f:
        f.write(f"live_active={'true' if active else 'false'}\n")
        f.write(f"last_known_status={last_known_status}\n")
        f.write(f"checked_at={last_health.get('timestamp', '')}\n")


def main() -> int:
    configure_logging()
    try:
        service = get_youtube_service()
        active = is_live_active(service)
    except Exception as exc:
        log.error("Falha ao verificar saude da live (nao escreve GITHUB_OUTPUT): %s", exc)
        return 1

    log.info("Live ativa: %s", active)
    last_health = _write_last_health(active)
    _write_github_output(active, last_health)
    return 0


if __name__ == "__main__":
    sys.exit(main())
