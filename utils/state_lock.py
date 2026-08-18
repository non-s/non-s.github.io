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
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock

log = logging.getLogger(__name__)

# Locks mais antigos que este limite (em segundos) sao considerados
# residuais de um processo que morreu sem liberar o lock. O filelock
# moderno ja protege contra isso via flock/lockf, mas em runners
# efemeros (GitHub Actions) ou sistemas de arquivos compartilhados um
# arquivo .lock abandonado pode fazer o proximo job esperar ate o
# timeout. A limpeza e conservadora: so remove se estiver realmente
# velho.
_STALE_LOCK_SECONDS = 3600.0


def _prune_stale_lock(lock_path: Path) -> None:
    """Remove um arquivo de lock abandonado se ele for muito antigo.

    The prune threshold is intentionally high (1h) so it never fires under a
    legitimate long-running write (e.g. quality_history rewrite on a slow
    runner). The FileLock ``timeout`` (30s) is the primary contention guard;
    this prune only handles the rare case of a crashed process leaving a
    .lock file on a persistent filesystem. Deleting a lock file that another
    process holds via flock is unsafe on some platforms (the next contender
    acquires a new inode), so we only prune when the age is unambiguous.
    """
    try:
        if not lock_path.exists():
            return
        mtime = lock_path.stat().st_mtime
        age = time.time() - mtime
        if age > _STALE_LOCK_SECONDS:
            log.warning("Removendo lock residuo (%d s) em %s", int(age), lock_path)
            os.remove(lock_path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("Nao foi possivel remover lock residuo %s: %s", lock_path, exc)


@contextmanager
def state_lock(path: Path, timeout: float = 30.0) -> Iterator[None]:
    """Adquire um lock de arquivo para o caminho dado.

    Cria um arquivo ``{path}.lock`` ao lado do arquivo de estado. Usa
    timeout de 30s por padrao ( suficiente para concorrencia entre jobs
    do GHA - escrever JSON de estado e rapido). Se expirar, levanta
    Timeout (derivado de OSError) - nao e silencioso de proposito: perder
    o lock e pior do que falhar alto.

    Antes de adquirir, remove locks residuais antigos para evitar que um
    processo morto deixe o proximo job travado.

    Uso tipico::

        with state_lock(_VIDEO_TAGS_FILE):
            existing = _load()
            existing[video_id] = {...}
            _save(existing)
    """
    lock_path = Path(str(path) + ".lock")
    _prune_stale_lock(lock_path)
    lock = FileLock(str(lock_path), timeout=timeout)
    try:
        with lock:
            yield
    except OSError as exc:
        log.warning("Falha ao adquirir lock para %s: %s", path, exc)
        raise
