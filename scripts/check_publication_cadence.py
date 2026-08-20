"""Expose publication cadence as a GitHub Actions step output."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.paths import data_dir
from utils.publication_cadence import decide_cadence


def main() -> int:
    manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    decision = decide_cadence(data_dir(), manual=manual)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"generate={'true' if decision.generate else 'false'}\n")
            handle.write(f"reason={decision.reason}\n")
    print(json.dumps(decision.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
