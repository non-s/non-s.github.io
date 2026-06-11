#!/usr/bin/env python3
"""Prepare local folders for optional YouTube Reporting API CSV backfills."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def bootstrap(root: Path = Path(".")) -> dict:
    enabled = os.environ.get("YOUTUBE_REPORTING_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    incoming = root / "_data" / "reporting_import"
    processed = root / "_data" / "analytics" / "reporting_backfill"
    incoming.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enabled": enabled,
        "incoming_dir": str(incoming.relative_to(root)),
        "processed_dir": str(processed.relative_to(root)),
        "status": "ready" if enabled else "disabled_safe_noop",
    }
    out = root / "_data" / "analytics" / "reporting_bootstrap.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    report = bootstrap(Path(args.root).resolve())
    print(f"reporting bootstrap: {report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
