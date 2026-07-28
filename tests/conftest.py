"""Insere o diretorio raiz do projeto no inicio do sys.path para evitar conflitos."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
