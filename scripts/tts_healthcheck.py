#!/usr/bin/env python3
"""Preflight optional local Coqui-compatible TTS fallback."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.tts_fallback import coqui_healthcheck  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-synth", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    payload = coqui_healthcheck(synthesize=not args.no_synth, output_dir=Path(args.root) / "_data" / "tts_health")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"tts health: {payload['status']} ({payload.get('reason', 'ok')})")
    return 2 if args.strict and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
