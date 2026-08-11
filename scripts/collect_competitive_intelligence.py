from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.competitive_intelligence import collect_competitive_intelligence, save_competitive_intelligence
from utils.log_config import configure_logging
from utils.youtube_oauth import get_youtube_service


def main() -> int:
    configure_logging()
    report = collect_competitive_intelligence(get_youtube_service())
    save_competitive_intelligence(report)
    print(f"Competitive panel collected: {len(report['channels'])} channels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
