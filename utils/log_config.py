"""
utils/log_config.py — configuração centralizada de logging para o Pata Jazz.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(level: int = logging.INFO, name: str | None = None) -> None:
    """Configura logging com formato padronizado para CLI e CI."""
    log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    logging.basicConfig(level=level, format=log_format, stream=sys.stdout)

    # Evita que bibliotecas de terceiros poluam demais
    for noisy in ("urllib3", "requests", "googleapiclient"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_exception_to_file(exc: BaseException, output_dir: Path, name: str = "last_error.txt") -> Path:
    """Salva traceback em arquivo para facilitar debug em CI."""
    import traceback
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / name
    path.write_text(traceback.format_exc(), encoding="utf-8")
    return path
