#!/usr/bin/env python3
"""List every video currently on the channel, with id/title/publishedAt.

One-off/manual admin tool: real ground truth for "what's actually live on
the channel right now" is the channel itself, not any locally cached
snapshot or git history of _videos/*.done markers -- both can be stale
relative to videos deleted or added outside this pipeline (e.g. a manual
reset done directly in YouTube Studio).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import _fetch_recent_channel_uploads, get_youtube_service  # noqa: E402


def main() -> int:
    youtube = get_youtube_service()
    uploads = _fetch_recent_channel_uploads(youtube, limit=200)
    print(json.dumps(uploads, indent=2, ensure_ascii=False))
    print(f"\ntotal: {len(uploads)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
