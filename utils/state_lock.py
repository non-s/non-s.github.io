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
import threading
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

# Reentrancy registry: maps a resolved lock path to the depth of nested
# state_lock() calls already held by the current thread. filelock.FileLock is
# NOT reentrant — acquiring the same lock twice from the same process blocks
# until the timeout. Several code paths (notably _update_style_drift wrapping
# _load_style_drift in generate_liquid_wire_video.py) legitimately nest
# state_lock() around the same file, which previously deadlocked for 30s per
# nested acquisition (the exact cause of the CI test job timing out at 15min).
# We track the depth per-thread so a nested call is a no-op: the outermost
# call still holds the real FileLock, and nested calls just bump a counter.
_held_locks: dict[str, int] = {}
_held_locks_guard = threading.Lock()


def _lock_key(path: Path) -> str:
    """Stable, OS-portable key for the reentrancy registry.

    os.path.normcase normalises drive-letter casing on Windows and makes the
    lookup case-insensitive there, while resolve() canonicalises ``..`` and
    symlinks so two paths to the same file share a key.
    """
    try:
        return os.path.normcase(str(path.resolve()))
    except OSError:
        # resolve() can raise on a non-existent parent on some platforms; fall
        # back to the normalised string form so reentrancy still works.
        return os.path.normcase(str(path))


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

    Reentrante: uma chamada aninhada com o mesmo ``path`` dentro da mesma
    thread nao bloqueia — apenas incrementa um contador e a liberacao
    real do FileLock so acontece no retorno da chamada mais externa. Isso
    e necessario porque filelock.FileLock nao e reentrante e varias rotinas
    (ex.: _update_style_drift -> _load_style_drift) aninham state_lock()
    sobre o mesmo arquivo.

    Uso tipico::

        with state_lock(_VIDEO_TAGS_FILE):
            existing = _load()
            existing[video_id] = {...}
            _save(existing)
    """
    lock_path = Path(str(path) + ".lock")
    key = _lock_key(path)

    acquired = False
    with _held_locks_guard:
        depth = _held_locks.get(key, 0)
        if depth == 0:
            acquired = True
            _held_locks[key] = 1
        else:
            _held_locks[key] = depth + 1

    try:
        if acquired:
            _prune_stale_lock(lock_path)
            lock = FileLock(str(lock_path), timeout=timeout)
            try:
                with lock:
                    yield
            except OSError as exc:
                log.warning("Falha ao adquirir lock para %s: %s", path, exc)
                raise
        else:
            # Nested call: the outermost state_lock already holds the FileLock
            # for this path on this thread, so yield without re-acquiring.
            yield
    finally:
        with _held_locks_guard:
            depth = _held_locks.get(key, 0)
            if depth <= 1:
                _held_locks.pop(key, None)
            else:
                _held_locks[key] = depth - 1
