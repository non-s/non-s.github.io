from __future__ import annotations

import subprocess

from scripts import run_intelligence_suite


class _Result:
    def __init__(self, returncode: int):
        self.returncode = returncode


def test_ops_guardian_operational_pause_is_soft_failure(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda _cmd: _Result(2))

    assert run_intelligence_suite.run_script("scripts/ops_guardian.py", strict=True) == 0


def test_strict_suite_still_fails_regular_script_errors(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda _cmd: _Result(2))

    assert run_intelligence_suite.run_script("scripts/audit_automation.py", strict=True) == 2
