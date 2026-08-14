"""
utils/log_config.py — configuração centralizada de logging para o Liquid Wire.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(level: int = logging.INFO, name: str | None = None) -> None:
    """Configura logging com formato padronizado para CLI e CI.

    Idempotente: se ja configurou, apenas ajusta o nivel. Evita duplicar
    handlers quando um script e importado por outro que ja configurou logs.
    """
    log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format=log_format, stream=sys.stdout)
    else:
        root.setLevel(level)

    # Evita que bibliotecas de terceiros poluam demais
    for noisy in ("urllib3", "requests", "googleapiclient"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_exception_to_file(exc: BaseException, output_dir: Path, name: str = "last_error.txt") -> Path:
    """Salva traceback em arquivo para facilitar debug em CI.

    Preserva historico: anexa ao arquivo existente com timestamp em vez
    de sobrescrever, para que erros de batch (3 videos) nao se percam.
    """
    import traceback
    from datetime import UTC, datetime

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / name
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    # Usa exc.__traceback__ explicitamente: traceback.format_exc() le
    # sys.exc_info(), que so retorna o traceback correto dentro de um bloco
    # `except` ativo. Essa funcao e chamada por handlers de nivel superior
    # (main() do upload_youtube) DEPOIS do except ter terminado, o que faria
    # format_exc() retornar "NoneType: None" e perder o traceback real.
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    entry = f"=== {timestamp} ===\n{tb}\n\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    return path
