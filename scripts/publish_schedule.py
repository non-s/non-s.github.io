#!/usr/bin/env python3
"""Write adaptive publish schedule recommendation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.publish_schedule import write_schedule

if __name__ == "__main__":
    schedule = write_schedule()
    print(f"publish_schedule: {schedule.get('recommended_slots', [])}")
