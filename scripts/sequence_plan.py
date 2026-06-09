#!/usr/bin/env python3
"""Build sequence variants from winners."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.sequence_factory import write_sequence_plan

if __name__ == "__main__":
    plan = write_sequence_plan()
    print(f"sequence_plan: {len(plan.get('variants', []))} variants")
