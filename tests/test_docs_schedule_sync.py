from __future__ import annotations

from pathlib import Path

from scripts.check_schedule_sync import REQUIRED_FLAGS, check_schedule_sync
from utils.publish_schedule import CANONICAL_SLOTS_UTC

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_current_repo_schedule_contract_is_in_sync():
    assert check_schedule_sync(REPO_ROOT) == []


def test_schedule_sync_detects_missing_workflow_slot(tmp_path):
    _write_contract_files(tmp_path, cron="23 14,19,23 * * *")

    errors = check_schedule_sync(tmp_path)

    assert any("05:23" in error and "youtube-bot.yml" in error for error in errors)


def test_schedule_sync_detects_missing_flag_docs(tmp_path):
    _write_contract_files(tmp_path, env_doc_flags=False)

    errors = check_schedule_sync(tmp_path)

    assert any("ADAPTIVE_CADENCE_ENABLED" in error for error in errors)


def _write_contract_files(root: Path, *, cron: str = "23 5,14,19,23 * * *", env_doc_flags: bool = True) -> None:
    slots = " ".join(CANONICAL_SLOTS_UTC)
    flags = "\n".join(REQUIRED_FLAGS) if env_doc_flags else ""
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / ".github" / "workflows" / "youtube-bot.yml").write_text(
        f'on:\n  schedule:\n    - cron: "{cron}"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(f"{slots}\n_data/publish_slot_decisions.jsonl\n", encoding="utf-8")
    (root / "docs" / "WILD_BRIEF_WORLD_CLASS_UPGRADE.md").write_text(slots, encoding="utf-8")
    (root / "docs" / "ENVIRONMENT.md").write_text(flags, encoding="utf-8")
    (root / ".env.example").write_text("\n".join(REQUIRED_FLAGS), encoding="utf-8")
