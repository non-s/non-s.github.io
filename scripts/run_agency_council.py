from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.agency_council import run_daily_council
from utils.log_config import configure_logging


def main() -> int:
    configure_logging()
    brief = run_daily_council()
    print(json.dumps(brief["consensus"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
