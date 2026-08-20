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
    "liquid-wire-analytics.yml": "12 2 * * *",
    "liquid-wire-identity.yml": "20 3 * * 1",
}


def test_legacy_weekly_batch_is_manual_only() -> None:
    data = _load_workflow("liquid-wire-weekly.yml")
    triggers = data.get("on", {})
    assert "workflow_dispatch" in triggers
    assert "schedule" not in triggers


def test_primary_workflows_expose_governance_switches() -> None:
    video = (WORKFLOWS_DIR / "liquid-wire-video.yml").read_text(encoding="utf-8")
    evolution = (WORKFLOWS_DIR / "liquid-wire-evolution.yml").read_text(encoding="utf-8")
    for switch in (
        "LIQUID_WIRE_PAUSE_SCHEDULES",
        "LIQUID_WIRE_DISABLE_GEMINI",
        "LIQUID_WIRE_DISABLE_EVOLUTION",
    ):
        assert switch in video
        assert switch in evolution
    assert "LIQUID_WIRE_DISABLE_UPLOAD" in video
    assert "LIQUID_WIRE_DISABLE_PUZZLE" in video
    assert "LIQUID_WIRE_FORCE_PRIVATE" in video


def test_horizontal_schedule_is_never_downgraded_to_short() -> None:
    video = (WORKFLOWS_DIR / "liquid-wire-video.yml").read_text(encoding="utf-8")
    horizontal = video.split('elif [ "${{ github.event.schedule }}" = "37 21 * * 2,4,6" ]', 1)[1]
    horizontal = horizontal.split("else", 1)[0]
    assert 'preset="long"' in horizontal
    assert "check_long_form_candidate.py" not in horizontal
    assert 'if [ "${{ steps.format.outputs.preset }}" = "long" ]' in video
    assert "attempts=2" in video


def test_video_and_analytics_rebuild_append_only_publication_ledger() -> None:
    for filename in ("liquid-wire-video.yml", "liquid-wire-analytics.yml"):
        workflow = (WORKFLOWS_DIR / filename).read_text(encoding="utf-8")
        assert "actions: read" in workflow
        assert "restore-publication-ledger.sh" in workflow


def test_continuous_live_chains_and_has_watchdog() -> None:
    live = (WORKFLOWS_DIR / "liquid-wire-live.yml").read_text(encoding="utf-8")
    watchdog = (WORKFLOWS_DIR / "liquid-wire-live-watchdog.yml").read_text(encoding="utf-8")
    assert "duration_minutes=330" in live
    assert "continuous=true" in live
    assert "gh workflow run liquid-wire-live.yml" in live
    assert "7,17,27,37,47,57 * * * *" in watchdog
    assert "delay_seconds=$((duration * 60 - 3600))" in live
    assert "active_other" in live
    assert "group: liquid-wire-live" not in live
    assert "_data/live_continuity.json" in live
    assert "status == \"in_progress\"" in watchdog


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
