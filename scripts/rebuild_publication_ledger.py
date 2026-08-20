"""Rebuild mutable learning state from append-only publication artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.paths import data_dir
from utils.publication_ledger import rebuild_publication_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("--data-root", type=Path, default=data_dir())
    args = parser.parse_args(argv)
    print(json.dumps(rebuild_publication_state(args.evidence_root, args.data_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
