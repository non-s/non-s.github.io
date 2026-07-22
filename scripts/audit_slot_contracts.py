#!/usr/bin/env python3
"""Audit the single publish-slot contract across code, workflows and docs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.publish_schedule import CANONICAL_SLOTS_UTC  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def audit_slot_contracts(root: Path = ROOT) -> dict:
    """The dense per-hour canonical slot grid (CANONICAL_SLOTS_UTC) was the
    lofi Shorts pipeline's publish cadence; this used to also check it
    against youtube-bot.yml's/youtube-watchdog.yml's cron (both removed
    when the channel pivoted fully to the storm/rain ambience pillar,
    growth pass 2026-07-21 -- see scripts/check_schedule_sync.py's
    identical retirement note). That workflow-cron coverage check is
    retired along with those files; CANONICAL_SLOTS_UTC itself and the
    doc-coverage checks below stay, since upload_youtube.py's dedup/
    adaptive-schedule math and the documented temporal-metadata fields
    are both still real and still load-bearing.
    """
    canonical = set(CANONICAL_SLOTS_UTC)
    docs_text = "\n".join(
        _read(path)
        for path in (
            root / "README.md",
            root / "docs" / "ENVIRONMENT.md",
            root / "docs" / "ARCHITECTURE.md",
        )
    )
    errors: list[str] = []
    for slot in sorted(canonical):
        if slot not in docs_text:
            errors.append(f"docs missing canonical slot {slot}")
    if "publish_ts_utc" not in docs_text or "quota_day_pt" not in docs_text or "views_regime" not in docs_text:
        errors.append("docs missing temporal metadata fields")
    return {
        "ok": not errors,
        "canonical_slots_utc": sorted(canonical),
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
