#!/usr/bin/env python3
"""Write the live-state control-plane pressure report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.control_plane import build_control_plane_report  # noqa: E402

OUT = ROOT / "_data" / "control_plane_report.json"


def main() -> int:
    payload = build_control_plane_report(ROOT)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"control plane: {payload['state']} ({payload['pressure_score']}/100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

