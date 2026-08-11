"""Generate a reviewable 30-day editorial plan without publishing anything."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.editorial_calendar import build_calendar
from utils.paths import data_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the Pata Jazz editorial calendar")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)
    if args.days < 1 or args.days > 90:
        parser.error("--days must be between 1 and 90")
    output = data_dir() / "editorial_calendar.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "start": args.start.isoformat(),
        "days": args.days,
        "items": build_calendar(args.start, args.days),
    }
    output.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
