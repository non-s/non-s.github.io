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


def _cron_field_values(field: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for chunk in str(field or "").split(","):
        part = chunk.strip()
        if not part:
            continue
        if part == "*":
            values.update(range(minimum, maximum + 1))
        elif part.startswith("*/") and part[2:].isdigit():
            step = max(1, int(part[2:]))
            values.update(range(minimum, maximum + 1, step))
        elif "-" in part:
            start, end = part.split("-", 1)
            if start.isdigit() and end.isdigit():
                values.update(range(max(minimum, int(start)), min(maximum, int(end)) + 1))
        elif part.isdigit():
            value = int(part)
            if minimum <= value <= maximum:
                values.add(value)
    return values


def _cron_slots(text: str) -> set[str]:
    slots: set[str] = set()
    for match in re.finditer(r"cron:\s*['\"](?P<cron>[^'\"]+)['\"]", text):
        parts = match.group("cron").split()
        if len(parts) < 2:
            continue
        minutes = _cron_field_values(parts[0], 0, 59)
        hours = _cron_field_values(parts[1], 0, 23)
        for minute in minutes:
            for hour in hours:
                slots.add(f"{int(hour):02d}:{int(minute):02d}")
    return slots


def _append_overlap_errors(errors: list[str], left_name: str, left: set[str], right_name: str, right: set[str]) -> None:
    overlap = sorted(left & right)
    if overlap:
        preview = ", ".join(overlap[:12])
        suffix = "" if len(overlap) <= 12 else f" and {len(overlap) - 12} more"
        errors.append(f"{left_name} cron overlaps {right_name}: {preview}{suffix}")


def audit_slot_contracts(root: Path = ROOT) -> dict:
    canonical = set(CANONICAL_SLOTS_UTC)
    bot_text = _read(root / ".github" / "workflows" / "youtube-bot.yml")
    watchdog_text = _read(root / ".github" / "workflows" / "youtube-watchdog.yml")
    fetch_text = _read(root / ".github" / "workflows" / "fetch-content.yml")
    docs_text = "\n".join(
        _read(path)
        for path in (
            root / "README.md",
            root / "docs" / "ENVIRONMENT.md",
            root / "docs" / "WILD_BRIEF_WORLD_CLASS_UPGRADE.md",
        )
    )
    bot_slots = _cron_slots(bot_text)
    watchdog_slots = _cron_slots(watchdog_text)
    fetch_slots = _cron_slots(fetch_text)
    errors: list[str] = []
    missing_bot = sorted(canonical - bot_slots)
    if missing_bot:
        errors.append("youtube-bot.yml missing canonical slots: " + ", ".join(missing_bot))
    if fetch_slots:
        _append_overlap_errors(errors, "youtube-bot.yml", bot_slots, "fetch-content.yml", fetch_slots)
        _append_overlap_errors(errors, "youtube-watchdog.yml", watchdog_slots, "fetch-content.yml", fetch_slots)
    if bot_slots and watchdog_slots:
        _append_overlap_errors(errors, "youtube-bot.yml", bot_slots, "youtube-watchdog.yml", watchdog_slots)
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
