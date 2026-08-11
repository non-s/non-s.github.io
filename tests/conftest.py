"""Insere o diretorio raiz do projeto no inicio do sys.path para evitar conflitos."""

import sys
from pathlib import Path

import pytest

import utils.media_usage as media_usage

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_permanent_media_ledger(tmp_path, monkeypatch):
    """Cada teste recebe um ledger vazio e nunca toca o estado real do repo."""
    ledger = tmp_path / "_state" / "media_usage.json"
    monkeypatch.setattr(media_usage, "_usage_file", lambda: ledger)
