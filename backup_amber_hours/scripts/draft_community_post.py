#!/usr/bin/env python3
"""Draft a suggested YouTube Community-tab post for this week (chat, growth
pass 2026-07-21).

The Community tab has no public YouTube Data API endpoint, so this is an
*operator-assist* artifact, not automation (see SECURITY.md: "When
Studio-only features are needed, generate operator-assist artifacts
instead of automating them") -- it writes one ready-to-paste suggestion to
`_data/community/suggested_post.json`, and a human pastes it into YouTube
Studio -> Community by hand. Contrast with scripts/reply_to_comments.py,
which *does* post automatically -- comment replies go through an official,
documented API endpoint, Community posts do not.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.community_posts import draft_for_week  # noqa: E402

OUT_PATH = ROOT / "_data" / "community" / "suggested_post.json"


def main() -> int:
    now = datetime.now(timezone.utc)
    week_key = now.strftime("%G-W%V")
    draft = draft_for_week(week_key)
    draft["generated_at"] = now.isoformat()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Suggested Community post for {week_key}:\n\n{draft['text']}\n")
    print(f"Paste this into YouTube Studio -> Community when you get a chance. Wrote {OUT_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
