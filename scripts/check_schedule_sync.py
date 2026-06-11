#!/usr/bin/env python3
"""Check that publish cadence docs, workflow and env flags stay in sync."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.publish_schedule import CANONICAL_SLOTS_UTC  # noqa: E402

REQUIRED_FLAGS = (
    "ADAPTIVE_CADENCE_ENABLED",
    "ALLOW_FLEX_SLOT",
    "MIN_SLOT_PUBLISH_SCORE",
    "MIN_QUEUE_OPPORTUNITY_SCORE",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _workflow_slots(workflow: str) -> set[str]:
    slots: set[str] = set()
    for match in re.finditer(r"cron:\s*['\"](?P<cron>[^'\"]+)['\"]", workflow):
        parts = match.group("cron").split()
        if len(parts) < 2:
            continue
        minute = parts[0]
        for hour in parts[1].split(","):
            if hour.isdigit() and minute.isdigit():
                slots.add(f"{int(hour):02d}:{int(minute):02d}")
    return slots


def check_schedule_sync(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    canonical = set(CANONICAL_SLOTS_UTC)
    workflow = _read(root / ".github" / "workflows" / "youtube-bot.yml")
    workflow_slots = _workflow_slots(workflow)
    missing_workflow = sorted(canonical - workflow_slots)
    if missing_workflow:
        errors.append(f"youtube-bot.yml cron is missing canonical slots: {', '.join(missing_workflow)}")

    readme = _read(root / "README.md")
    upgrade_doc = _read(root / "docs" / "WILD_BRIEF_WORLD_CLASS_UPGRADE.md")
    env_doc = _read(root / "docs" / "ENVIRONMENT.md")
    env_example = _read(root / ".env.example")
    docs_text = "\n".join([readme, upgrade_doc, env_doc])
    for slot in sorted(canonical):
        if slot not in docs_text:
            errors.append(f"canonical slot {slot} is missing from README/docs")
    for flag in REQUIRED_FLAGS:
        if flag not in env_doc:
            errors.append(f"{flag} is missing from docs/ENVIRONMENT.md")
        if flag not in env_example:
            errors.append(f"{flag} is missing from .env.example")
    if "publish_slot_decisions.jsonl" not in docs_text:
        errors.append("publish_slot_decisions.jsonl is missing from README/docs")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    errors = check_schedule_sync(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"schedule sync: {error}", file=sys.stderr)
        return 1
    print("schedule sync: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
