#!/usr/bin/env python3
"""Post weekly audit summary to Bluesky"""
import json
import os
import sys
from pathlib import Path


def main():
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        print("Bluesky credentials not set — skipping")
        return

    audit_path = Path("_data/audit_report.json")
    if not audit_path.exists():
        print("No audit report found")
        return

    data = json.loads(audit_path.read_text())

    text = "📊 Weekly Site Report — GlobalBR News\n\n"
    text += f"📰 {data['total_posts']} total posts\n"
    cats = data.get("category_counts", {})
    if cats:
        top = sorted(cats.items(), key=lambda x: x[1], reverse=True)[:3]
        text += f"🏆 Top categories: {', '.join(f'{k} ({v})' for k, v in top)}\n"
    issues = data.get("issues_count", 0)
    text += f"⚠️ {issues} posts need attention\n\n"
    text += "#GlobalBRNews #WeeklyReport"

    if len(text) > 300:
        text = text[:297] + "..."

    # Use same auth pattern as post_bluesky.py
    import requests
    from datetime import datetime, timezone

    try:
        resp = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
            timeout=20,
        )
        resp.raise_for_status()
        session = resp.json()

        requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={
                "repo": session["did"],
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": text,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "langs": ["en"],
                },
            },
            timeout=20,
        )
        print("✅ Posted audit summary to Bluesky")
    except Exception as e:
        print(f"Bluesky post failed: {e}")


if __name__ == "__main__":
    main()
