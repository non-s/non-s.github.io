#!/usr/bin/env python3
"""
send_newsletter.py
Daily email newsletter — sends the top 5 posts to Mailchimp subscribers.

Env vars required:
  MAILCHIMP_API_KEY   — format: <key>-<dc>  e.g. abc123-us21
  MAILCHIMP_AUDIENCE_ID — Mailchimp list / audience ID
"""

import os
import sys
import json
import logging
import re
import requests
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("newsletter.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
POSTS_DIR = Path(__file__).parent / "_posts"
SITE_BASE_URL = "https://non-s.github.io"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> dict:
    """Very small YAML frontmatter parser — no external deps."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    raw = parts[1]
    data: dict = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        # Handle list-style categories: [war] or [war, politics]
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
            data[key] = items
        else:
            data[key] = val
    return data


def load_recent_posts(n: int = 10) -> list[dict]:
    """Return the n most-recently-dated posts with full frontmatter."""
    posts = []
    for path in sorted(POSTS_DIR.glob("*.md"), reverse=True)[:n]:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if not fm:
            continue
        fm["_path"] = path
        fm["_filename"] = path.name
        posts.append(fm)
    return posts


def select_top5(posts: list[dict]) -> list[dict]:
    """Keep only posts that have the required fields, return the first 5."""
    required = ("title", "description", "source_url", "image")
    filtered = [p for p in posts if all(p.get(f) for f in required)]
    return filtered[:5]


def build_post_url(post: dict) -> str:
    """Build the permalink for a post."""
    filename = post["_filename"]          # e.g. 2026-05-13-some-slug.md
    stem = filename.removesuffix(".md")   # 2026-05-13-some-slug
    parts = stem.split("-", 3)            # ['2026', '05', '13', 'some-slug']
    if len(parts) < 4:
        return SITE_BASE_URL
    year, month, day, slug = parts[0], parts[1], parts[2], parts[3]
    cats = post.get("categories", [])
    category = cats[0] if isinstance(cats, list) and cats else "news"
    return f"{SITE_BASE_URL}/{category}/{year}/{month}/{day}/{slug}/"


def truncate(text: str, limit: int = 100) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def build_html(posts: list[dict], today: str) -> str:
    story_blocks = []
    for post in posts:
        title = post.get("title", "Untitled")
        description = truncate(post.get("description", ""), 100)
        image_url = post.get("image", "")
        source_url = post.get("source_url", "#")
        post_url = build_post_url(post)
        cats = post.get("categories", [])
        category = (cats[0] if isinstance(cats, list) and cats else "News").upper()

        img_block = ""
        if image_url:
            img_block = f"""
            <a href="{post_url}" style="display:block;text-decoration:none;">
              <img src="{image_url}" alt="{title}"
                   style="width:100%;max-height:220px;object-fit:cover;border-radius:6px;display:block;margin-bottom:12px;" />
            </a>"""

        story_blocks.append(f"""
        <!-- Story -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="margin-bottom:28px;border-bottom:1px solid #1e2435;padding-bottom:24px;">
          <tr>
            <td>
              {img_block}
              <span style="display:inline-block;background:#f97316;color:#fff;font-size:11px;
                           font-weight:700;letter-spacing:1px;padding:3px 9px;border-radius:3px;
                           margin-bottom:8px;">{category}</span>
              <h2 style="margin:8px 0 6px;font-size:18px;line-height:1.35;">
                <a href="{post_url}" style="color:#f1f5f9;text-decoration:none;">{title}</a>
              </h2>
              <p style="margin:0 0 12px;color:#94a3b8;font-size:14px;line-height:1.6;">{description}</p>
              <a href="{source_url}"
                 style="display:inline-block;background:#f97316;color:#fff;font-size:13px;
                        font-weight:600;padding:8px 18px;border-radius:4px;text-decoration:none;">
                Read more →
              </a>
            </td>
          </tr>
        </table>""")

    stories_html = "\n".join(story_blocks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GlobalBR News — Daily Digest</title>
</head>
<body style="margin:0;padding:0;background:#080c17;font-family:Arial,Helvetica,sans-serif;color:#f1f5f9;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#080c17;">
    <tr>
      <td align="center" style="padding:20px 10px;">

        <!-- Wrapper -->
        <table width="620" cellpadding="0" cellspacing="0" border="0"
               style="max-width:620px;width:100%;background:#0f1523;border-radius:10px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background:#080c17;padding:28px 32px;border-bottom:2px solid #f97316;text-align:center;">
              <h1 style="margin:0 0 6px;font-size:26px;color:#f97316;letter-spacing:-0.5px;">
                🌍 GlobalBR News
              </h1>
              <p style="margin:0;color:#64748b;font-size:13px;letter-spacing:1px;text-transform:uppercase;">
                Daily Digest &mdash; {today}
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:28px 32px;">
              {stories_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#080c17;padding:20px 32px;text-align:center;
                       border-top:1px solid #1e2435;">
              <p style="margin:0 0 8px;color:#475569;font-size:12px;">
                You are receiving this because you subscribed to GlobalBR News updates.
              </p>
              <p style="margin:0;color:#475569;font-size:12px;">
                <a href="*|UNSUB|*" style="color:#f97316;text-decoration:none;">Unsubscribe</a>
                &nbsp;|&nbsp;
                <a href="{SITE_BASE_URL}" style="color:#94a3b8;text-decoration:none;">Visit site</a>
              </p>
            </td>
          </tr>

        </table>
        <!-- /Wrapper -->

      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Mailchimp API
# ---------------------------------------------------------------------------

class MailchimpClient:
    def __init__(self, api_key: str, audience_id: str):
        dc = api_key.split("-")[-1]   # e.g. "us21"
        self.base = f"https://{dc}.api.mailchimp.com/3.0"
        self.audience_id = audience_id
        self.session = requests.Session()
        self.session.auth = ("anystring", api_key)
        self.session.headers.update({"Content-Type": "application/json"})

    def _post(self, path: str, payload: dict) -> dict:
        url = self.base + path
        resp = self.session.post(url, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, payload: dict) -> dict:
        url = self.base + path
        resp = self.session.put(url, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def create_campaign(self, subject: str, from_name: str, reply_to: str) -> str:
        payload = {
            "type": "regular",
            "recipients": {"list_id": self.audience_id},
            "settings": {
                "subject_line": subject,
                "from_name": from_name,
                "reply_to": reply_to,
            },
        }
        result = self._post("/campaigns", payload)
        campaign_id: str = result["id"]
        log.info("Campaign created — id=%s", campaign_id)
        return campaign_id

    def set_content(self, campaign_id: str, html: str) -> None:
        self._put(f"/campaigns/{campaign_id}/content", {"html": html})
        log.info("Campaign content set — id=%s", campaign_id)

    def send(self, campaign_id: str) -> None:
        self._post(f"/campaigns/{campaign_id}/actions/send", {})
        log.info("Campaign sent — id=%s", campaign_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = os.environ.get("MAILCHIMP_API_KEY", "").strip()
    audience_id = os.environ.get("MAILCHIMP_AUDIENCE_ID", "").strip()

    if not api_key or not audience_id:
        log.warning(
            "MAILCHIMP_API_KEY and/or MAILCHIMP_AUDIENCE_ID not set — skipping newsletter."
        )
        sys.exit(0)

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    today_short = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    log.info("Loading posts from %s", POSTS_DIR)
    posts = load_recent_posts(10)
    log.info("Loaded %d posts", len(posts))

    top5 = select_top5(posts)
    if not top5:
        log.warning("No posts with all required fields found — skipping newsletter.")
        sys.exit(0)

    top_headline = top5[0].get("title", "Top World News")
    subject = f"🌍 {top_headline} — GlobalBR News {today_short}"

    log.info("Selected %d posts for newsletter", len(top5))
    for p in top5:
        log.info("  • %s", p.get("title", p["_filename"]))

    html = build_html(top5, today)

    client = MailchimpClient(api_key, audience_id)

    try:
        campaign_id = client.create_campaign(
            subject=subject,
            from_name="GlobalBR News",
            reply_to="noreply@non-s.github.io",
        )
        client.set_content(campaign_id, html)
        client.send(campaign_id)
        log.info("Newsletter dispatched successfully — campaign_id=%s", campaign_id)
    except requests.HTTPError as exc:
        log.error("Mailchimp API error: %s — %s", exc.response.status_code, exc.response.text)
        sys.exit(1)


if __name__ == "__main__":
    main()
