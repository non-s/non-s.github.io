"""
scripts/batch_generate.py — gera múltiplos shorts em sequência.

Argumentos de linha de comando (com fallback para env vars, para compat
com workflows existentes que injetam via environment):
    --count=1..10                   (BATCH_COUNT)
    --upload=true|false             (BATCH_UPLOAD)
    --schedule=true|false           (BATCH_SCHEDULE) — usa publish_optimizer

Quando --schedule=true, o batch reserva slots de publicação otimizados
(utils/publish_optimizer.pick_publish_time) e passa cada um como
--publish-at para upload_youtube.py. Assim vários shorts podem ser
agendados em horários diferentes de alto CTR em vez de todos publicarem
de uma vez.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_config import configure_logging
from utils.publish_optimizer import iso_datetime_from_slot, pick_publish_time

log = logging.getLogger(__name__)


def _run(cmd: list[str], env: dict | None = None) -> int:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    log.info("Executando: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, env=full_env)
    return result.returncode


def _parse_args(argv: list[str] | None = None) -> tuple[int, bool, bool]:
    """Resolve count/upload/schedule: argparse se presente, com fallback para
    env vars (BATCH_COUNT/BATCH_UPLOAD/BATCH_SCHEDULE). Mantem compatibilidade
    com workflows que injetam via environment."""
    parser = argparse.ArgumentParser(description="Batch generator Pata Jazz (shorts)")
    parser.add_argument("--count", default=None, help="1..10")
    parser.add_argument("--upload", default=None, help="true|false")
    parser.add_argument("--schedule", default=None, help="true|false")
    args, _ = parser.parse_known_args(argv)

    raw_count = args.count if args.count is not None else os.environ.get("BATCH_COUNT", "1")
    raw_upload = args.upload if args.upload is not None else os.environ.get("BATCH_UPLOAD", "false")
    raw_schedule = args.schedule if args.schedule is not None else os.environ.get("BATCH_SCHEDULE", "false")
    upload = str(raw_upload).lower() in ("1", "true", "yes")
    schedule = str(raw_schedule).lower() in ("1", "true", "yes")
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        count = -1
    return count, upload, schedule


def _reserve_slots(count: int) -> list[str]:
    """Reserva N slots de publicação otimizados e retorna lista de ISO 8601 UTC."""
    chosen = pick_publish_time(count=count * 2, horizon_days=14, min_delay_hours=2)
    slots: list[dict] = [chosen] if isinstance(chosen, dict) else chosen
    reserved: list[str] = []
    for slot in slots[:count]:
        try:
            iso = iso_datetime_from_slot(slot)
            reserved.append(iso)
        except Exception as exc:
            log.warning("Falha ao converter slot %s: %s", slot, exc)
    # Fallback: se faltou slot, preenche com horários espaçados de 2h a partir de amanhã 18h BRT.
    while len(reserved) < count:
        from datetime import UTC, datetime, timedelta

        fallback = datetime.now(UTC) + timedelta(hours=2 + len(reserved) * 2)
        reserved.append(fallback.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return reserved


def main(argv: list[str] | None = None) -> int:
    configure_logging()

    count, upload, schedule = _parse_args(argv)

    if not 1 <= count <= 10:
        log.error("BATCH_COUNT deve ser entre 1 e 10")
        return 1

    # A manual batch may prepare several private drafts, but must never make
    # more than one public release without an explicit operator override.
    privacy = os.environ.get("YOUTUBE_PRIVACY", "private").lower()
    if upload and privacy == "public" and count > 1 and os.environ.get("ALLOW_MULTI_PUBLIC_BATCH") != "1":
        log.error("Lote publico bloqueado: use a rotina diaria ou ALLOW_MULTI_PUBLIC_BATCH=1 apos revisao editorial.")
        return 1

    slots: list[str] = []
    if schedule and upload:
        slots = _reserve_slots(count)
        log.info("Slots de publicação reservados: %s", [json.loads(json.dumps(s)) for s in slots])

    for i in range(count):
        log.info("=== Batch %d/%d (short pata_jazz) ===", i + 1, count)
        rc = _run([sys.executable, "generate_pata_jazz_short.py"])
        if rc != 0:
            log.error("Falha ao gerar short %d", i + 1)
            return rc

        if upload:
            upload_cmd = [
                sys.executable,
                "upload_youtube.py",
                "--mode",
                "upload",
                "--language",
                "en",
            ]
            if schedule and i < len(slots):
                upload_cmd += ["--publish-at", slots[i]]
                log.info("Agendando short %d para %s", i + 1, slots[i])
            rc = _run(upload_cmd)
            if rc != 0:
                log.error("Falha no upload %d", i + 1)
                return rc

    log.info("Batch concluido: %d shorts (pata_jazz)", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
