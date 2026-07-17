#!/usr/bin/env python3
"""Print the channel's real snippet.title vs brandingSettings.channel.title.

One-off/manual, read-only admin tool. channels.update accepting a
brandingSettings.channel.title write without error doesn't guarantee it
actually took effect: on a channel tied directly to a personal Google
Account (not a separate Brand Account), the visible channel name is
sourced from the Google Account profile name and the brandingSettings
write can be silently ignored. Comparing the two fields here is how to
tell which situation this channel is in.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import get_youtube_service  # noqa: E402


def main() -> int:
    youtube = get_youtube_service()
    response = youtube.channels().list(part="snippet,brandingSettings", mine=True).execute()
    items = response.get("items") or []
    if not items:
        print("No channel found for the authenticated account.", file=sys.stderr)
        return 1
    channel = items[0]
    result = {
        "channel_id": channel.get("id"),
        "snippet.title": (channel.get("snippet") or {}).get("title"),
        "brandingSettings.channel.title": (channel.get("brandingSettings") or {}).get("channel", {}).get("title"),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
