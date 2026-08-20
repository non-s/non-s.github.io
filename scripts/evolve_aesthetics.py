"""Weekly aesthetic evolution: analyze YouTube analytics and adjust weights.

Runs as a GitHub Actions workflow (liquid-wire-evolution.yml). Reads
analytics data, asks Gemini to identify patterns in what performs best,
and saves aesthetic weights that influence future video generation.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.ai_evolution import evolve_aesthetics, load_aesthetic_weights

log = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("Starting aesthetic evolution cycle...")
    report = evolve_aesthetics()
    status = report.get("status", "unknown")
    if status in {"evolved", "evolved_deterministic"}:
        log.info("Evolution complete: aesthetic weights updated.")
        weights = load_aesthetic_weights()
        fw = len(weights.get("family_weights", {}))
        gw = len(weights.get("genre_weights", {}))
        log.info("New weights: %d families, %d genres", fw, gw)
        if report.get("recommendations"):
            log.info("Recommendations: %s", report["recommendations"][:500])
    else:
        log.info("Evolution skipped (status=%s). Weights unchanged.", status)
    # Save the report for the dashboard.
    report_path = ROOT / "_data" / "evolution_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
