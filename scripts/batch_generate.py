"""
scripts/batch_generate.py — gera múltiplos shorts em sequência.

Argumentos de linha de comando (com fallback para env vars, para compat
com workflows existentes que injetam via environment):
    --count=1..10                   (BATCH_COUNT)
    --upload=true|false             (BATCH_UPLOAD)
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.channel_config import active_channel, set_channel_from_env
from utils.log_config import configure_logging

# Ativa o canal via YOUTUBE_CHANNEL env var (multi-canal).
set_channel_from_env()

log = logging.getLogger(__name__)


def _run(cmd: list[str], env: dict | None = None) -> int:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    log.info("Executando: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, env=full_env)
    return result.returncode


def _parse_args(argv: list[str] | None = None) -> tuple[int, bool]:
    """Resolve count/upload: argparse se presente, com fallback para
    env vars (BATCH_COUNT/BATCH_UPLOAD). Mantem compatibilidade
    com workflows que injetam via environment."""
    parser = argparse.ArgumentParser(description=f"Batch generator {active_channel.name} (shorts)")
    parser.add_argument("--count", default=None, help="1..10")
    parser.add_argument("--upload", default=None, help="true|false")
    args, _ = parser.parse_known_args(argv)

    raw_count = args.count if args.count is not None else os.environ.get("BATCH_COUNT", "1")
    raw_upload = args.upload if args.upload is not None else os.environ.get("BATCH_UPLOAD", "true")
    upload = str(raw_upload).lower() in ("1", "true", "yes")
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        count = -1
    return count, upload


def main(argv: list[str] | None = None) -> int:
    configure_logging()

    count, upload = _parse_args(argv)

    if not 1 <= count <= 10:
        log.error("BATCH_COUNT deve ser entre 1 e 10")
        return 1

    prefix = f"{active_channel.slug}_short_"
    for i in range(count):
        log.info("=== Batch %d/%d (short %s) ===", i + 1, count, active_channel.slug)
        rc = _run([sys.executable, "generate_pata_jazz_short.py"])
        if rc != 0:
            log.error("Falha ao gerar short %d", i + 1)
            return rc

        if upload:
            rc = _run([
                sys.executable, "upload_youtube.py",
                "--mode", "upload", "--language", "en", "--prefix", prefix,
            ])
            if rc != 0:
                log.error("Falha no upload %d", i + 1)
                return rc

    log.info("Batch concluido: %d shorts (%s)", count, active_channel.slug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
