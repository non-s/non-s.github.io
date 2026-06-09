#!/usr/bin/env python3
"""Write first-24h video decisions."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.post24_review import write_review

if __name__ == "__main__":
    review = write_review()
    print(f"post24_review: {review.get('counts', {})}")
