from __future__ import annotations

from pathlib import Path

from scripts.check_schedule_sync import check_schedule_sync
from utils.publish_schedule import CANONICAL_SLOTS_UTC

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_current_repo_schedule_contract_is_in_sync():
    assert check_schedule_sync(REPO_ROOT) == []


def test_schedule_sync_detects_missing_workflow_slot(tmp_path):
    _write_contract_files(tmp_path, cron="23 14,19,23 * * *")

    errors = check_schedule_sync(tmp_path)

    assert any("05:00" in error and "youtube-bot.yml" in error for error in errors)


def test_schedule_sync_detects_missing_docs(tmp_path):
    _write_contract_files(tmp_path, slots_in_docs=False)

    errors = check_schedule_sync(tmp_path)

    assert any("missing from README/docs" in error for error in errors)


def _write_contract_files(
    root: Path,
    *,
    cron: str = "0 * * * *",
    slots_in_docs: bool = True,
) -> None:
    slots = " ".join(CANONICAL_SLOTS_UTC) if slots_in_docs else ""
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / ".github" / "workflows" / "youtube-bot.yml").write_text(
        f'on:\n  schedule:\n    - cron: "{cron}"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(f"{slots}\n", encoding="utf-8")
    (root / "docs" / "ENVIRONMENT.md").write_text("", encoding="utf-8")
