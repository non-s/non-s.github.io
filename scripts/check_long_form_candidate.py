"""Exit successfully only when replicated mature Shorts justify long-form."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.long_form_policy import eligible_long_form_families
from utils.paths import data_dir


def main() -> int:
    families = eligible_long_form_families(data_dir())
    print(json.dumps({"eligible": bool(families), "families": families}, ensure_ascii=False))
    return 0 if families else 2


if __name__ == "__main__":
    raise SystemExit(main())
