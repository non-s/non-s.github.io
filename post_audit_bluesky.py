#!/usr/bin/env python3
"""Post weekly audit summary to Bluesky with enriched site health metrics."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from utils.retry import retry_call

BSKY_API  = "https://bsky.social/xrpc"
POSTS_DIR = Path(__file__).parent / "_posts"


def _count_posts_this_week() -> tuple[int, dict]:
    """Count posts created in the last 7 days and breakdown by category."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    total = 0
    by_cat: dict[str, int] = {}
    for p in POSTS_DIR.glob("*.md"):
        m_date = __import__("re").match(r'^(\d{4})-(\d{2})-(\d{2})-', p.name)
        if not m_date:
            continue
        try:
            pd = datetime(int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3)), tzinfo=timezone.utc)
        except ValueError:
            continue
        if pd >= cutoff:
            total += 1
            text = p.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if line.startswith("categories:"):
                    import re
                    m = re.search(r'\[([^\]]+)\]', line)
                    cat = m.group(1).split(",")[0].strip().strip('"').strip("'") if m else "news"
                    by_cat[cat] = by_cat.get(cat, 0) + 1
                    break
    return total, by_cat


def _count_total_posts() -> int:
    return sum(1 for p in POSTS_DIR.glob("*.md"))


def _load_audit_data() -> dict:
    audit_path = Path("_data/audit_report.json")
    if audit_path.exists():
        try:
            return json.loads(audit_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _build_text(total_posts: int, week_count: int, week_cats: dict, audit: dict) -> str:
    top_cats = sorted(week_cats.items(), key=lambda x: x[1], reverse=True)[:3]
    top_cat_str = ", ".join(f"{k}({v})" for k, v in top_cats) if top_cats else "—"

    issues = audit.get("issues_count", 0)
    now_str = datetime.now(timezone.utc).strftime("%b %d")

    lines = [
        f"📊 GlobalBR News — Weekly Health ({now_str})",
        f"",
        f"📰 {total_posts} total posts | +{week_count} this week",
        f"🏆 Top: {top_cat_str}",
    ]
    if issues:
        lines.append(f"⚠️ {issues} posts need attention")

    lines += ["", "#GlobalBRNews #WeeklyReport #NewsBot"]

    text = "\n".join(lines)
    if len(text) > 300:
        text = text[:297] + "…"
    return text


def main() -> None:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        print("Bluesky credentials not set — skipping")
        sys.exit(0)

    total_posts      = _count_total_posts()
    week_count, week_cats = _count_posts_this_week()
    audit            = _load_audit_data()
    text             = _build_text(total_posts, week_count, week_cats, audit)

    def _auth():
        r = requests.post(
            f"{BSKY_API}/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    session = retry_call(_auth, max_attempts=3, base_delay=5.0, default=None)
    if not session:
        print("Bluesky auth failed — skipping")
        sys.exit(1)

    def _post():
        r = requests.post(
            f"{BSKY_API}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={
                "repo":       session["did"],
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type":     "app.bsky.feed.post",
                    "text":      text,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "langs":     ["en"],
                },
            },
            timeout=20,
        )
        r.raise_for_status()
        return True

    ok = retry_call(_post, max_attempts=3, base_delay=5.0, default=False)
    if ok:
        print(f"✅ Posted weekly audit to Bluesky ({total_posts} posts total, +{week_count} this week)")
    else:
        print("Bluesky post failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
