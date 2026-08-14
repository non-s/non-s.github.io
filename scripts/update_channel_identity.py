"""scripts/update_channel_identity.py — mantém a identidade do canal viva.

Parte da "humanizacao" da automacao: o canal nao pode parecer um feed de bot.
Alem de publicar e responder comentarios, a pagina do canal precisa respirar.
Este script rotaciona a descricao (about) e as keywords do canal por semana
ISO, reforçando angulos diferentes da marca (ambient, foco, generativo),
com IA e fallback local. Roda no workflow liquid-wire-identity.yml (semanal),
mas tambem aceita disparo manual.

Guards:
- LIQUID_WIRE_ENABLED=1 e LIQUID_WIRE_IDENTITY_ENABLED=1 para ligar (mesmo
  padrao dos outros workflows).
- Sem YOUTUBE_TOKEN/credenciais, o script loga e retorna 1 (nao quebra CI).

Custo de quota: channels.list = 1 unidade; channels.update = 50 (tranquilo
dentro do pool de 10000/dia, rodando 1x por semana).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.channel_identity import run_identity_update
from utils.log_config import configure_logging, log_exception_to_file
from utils.pipeline_metrics import record_pipeline_run
from utils.youtube_oauth import get_youtube_service

log = logging.getLogger(__name__)

OUTPUT_DIR = ROOT / "_videos"


def _own_channel_id(service) -> str:
    """Retorna o id do canal autenticado via channels.list(mine=true)."""
    response = service.channels().list(part="snippet", mine=True).execute()
    items = response.get("items") or []
    if not items:
        raise RuntimeError("Nenhum canal encontrado para as credenciais atuais.")
    return str(items[0]["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualiza a identidade do Liquid Wire (about/keywords)")
    parser.add_argument("--dry-run", action="store_true", help="Mostra a identidade-alvo sem publicar")
    parser.add_argument("--force", action="store_true", help="Ignora a trava de 1x por semana")
    parser.add_argument(
        "--no-guard", action="store_true",
        help="Ignora os guards de env (LIQUID_WIRE_ENABLED/IDENTITY)",
    )
    args = parser.parse_args()

    configure_logging()

    enabled_var = "LIQUID_WIRE_ENABLED"
    identity_var = "LIQUID_WIRE_IDENTITY_ENABLED"

    # Guards de feature flag: 1 para ligar. Em local/CI de teste, use
    # --no-guard ou configure as env vars.
    enabled = os.environ.get(enabled_var, "") == "1"
    identity_enabled = os.environ.get(identity_var, "") == "1"
    if not args.no_guard and not (enabled and identity_enabled):
        log.info(
            "Guards desligados (%s=%r, %s=%r). Nada a fazer.",
            enabled_var,
            os.environ.get(enabled_var),
            identity_var,
            os.environ.get(identity_var),
        )
        return 0

    start_time = time.time()
    success = False
    try:
        service = get_youtube_service()
        channel_id = _own_channel_id(service)
        report = run_identity_update(
            service,
            channel_id,
            dry_run=args.dry_run,
            force=args.force,
        )
        success = True
        log.info(
            "Identidade concluida: semana=%d changed=%s updated=%s dry_run=%s",
            report["iso_week"],
            report["changed"],
            report["updated"],
            report["dry_run"],
        )
        return 0
    except Exception as exc:
        log.exception("Falha ao atualizar identidade: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1
    finally:
        record_pipeline_run(
            stage="channel_identity",
            success=success,
            duration_seconds=time.time() - start_time,
            kind="identity",
        )


if __name__ == "__main__":
    sys.exit(main())
