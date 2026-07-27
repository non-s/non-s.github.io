"""utils/state_lock.py — locks de arquivo para estado JSON compartilhado.

Os arquivos de estado em _data/ (video_tags.json, live_state.json,
scene_performance.json, etc) sofrem read-modify-write de multiplos scripts
e multiplos jobs do GitHub Actions que podem rodar sobrepostos. Sem lock,
o ultimo a salvar vence e mudancas sao perdidas silenciosamente.

filelock (pip install filelock) e uma dependencia leve e portavel que
funciona em Linux (CI) e Windows (dev local) sem precisar de fcntl/msvcrt.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock

log = logging.getLogger(__name__)


@contextmanager
def state_lock(path: Path, timeout: float = 30.0) -> Iterator[None]:
    """Adquire um lock de arquivo para o caminho dado.

    Cria um arquivo ``{path}.lock`` ao lado do arquivo de estado. Usa
    timeout de 30s por padrao ( suficiente para concorrencia entre jobs
    do GHA - escrever JSON de estado e rapido). Se expirar, levanta
    Timeout (derivado de OSError) - nao e silencioso de proposito: perder
    o lock e pior do que falhar alto.

    Uso tipico::

        with state_lock(_VIDEO_TAGS_FILE):
            existing = _load()
            existing[video_id] = {...}
            _save(existing)
    """
    lock = FileLock(str(path) + ".lock", timeout=timeout)
    try:
        with lock:
            yield
    except OSError as exc:
        log.warning("Falha ao adquirir lock para %s: %s", path, exc)
        raise
