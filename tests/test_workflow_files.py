"""Tests for the new Frente F GitHub Actions workflow files."""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _load_workflow(filename: str) -> dict:
    """Load a workflow YAML, normalising the ``on`` key.

    PyYAML (YAML 1.1) coerces the unquoted ``on:`` mapping key to the boolean
    ``True``; GitHub Actions and other YAML 1.2 parsers keep it as ``"on"``.
    Normalise so tests work either way.
    """
    data = yaml.safe_load((WORKFLOWS_DIR / filename).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "on" not in data and True in data:
        data["on"] = data.pop(True)
    return data


WORKFLOW_FILES = {
    "liquid-wire-engagement.yml": "0 */2 * * *",
    "liquid-wire-analytics.yml": "12 2 * * 1",
    "liquid-wire-identity.yml": "20 3 * * 1",
    "liquid-wire-weekly.yml": "30 3 * * 1",
}


@pytest.mark.parametrize("filename", list(WORKFLOW_FILES.keys()))
def test_workflow_file_exists(filename: str) -> None:
    path = WORKFLOWS_DIR / filename
    assert path.exists(), f"{filename} missing in .github/workflows/"


@pytest.mark.parametrize(("filename", "cron"), list(WORKFLOW_FILES.items()))
def test_workflow_has_correct_cron(filename: str, cron: str) -> None:
    data = _load_workflow(filename)
    schedules = data.get("on", {}).get("schedule", [])
    crons = [entry.get("cron") for entry in schedules if isinstance(entry, dict)]
    assert cron in crons, f"{filename} missing expected cron '{cron}'; found {crons}"


@pytest.mark.parametrize("filename", list(WORKFLOW_FILES.keys()))
def test_workflow_uses_liquid_wire_enabled_guard(filename: str) -> None:
    data = _load_workflow(filename)
    jobs = data.get("jobs", {})
    assert jobs, f"{filename} has no jobs"
    for job_name, job in jobs.items():
        condition = str(job.get("if", ""))
        assert "LIQUID_WIRE_ENABLED" in condition, (
            f"{filename} job '{job_name}' is missing the LIQUID_WIRE_ENABLED guard; if={condition!r}"
        )


@pytest.mark.parametrize("filename", list(WORKFLOW_FILES.keys()))
def test_workflow_is_valid_yaml(filename: str) -> None:
    data = _load_workflow(filename)
    assert isinstance(data, dict)
    assert "on" in data
    assert "jobs" in data
