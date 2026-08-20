"""Build the auditable 10/10 report from production evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.excellence_evidence import build_evidence
from utils.excellence_scorecard import evaluate_scorecard


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "_data")
    parser.add_argument("--manifest", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=ROOT / "_data" / "excellence_evidence.json")
    args = parser.parse_args(argv)
    bundle = build_evidence(args.data_root, args.manifest)
    bundle["scorecard"] = evaluate_scorecard(ROOT / "config" / "excellence_scorecard.json", bundle["evidence"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(bundle["scorecard"], ensure_ascii=False, indent=2))
    return 0 if bundle["scorecard"]["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
