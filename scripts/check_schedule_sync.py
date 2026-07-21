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

# :20/:40 dropped from the legacy {2,20,22,40,42} recovery-proxy set --
# they're now real canonical slot minutes in their own right (10-minute
# Shorts grid), not stand-ins for the top of the hour.
PUBLISH_SLOT_PROXY_MINUTES = {2, 22, 42}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _workflow_slots(workflow: str) -> set[str]:
    slots: set[str] = set()
    for match in re.finditer(r"cron:\s*['\"](?P<cron>[^'\"]+)['\"]", workflow):
        parts = match.group("cron").split()
        if len(parts) < 2:
            continue
        minutes = range(60) if parts[0] == "*" else [int(parts[0])] if parts[0].isdigit() else []
        hours = range(24) if parts[1] == "*" else [int(hour) for hour in parts[1].split(",") if hour.isdigit()]
        for minute in minutes:
            for hour in hours:
                slots.add(f"{int(hour):02d}:{int(minute):02d}")
    return slots


def _workflow_intended_publish_slots(workflow: str) -> set[str]:
    slots = set()
    for slot in _workflow_slots(workflow):
        hour, minute = [int(part) for part in slot.split(":", 1)]
        if minute in PUBLISH_SLOT_PROXY_MINUTES:
            slots.add(f"{hour:02d}:00")
        else:
            slots.add(slot)
    return slots


def check_schedule_sync(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    canonical = set(CANONICAL_SLOTS_UTC)
    workflow = _read(root / ".github" / "workflows" / "youtube-bot.yml")
    workflow_slots = _workflow_intended_publish_slots(workflow)
    missing_workflow = sorted(canonical - workflow_slots)
    if missing_workflow:
        errors.append(f"youtube-bot.yml cron is missing canonical slots: {', '.join(missing_workflow)}")

    readme = _read(root / "README.md")
    env_doc = _read(root / "docs" / "ENVIRONMENT.md")
    docs_text = "\n".join([readme, env_doc])
    for slot in sorted(canonical):
        if slot not in docs_text:
            errors.append(f"canonical slot {slot} is missing from README/docs")
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
