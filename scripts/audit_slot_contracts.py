#!/usr/bin/env python3
"""Audit the single publish-slot contract across code, workflows and docs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.publish_schedule import CANONICAL_SLOTS_UTC  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _cron_slots(text: str) -> set[str]:
    slots: set[str] = set()
    for match in re.finditer(r"cron:\s*['\"](?P<cron>[^'\"]+)['\"]", text):
        parts = match.group("cron").split()
        if len(parts) < 2:
            continue
        minute = parts[0]
        for hour in parts[1].split(","):
            if hour.isdigit() and minute.isdigit():
                slots.add(f"{int(hour):02d}:{int(minute):02d}")
    return slots


def audit_slot_contracts(root: Path = ROOT) -> dict:
    canonical = set(CANONICAL_SLOTS_UTC)
    bot_text = _read(root / ".github" / "workflows" / "youtube-bot.yml")
    watchdog_text = _read(root / ".github" / "workflows" / "youtube-watchdog.yml")
    docs_text = "\n".join(
        _read(path)
        for path in (
            root / "README.md",
            root / "docs" / "ENVIRONMENT.md",
            root / "docs" / "WILD_BRIEF_WORLD_CLASS_UPGRADE.md",
        )
    )
    bot_slots = _cron_slots(bot_text)
    errors: list[str] = []
    missing_bot = sorted(canonical - bot_slots)
    if missing_bot:
        errors.append("youtube-bot.yml missing canonical slots: " + ", ".join(missing_bot))
    for slot in sorted(canonical):
        if slot not in watchdog_text:
            errors.append(f"youtube-watchdog.yml missing canonical slot {slot}")
        if slot not in docs_text:
            errors.append(f"docs missing canonical slot {slot}")
    if "publish_ts_utc" not in docs_text or "quota_day_pt" not in docs_text or "views_regime" not in docs_text:
        errors.append("docs missing temporal metadata fields")
    return {
        "ok": not errors,
        "canonical_slots_utc": sorted(canonical),
        "youtube_bot_slots": sorted(bot_slots),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit_slot_contracts(Path(args.root).resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    elif report["ok"]:
        print("slot contracts: ok")
    else:
        for error in report["errors"]:
            print(f"slot contract: {error}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
