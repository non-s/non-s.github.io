#!/usr/bin/env python3
"""Local operator doctor for zero-cost Wild Brief automation."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_slot_contracts import audit_slot_contracts  # noqa: E402
from scripts.check_repo_contracts import check_repo_contracts  # noqa: E402


def run(root: Path = ROOT) -> dict:
    checks = {
        "python": bool(shutil.which("python")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "slot_contracts": audit_slot_contracts(root),
        "repo_contract_errors": check_repo_contracts(root),
    }
    checks["ok"] = checks["python"] and checks["slot_contracts"]["ok"] and not checks["repo_contract_errors"]
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run(Path(args.root).resolve())
    print(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
        if args.json
        else ("doctor: ok" if report["ok"] else "doctor: issues found")
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
