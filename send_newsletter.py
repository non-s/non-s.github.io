#!/usr/bin/env python3
"""
send_newsletter.py
Daily email newsletter — sends the top posts of the day to Mailchimp subscribers.

Only sends if at least MIN_POSTS posts were published today.

Env vars required:
  MAILCHIMP_API_KEY     — Mailchimp API key
  MAILCHIMP_AUDIENCE_ID — Mailchimp list / audience ID
  MAILCHIMP_SERVER      — datacenter prefix, e.g. "us15" (optional; derived from
                          API key suffix when omitted, e.g. key ending in "-us15")
"""
from __future__ import annotations

import html
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

from utils.frontmatter import parse, get_str, get_list
from utils.retry import retry_call


def _safe_url(raw: str, fallback: str = "#") -> str:
    """Allow only http(s) URLs; anything else collapses to fallback."""
    if not raw:
        return fallback
    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return raw
    return fallback


def _esc(text: str) -> str:
    """HTML-escape user-controlled content before inlining into the email body."""
    return html.escape(text or "", quote=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("newsletter.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR     = Path(__file__).parent / "_posts"
SITE_BASE_URL = "https://non-s.github.io"
MIN_POSTS     = int(os.environ.get("NEWSLETTER_MIN_POSTS", "3"))
MAX_POSTS     = int(os.environ.get("NEWSLETTER_MAX_POSTS", "10"))


def load_todays_posts() -> list[dict]:
    """Return up to MAX_POSTS posts published today."""
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    posts: list[dict] = []
    for path in sorted(POSTS_DIR.glob(f"{today_prefix}-*.md"), reverse=True)[:MAX_POSTS]:
        try:
            fm = parse(path.read_text(encoding="utf-8", errors="replace"))
            if not fm:
                continue
            fm["_path"]     = path
            fm["_filename"] = path.name
            posts.append(fm)
        except Exception as exc:
            log.warning("Could not read %s: %s", path, exc)
    return posts


def build_post_url(post: dict) -> str:
    filename = post["_filename"]
    stem     = filename.removesuffix(".md")
    parts    = stem.split("-", 3)
    if len(parts) < 4:
        return SITE_BASE_URL
    year, month, day, slug = parts
    category = get_str(post, "categories", "news")
    return f"{SITE_BASE_URL}/{category}/{year}/{month}/{day}/{slug}/"


def truncate(text: str, limit: int = 150) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    last_space = cut.rfind(" ")
    return (cut[:last_space] if last_space > limit // 2 else cut) + "…"


def build_html(posts: list[dict], today: str) -> str:
    story_blocks = []
    for post in posts:
        title       = _esc(get_str(post, "title", "Untitled"))
        description = _esc(truncate(get_str(post, "description"), 150))
        image_url   = _safe_url(get_str(post, "image"), "")
        source_url  = _safe_url(get_str(post, "source_url"), "#")
        post_url    = _safe_url(build_post_url(post), SITE_BASE_URL)
        category    = _esc(get_str(post, "categories", "News").upper())

        img_block = ""
        if image_url:
            img_block = (
                f'<a href="{_esc(post_url)}" style="display:block;text-decoration:none;">'
                f'<img src="{_esc(image_url)}" alt="{title}" '
                f'style="width:100%;max-height:220px;object-fit:cover;border-radius:6px;'
                f'display:block;margin-bottom:12px;" /></a>'
            )

        story_blocks.append(f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="margin-bottom:28px;border-bottom:1px solid #1e2435;padding-bottom:24px;">
          <tr><td>
            {img_block}
            <span style="display:inline-block;background:#f97316;color:#fff;font-size:11px;
                         font-weight:700;letter-spacing:1px;padding:3px 9px;border-radius:3px;
                         margin-bottom:8px;">{category}</span>
            <h2 style="margin:8px 0 6px;font-size:18px;line-height:1.35;">
              <a href="{_esc(post_url)}" style="color:#f1f5f9;text-decoration:none;">{title}</a>
            </h2>
            <p style="margin:0 0 12px;color:#94a3b8;font-size:14px;line-height:1.6;">{description}</p>
            <a href="{_esc(source_url)}"
               style="display:inline-block;background:#f97316;color:#fff;font-size:13px;
                      font-weight:600;padding:8px 18px;border-radius:4px;text-decoration:none;">
              Read more →
            </a>
          </td></tr>
        </table>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GlobalBR News — Daily Digest</title>
</head>
<body style="margin:0;padding:0;background:#080c17;font-family:Arial,Helvetica,sans-serif;color:#f1f5f9;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#080c17;">
    <tr><td align="center" style="padding:20px 10px;">
      <table width="620" cellpadding="0" cellspacing="0" border="0"
             style="max-width:620px;width:100%;background:#0f1523;border-radius:10px;overflow:hidden;">
        <tr>
          <td style="background:#080c17;padding:28px 32px;border-bottom:2px solid #f97316;text-align:center;">
            <h1 style="margin:0 0 6px;font-size:26px;color:#f97316;">GlobalBR News</h1>
            <p style="margin:0;color:#64748b;font-size:13px;text-transform:uppercase;">
              Daily Digest &mdash; {today}
            </p>
          </td>
        </tr>
        <tr><td style="padding:28px 32px;">{"".join(story_blocks)}</td></tr>
        <tr>
          <td style="background:#080c17;padding:20px 32px;text-align:center;border-top:1px solid #1e2435;">
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
    </td></tr>
  </table>
</body>
</html>"""


class MailchimpClient:
    def __init__(self, api_key: str, audience_id: str, server: str = "") -> None:
        dc = server.strip() or api_key.split("-")[-1]
        self.base        = f"https://{dc}.api.mailchimp.com/3.0"
        self.audience_id = audience_id
        self.session     = requests.Session()
        self.session.auth = ("anystring", api_key)
        self.session.headers.update({"Content-Type": "application/json"})

    def _post(self, path: str, payload: dict) -> dict:
        def _call():
            r = self.session.post(self.base + path, data=json.dumps(payload), timeout=30)
            r.raise_for_status()
            return r.json()
        result = retry_call(_call, max_attempts=3, base_delay=5.0, default=None)
        if result is None:
            raise RuntimeError(f"Mailchimp POST {path} failed after 3 attempts")
        return result

    def _put(self, path: str, payload: dict) -> dict:
        def _call():
            r = self.session.put(self.base + path, data=json.dumps(payload), timeout=30)
            r.raise_for_status()
            return r.json()
        result = retry_call(_call, max_attempts=3, base_delay=5.0, default=None)
        if result is None:
            raise RuntimeError(f"Mailchimp PUT {path} failed after 3 attempts")
        return result

    def create_campaign(self, subject: str, from_name: str, reply_to: str) -> str:
        payload = {
            "type": "regular",
            "recipients": {"list_id": self.audience_id},
            "settings": {"subject_line": subject, "from_name": from_name, "reply_to": reply_to},
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


def main() -> None:
    api_key     = os.environ.get("MAILCHIMP_API_KEY", "").strip()
    audience_id = os.environ.get("MAILCHIMP_AUDIENCE_ID", "").strip()
    server      = os.environ.get("MAILCHIMP_SERVER", "").strip()

    if not api_key or not audience_id:
        log.warning("MAILCHIMP_API_KEY or MAILCHIMP_AUDIENCE_ID not set — skipping newsletter.")
        sys.exit(0)

    now            = datetime.now(timezone.utc)
    today_display  = now.strftime("%B %d, %Y")

    posts = load_todays_posts()
    log.info("Found %d post(s) for today.", len(posts))

    if len(posts) < MIN_POSTS:
        log.info("Only %d post(s) (minimum %d) — skipping newsletter.", len(posts), MIN_POSTS)
        sys.exit(0)

    for p in posts:
        log.info("  • %s", get_str(p, "title", p["_filename"]))

    subject = f"GlobalBR News — {today_display}"
    html    = build_html(posts, today_display)
    client  = MailchimpClient(api_key, audience_id, server)

    try:
        campaign_id = client.create_campaign(
            subject=subject, from_name="GlobalBR News", reply_to="noreply@globalbrnews.com",
        )
        client.set_content(campaign_id, html)
        client.send(campaign_id)
        log.info("Newsletter sent — campaign_id=%s, posts=%d", campaign_id, len(posts))
    except Exception as exc:
        log.error("Newsletter failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
