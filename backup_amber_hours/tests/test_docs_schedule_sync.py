from __future__ import annotations

from pathlib import Path

from scripts.check_schedule_sync import check_schedule_sync

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_current_repo_schedule_contract_is_in_sync():
    """The dense per-hour canonical slot grid this check used to validate
    was the (now-removed) lofi Shorts pipeline's cadence -- see
    check_schedule_sync()'s docstring. Retired to an always-empty
    contract rather than deleted outright, so a future dense-cadence
    pipeline has somewhere to re-add a real check."""
    assert check_schedule_sync(REPO_ROOT) == []
