#!/usr/bin/env python3
"""Check that publish cadence docs, workflow and env flags stay in sync."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_schedule_sync(root: Path = ROOT) -> list[str]:
    """The dense per-hour canonical slot grid (utils.publish_schedule.
    CANONICAL_SLOTS_UTC) was the lofi Shorts pipeline's publish cadence,
    checked here against youtube-bot.yml's cron. That workflow was removed
    when the channel pivoted fully to the storm/rain ambience pillar
    (growth pass, 2026-07-21), which publishes on its own much sparser
    cadence (storm-ambience.yml/storm-shorts.yml) that was never meant to
    cover this grid -- so there is no workflow left for this check to
    validate against. CANONICAL_SLOTS_UTC itself stays (upload_youtube.py's
    dedup/adaptive-schedule math still uses it), only this workflow-cron-
    coverage check is retired -- kept as an always-empty contract (not
    deleted outright) so a future dense-cadence pipeline has somewhere to
    re-add a real check.
    """
    del root
    return []


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
