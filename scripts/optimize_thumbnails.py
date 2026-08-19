"""Run thumbnail A/B optimization: check experiments and swap to winners."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.thumbnail_ab_test import run_thumbnail_optimization

log = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("Starting thumbnail A/B optimization cycle...")
    swaps = run_thumbnail_optimization()
    if swaps:
        log.info("Completed %d thumbnail swaps.", len(swaps))
        for s in swaps:
            log.info(
                "  %s: %s -> %s (CTR improvement: %.2f%%)",
                s.get("video_id"),
                s.get("old_variant"),
                s.get("new_variant"),
                s.get("ctr_improvement", 0.0),
            )
    else:
        log.info("No thumbnail swaps needed this cycle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
