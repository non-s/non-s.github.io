"""
utils/paths.py — caminhos de dados do projeto.

O projeto opera com um único canal (Pata Jazz), então todo estado fica em
_data/.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_DATA_ROOT = ROOT / "_data"


def data_dir() -> Path:
    """Retorna o diretório de dados do projeto."""
    return _DATA_ROOT


def ensure_data_dir() -> Path:
    """Garante que o diretório de dados existe e o retorna."""
    _DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return _DATA_ROOT
