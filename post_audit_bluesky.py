#!/usr/bin/env python3
"""Post weekly audit summary to Bluesky with enriched site health metrics."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from utils.frontmatter import parse, get_str
from utils.retry import retry_call

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

BSKY_API  = "https://bsky.social/xrpc"
POSTS_DIR = Path(__file__).parent / "_posts"
_DATE_RE  = re.compile(r'^(\d{4})-(\d{2})-(\d{2})-')


def _count_posts_this_week() -> tuple[int, dict[str, int]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    total = 0
    by_cat: dict[str, int] = {}
    for p in POSTS_DIR.glob("*.md"):
        m = _DATE_RE.match(p.name)
        if not m:
            continue
        try:
            pd = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            continue
        if pd >= cutoff:
            total += 1
            try:
                fm  = parse(p.read_text(encoding="utf-8", errors="replace"))
                cat = get_str(fm, "categories", "news")
                by_cat[cat] = by_cat.get(cat, 0) + 1
            except Exception:
                pass
    return total, by_cat


def _count_total_posts() -> int:
    return sum(1 for _ in POSTS_DIR.glob("*.md"))


def _load_run_data() -> dict:
    for path in (Path("_data/last_run.json"), Path("_data/audit_report.json")):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _build_text(total_posts: int, week_count: int, week_cats: dict, run_data: dict) -> str:
    top_cats    = sorted(week_cats.items(), key=lambda x: x[1], reverse=True)[:3]
    top_cat_str = ", ".join(f"{k}({v})" for k, v in top_cats) if top_cats else "—"
    issues      = run_data.get("issues_count", 0)
    dead        = run_data.get("feeds_dead", 0)
    now_str     = datetime.now(timezone.utc).strftime("%b %d")

    lines = [
        f"📊 GlobalBR News — Weekly Health ({now_str})",
        "",
        f"📰 {total_posts} total posts | +{week_count} this week",
        f"🏆 Top: {top_cat_str}",
    ]
    if issues:
        lines.append(f"⚠️ {issues} posts need attention")
    if dead:
        lines.append(f"💀 {dead} dead feed(s) detected")
    lines += ["", "#GlobalBRNews #WeeklyReport #NewsBot"]

    text = "\n".join(lines)
    return (text[:297] + "…") if len(text) > 300 else text


def main() -> None:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        log.warning("Bluesky credentials not set — skipping")
        sys.exit(0)

    total_posts       = _count_total_posts()
    week_count, wcats = _count_posts_this_week()
    run_data          = _load_run_data()
    text              = _build_text(total_posts, week_count, wcats, run_data)

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
        log.error("Bluesky auth failed — skipping")
        sys.exit(1)

    def _do_post():
        r = requests.post(
            f"{BSKY_API}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={
                "repo": session["did"], "collection": "app.bsky.feed.post",
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

    ok = retry_call(_do_post, max_attempts=3, base_delay=5.0, default=False)
    if ok:
        log.info("✅ Weekly audit posted (%d total, +%d this week)", total_posts, week_count)
    else:
        log.warning("Bluesky post failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
