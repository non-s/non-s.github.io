"""Tests for utils/panic.py — env + file kill switch."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils import panic


def test_default_not_halted(monkeypatch):
    monkeypatch.delenv("PANIC_HALT", raising=False)
    monkeypatch.setattr(panic, "PANIC_FLAG_FILE", Path("/nonexistent/panic.flag"))
    halted, _ = panic.is_halted()
    assert halted is False


def test_env_halt_zero_is_not_halted(monkeypatch):
    monkeypatch.setenv("PANIC_HALT", "0")
    monkeypatch.setattr(panic, "PANIC_FLAG_FILE", Path("/nope"))
    assert panic.is_halted()[0] is False


def test_env_halt_one_is_halted(monkeypatch):
    monkeypatch.setenv("PANIC_HALT", "1")
    monkeypatch.setattr(panic, "PANIC_FLAG_FILE", Path("/nope"))
    halted, reason = panic.is_halted()
    assert halted
    assert "1" in reason


def test_env_halt_true_is_halted(monkeypatch):
    monkeypatch.setenv("PANIC_HALT", "true")
    monkeypatch.setattr(panic, "PANIC_FLAG_FILE", Path("/nope"))
    assert panic.is_halted()[0]


def test_file_flag_triggers_halt(tmp_path, monkeypatch):
    monkeypatch.delenv("PANIC_HALT", raising=False)
    flag = tmp_path / "PANIC_HALT"
    flag.write_text("emergency: ad invasive", encoding="utf-8")
    monkeypatch.setattr(panic, "PANIC_FLAG_FILE", flag)
    halted, reason = panic.is_halted()
    assert halted
    assert "PANIC_HALT" in reason
    assert "emergency" in reason


def test_abort_exits_non_zero_when_halted(monkeypatch):
    monkeypatch.setenv("PANIC_HALT", "1")
    monkeypatch.setattr(panic, "PANIC_FLAG_FILE", Path("/nope"))
    with pytest.raises(SystemExit) as exc:
        panic.abort_if_halted("test_component")
    assert exc.value.code == 75


def test_abort_returns_normally_when_clean(monkeypatch):
    monkeypatch.delenv("PANIC_HALT", raising=False)
    monkeypatch.setattr(panic, "PANIC_FLAG_FILE", Path("/nope"))
    # Should NOT raise.
    panic.abort_if_halted("test")
