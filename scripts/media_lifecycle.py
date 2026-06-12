#!/usr/bin/env python3
"""Clean generated media and audit tracked media policy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.media_lifecycle import cleanup_output_dirs, tracked_media_risks, write_lifecycle_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--audit-tracked", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-fail", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    run_cleanup = args.cleanup
    run_audit = args.audit_tracked or not run_cleanup
    sections: dict[str, dict] = {}
    if run_cleanup:
        sections["cleanup"] = cleanup_output_dirs(root=root, dry_run=args.dry_run)
    if run_audit:
        sections["tracked_media"] = tracked_media_risks(root=root)

    report = write_lifecycle_report(root=root, **sections)
    if args.json:
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    else:
        cleanup = sections.get("cleanup") or {}
        tracked = sections.get("tracked_media") or {}
        if cleanup:
            print(
                "media lifecycle: "
                f"deleted={len(cleanup.get('deleted') or [])}, "
                f"bytes={int(cleanup.get('deleted_bytes') or 0)}"
            )
        if tracked:
            print(f"media lifecycle: tracked risks={int(tracked.get('risk_count') or 0)}")

    tracked = sections.get("tracked_media") or {}
    if tracked.get("risk_count") and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
