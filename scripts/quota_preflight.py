#!/usr/bin/env python3
"""Write an API quota estimate before expensive workflows."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.api_quota_budget import (  # noqa: E402
    estimate_fetch_content_cost,
    estimate_publish_run_cost,
    quota_ledger_row,
    write_quota_ledger_row,
)


def preflight(workflow: str, *, check_only: bool = False) -> dict:
    if workflow == "fetch-content":
        estimate = estimate_fetch_content_cost()
    else:
        estimate = estimate_publish_run_cost()
    if check_only:
        return quota_ledger_row(estimate)
    return write_quota_ledger_row(estimate)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow", choices=["fetch-content", "youtube-bot"])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--no-fail-on-block",
        action="store_true",
        help="Report quota block state without failing audit-only jobs.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Evaluate guard state without appending estimated spend to the ledger.",
    )
    args = parser.parse_args()
    row = preflight(args.workflow, check_only=args.check_only)
    if args.json:
        print(json.dumps(row, sort_keys=True, ensure_ascii=False))
    else:
        guard = row.get("guard") or {}
        print(
            f"quota preflight: workflow={row.get('workflow')} units={row.get('estimated_units')} "
            f"ratio={guard.get('projected_ratio')} block={guard.get('block')}"
        )
    if args.no_fail_on_block:
        return 0
    return 3 if (row.get("guard") or {}).get("block") else 0


if __name__ == "__main__":
    raise SystemExit(main())
