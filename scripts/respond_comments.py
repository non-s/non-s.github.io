"""scripts/respond_comments.py — responde aos comentarios dos videos do canal.

Parte da "humanizacao" da automacao: um canal que responde comentarios gera
mais engajamento real (o algoritmo usa comentarios como sinal de satisfacao)
e faz o publico voltar. Roda no workflow liquid-wire-engagement.yml (cron
horario), mas tambem aceita disparo manual.

Guards:
- LIQUID_WIRE_ENABLED=1 e LIQUID_WIRE_COMMENTS_ENABLED=1 para ligar (mesmo
  padrao dos outros workflows).
- Sem YOUTUBE_TOKEN/credenciais, o script loga e retorna 1 (nao quebra CI).

Custo de quota: commentThreads.list = 1 unidade; cada comments.insert = 50.
Com o default de 10 respostas/run, uma execucao usa ~501 unidades do pool
compartilhado de 10000/dia.
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

from utils.comment_responder import (
    _MAX_REPLIES_PER_RUN,
    run_comment_engagement,
)
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
    parser = argparse.ArgumentParser(description="Responde aos comentarios do Liquid Wire")
    parser.add_argument("--dry-run", action="store_true", help="Seleciona e mostra as respostas sem publicar")
    parser.add_argument(
        "--max-replies", type=int, default=_MAX_REPLIES_PER_RUN, help="Maximo de respostas por execucao"
    )
    parser.add_argument(
        "--no-guard", action="store_true",
        help="Ignora os guards de env (LIQUID_WIRE_ENABLED/COMMENTS)",
    )
    args = parser.parse_args()

    configure_logging()

    enabled_var = "LIQUID_WIRE_ENABLED"
    comments_var = "LIQUID_WIRE_COMMENTS_ENABLED"

    # Guards de feature flag: 1 para ligar. Em local/CI de teste, use
    # --no-guard ou configure as env vars.
    enabled = os.environ.get(enabled_var, "") == "1"
    comments_enabled = os.environ.get(comments_var, "") == "1"
    if not args.no_guard and not (enabled and comments_enabled):
        log.info(
            "Guards desligados (%s=%r, %s=%r). Nada a fazer.",
            enabled_var,
            os.environ.get(enabled_var),
            comments_var,
            os.environ.get(comments_var),
        )
        return 0

    start_time = time.time()
    success = False
    try:
        service = get_youtube_service()
        channel_id = _own_channel_id(service)
        report = run_comment_engagement(
            service,
            channel_id,
            max_replies=args.max_replies,
            dry_run=args.dry_run,
        )
        success = True
        log.info(
            "Engajamento concluido: buscados=%d candidatos=%d respondidos=%d falhas=%d",
            report["fetched"],
            report["candidates"],
            report["replied"],
            report["failed"],
        )
        return 0
    except Exception as exc:
        log.exception("Falha no engajamento: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1
    finally:
        record_pipeline_run(
            stage="comment_engagement",
            success=success,
            duration_seconds=time.time() - start_time,
            kind="comments",
        )


if __name__ == "__main__":
    sys.exit(main())
