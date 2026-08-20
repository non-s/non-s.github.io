"""Generate machine- and human-readable research reports from channel evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_config import configure_logging
from utils.paths import ensure_data_dir
from utils.research_cycle import run_research_cycle


def main() -> int:
    configure_logging()
    report = run_research_cycle(ensure_data_dir())
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
