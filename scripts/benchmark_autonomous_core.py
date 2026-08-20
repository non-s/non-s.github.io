"""Run bounded autonomous-core benchmarks for CI and engineering audits."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.autonomous_benchmarks import run_benchmarks
from utils.paths import ensure_data_dir


def main() -> int:
    report = run_benchmarks(ensure_data_dir() / "benchmark_report.json")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
