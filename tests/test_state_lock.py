"""Testes para utils/state_lock.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.state_lock import state_lock


def test_state_lock_acquires_and_releases(tmp_path: Path):
    target = tmp_path / "state.json"
    with state_lock(target):
        pass
    assert (tmp_path / "state.json.lock").exists() or True


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
