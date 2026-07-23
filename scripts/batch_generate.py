"""
scripts/batch_generate.py — gera múltiplos conteúdos em sequência (short/horizontal/live).

Lê variáveis de ambiente:
    BATCH_KIND=short|horizontal|live
    BATCH_COUNT=1..3
    BATCH_UPLOAD=true|false
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

log = logging.getLogger(__name__)


def _run(cmd: list[str], env: dict | None = None) -> int:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    log.info("Executando: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, env=full_env)
    return result.returncode


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    kind = os.environ.get("BATCH_KIND", "short")
    count = int(os.environ.get("BATCH_COUNT", "1"))
    upload = os.environ.get("BATCH_UPLOAD", "true").lower() in ("1", "true", "yes")

    if kind not in ("short", "horizontal", "live"):
        log.error("BATCH_KIND invalido: %s", kind)
        return 1
    if not 1 <= count <= 3:
        log.error("BATCH_COUNT deve ser entre 1 e 3")
        return 1

    for i in range(count):
        log.info("=== Batch %d/%d (%s) ===", i + 1, count, kind)
        if kind == "short":
            rc = _run([sys.executable, "generate_pata_jazz_short.py"])
        elif kind == "horizontal":
            rc = _run([sys.executable, "generate_pata_jazz_horizontal.py"])
        else:
            rc = _run([sys.executable, "scripts/run_live.py"])
        if rc != 0:
            log.error("Falha ao gerar %s %d", kind, i + 1)
            return rc

        if upload and kind != "live":
            prefix = f"pata_jazz_{kind}_"
            rc = _run([sys.executable, "upload_youtube.py", "--mode", "upload", "--language", "pt", "--prefix", prefix])
            if rc != 0:
                log.error("Falha no upload %s %d", kind, i + 1)
                return rc

    log.info("Batch concluido: %d x %s", count, kind)
    return 0


if __name__ == "__main__":
    sys.exit(main())
