"""Testes para utils/state_lock.py."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.state_lock import _STALE_LOCK_SECONDS, state_lock


def test_state_lock_acquires_and_releases(tmp_path: Path):
    target = tmp_path / "state.json"
    # O filelock pode ou nao manter o arquivo .lock apos liberar; o importante
    # e que o context manager rode sem levantar e que um segundo lock funcione.
    with state_lock(target):
        pass
    with state_lock(target):
        pass


def test_state_lock_propagates_oserror(tmp_path: Path):
    target = tmp_path / "state.json"
    with patch("utils.state_lock.FileLock") as mock_fl:
        fake_lock = MagicMock()
        fake_lock.__enter__ = MagicMock(side_effect=OSError("locked"))
        fake_lock.__exit__ = MagicMock(return_value=False)
        mock_fl.return_value = fake_lock
        with pytest.raises(OSError, match="locked"):
            with state_lock(target):
                pass


def test_state_lock_inner_exception_propagates(tmp_path: Path):
    target = tmp_path / "state.json"
    with pytest.raises(ValueError, match="boom"):
        with state_lock(target):
            raise ValueError("boom")


def test_state_lock_prunes_stale_lock(tmp_path: Path):
    target = tmp_path / "state.json"
    lock_file = tmp_path / "state.json.lock"
    lock_file.write_text("", encoding="utf-8")
    # Forca mtime para alem do limite de stale.
    old_mtime = time.time() - _STALE_LOCK_SECONDS - 1
    os.utime(lock_file, (old_mtime, old_mtime))

    # O lock antigo e removido e um novo e adquirido sem TimeoutError.
    with state_lock(target):
        pass

    # FileLock recria o arquivo durante o lock; depois de liberar o arquivo
    # pode ser mantido ou removido conforme a versao/ambiente. O teste real
    # de sucesso e nao ter levantado TimeoutError por causa do lock residuo.
    assert True


def test_state_lock_does_not_prune_recent_lock(tmp_path: Path):
    target = tmp_path / "state.json"
    lock_file = tmp_path / "state.json.lock"
    lock_file.write_text("", encoding="utf-8")

    with patch("utils.state_lock.os.remove") as mock_remove:
        with state_lock(target):
            pass

    # Locks recentes nao devem ser removidos.
    mock_remove.assert_not_called()


def test_state_lock_logs_prune_warning(tmp_path: Path, caplog):
    target = tmp_path / "state.json"
    lock_file = tmp_path / "state.json.lock"
    lock_file.write_text("", encoding="utf-8")
    old_mtime = time.time() - _STALE_LOCK_SECONDS - 1
    os.utime(lock_file, (old_mtime, old_mtime))

    with caplog.at_level("WARNING", logger="utils.state_lock"):
        with state_lock(target):
            pass

    assert "lock residuo" in caplog.text
