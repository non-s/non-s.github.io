"""utils/paths.py — caminhos de dados isolados por canal.

Cada canal tem seu proprio diretorio de estado em _data/<slug>/ para que
pesos de performance, video_tags, analytics e estado de live nao
contaminem entre canais. Pata Jazz mantem _data/ (raiz) por backward
compat com o estado ja existente em producao.
"""

from __future__ import annotations

from pathlib import Path

from utils.channel_config import active_channel

ROOT = Path(__file__).resolve().parent.parent
_DATA_ROOT = ROOT / "_data"


def data_dir() -> Path:
    """Retorna o diretorio de dados do canal ativo.

    Pata Jazz (slug='pata_jazz') usa _data/ (raiz) para backward compat.
    Outros canais usam _data/<slug>/.
    """
    if active_channel.slug == "pata_jazz":
        return _DATA_ROOT
    return _DATA_ROOT / active_channel.slug


def ensure_data_dir() -> Path:
    """Garante que o diretorio de dados do canal existe e o retorna."""
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d
