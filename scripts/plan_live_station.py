"""Create an auditable editorial plan for the Pata Jazz visual radio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.live_station import TARGET_TRACKS, build_station_plan, save_station_plan
from utils.media_pool import AUDIO_DIR, VIDEO_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan Pata Jazz visual radio without broadcasting.")
    parser.add_argument("--target-tracks", type=int, default=TARGET_TRACKS)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    plan = build_station_plan(
        list(AUDIO_DIR.glob("*.mp3")), list(VIDEO_DIR.glob("*.mp4")), target_tracks=args.target_tracks
    )
    output = save_station_plan(plan, args.output)
    print(f"Station plan: {output}")
    print(f"Verified tracks: {plan['approved_unique_tracks']}/{plan['target_unique_tracks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
