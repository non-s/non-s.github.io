#!/usr/bin/env python3
"""Reply to fresh top-level comments across the channel (chat, growth pass
2026-07-21).

The channel audit that kicked off this pass flagged zero community
engagement (no comment replies, no Community-tab activity) as a real gap:
YouTube's own ranking weighs a channel that looks "alive" to real people,
and it's the one growth lever here that doesn't touch video content at
all. This uses `commentThreads.list(allThreadsRelatedToChannelId=...)` --
an official, documented YouTube Data API v3 endpoint, same trust boundary
as every other call in this repo (see SECURITY.md: "Avoid unsupported/
private YouTube endpoints") -- to find comments across every video on the
channel in one paginated sweep, and `comments.insert` to post a reply.

Guardrails:
- A local ledger (`_data/community/replied_comments.jsonl`, append-only,
  same shape as `_data/upload_intents.jsonl`) plus a check of the API's own
  inline reply preview means a comment is never replied to twice.
- Comments containing a link are skipped, not replied to (see
  utils.community_replies.looks_like_spam) -- auto-engaging with spam/scam
  links would publicly associate the channel with them.
- `--max-replies` (env COMMENT_REPLY_MAX_PER_RUN, default 15) caps a single
  run so a sudden backlog can't turn into a burst-posting spam pattern.
- Gated by utils.panic's kill switch, same as every other publisher here.

Not gated by YOUTUBE_PUBLISHING_ENABLED -- posting a reply is a distinct
trust boundary from publishing a video (see the dedicated
COMMUNITY_ENGAGEMENT_ENABLED workflow variable in
.github/workflows/community-comment-replies.yml), so it can be turned on
independently.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import _execute, get_youtube_service  # noqa: E402
from utils.community_replies import looks_like_spam, pick_reply  # noqa: E402
from utils.panic import abort_if_halted  # noqa: E402

log = logging.getLogger("reply_to_comments")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

LEDGER_PATH = ROOT / "_data" / "community" / "replied_comments.jsonl"
DEFAULT_MAX_REPLIES_PER_RUN = 15


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _load_replied_ids(path: Path | None = None) -> set[str]:
    # `path` defaults through a lookup of the *current* module-level
    # LEDGER_PATH rather than binding it as the parameter's default value --
    # a plain `path: Path = LEDGER_PATH` default is captured once at def
    # time, so tests monkeypatching the module attribute would silently
    # keep writing to the real on-disk ledger instead of a tmp_path.
    path = path if path is not None else LEDGER_PATH
    ids: set[str] = set()
    if not path.exists():
        return ids
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        comment_id = str(row.get("comment_id") or "")
        if comment_id:
            ids.add(comment_id)
    return ids


def _append_ledger(row: dict, path: Path | None = None) -> None:
    path = path if path is not None else LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _my_channel_id(youtube) -> str:
    response = _execute(youtube.channels().list(part="id", mine=True))
    items = response.get("items") or []
    return str(items[0].get("id") or "") if items else ""


def _fetch_recent_threads(youtube, channel_id: str, *, limit: int) -> list[dict]:
    threads: list[dict] = []
    page_token = None
    while len(threads) < limit:
        response = _execute(
            youtube.commentThreads().list(
                part="snippet,replies",
                allThreadsRelatedToChannelId=channel_id,
                order="time",
                maxResults=min(100, limit - len(threads)),
                pageToken=page_token,
                textFormat="plainText",
            )
        )
        threads.extend(response.get("items") or [])
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return threads


def _already_owner_replied(thread: dict, channel_id: str) -> bool:
    """True if any reply already inlined in this thread (up to the API's
    own preview limit) came from the channel itself -- covers both a
    previous run of this script and a manual reply from Studio."""
    replies = ((thread.get("replies") or {}).get("comments")) or []
    for reply in replies:
        author_id = ((reply.get("snippet") or {}).get("authorChannelId") or {}).get("value")
        if author_id == channel_id:
            return True
    return False


def _post_reply(youtube, comment_id: str, text: str) -> str:
    response = _execute(
        youtube.comments().insert(
            part="snippet",
            body={"snippet": {"parentId": comment_id, "textOriginal": text}},
        )
    )
    return str(response.get("id") or "")


def run(*, dry_run: bool, max_replies: int) -> dict:
    youtube = get_youtube_service()
    channel_id = _my_channel_id(youtube)
    if not channel_id:
        log.error("Could not resolve the channel's own id -- aborting.")
        return {"error": "no_channel_id"}

    replied_ids = _load_replied_ids()
    threads = _fetch_recent_threads(youtube, channel_id, limit=max(100, max_replies * 4))

    posted = skipped_spam = skipped_own = skipped_already = 0
    for thread in threads:
        if posted >= max_replies:
            break
        top = (thread.get("snippet") or {}).get("topLevelComment") or {}
        snippet = top.get("snippet") or {}
        comment_id = str(top.get("id") or "")
        if not comment_id:
            continue
        if comment_id in replied_ids:
            skipped_already += 1
            continue
        author_channel_id = (snippet.get("authorChannelId") or {}).get("value")
        if author_channel_id == channel_id:
            skipped_own += 1
            continue
        if _already_owner_replied(thread, channel_id):
            skipped_already += 1
            continue
        text = str(snippet.get("textDisplay") or snippet.get("textOriginal") or "")
        if looks_like_spam(text):
            skipped_spam += 1
            continue

        reply_text = pick_reply(comment_id)
        if dry_run:
            log.info("[dry-run] would reply to %s: %s", comment_id, reply_text)
        else:
            try:
                _post_reply(youtube, comment_id, reply_text)
            except Exception as exc:
                log.warning("Failed to reply to %s: %s", comment_id, exc)
                continue
            _append_ledger(
                {
                    "comment_id": comment_id,
                    "video_id": str((thread.get("snippet") or {}).get("videoId") or ""),
                    "author": str(snippet.get("authorDisplayName") or ""),
                    "comment_snippet": text[:200],
                    "reply_text": reply_text,
                    "replied_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        posted += 1

    summary = {
        "threads_seen": len(threads),
        "replies_posted": posted,
        "skipped_spam": skipped_spam,
        "skipped_own_comment": skipped_own,
        "skipped_already_replied": skipped_already,
        "dry_run": dry_run,
    }
    log.info("Comment-reply run: %s", json.dumps(summary))
    return summary


def main() -> int:
    abort_if_halted("reply_to_comments")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Log what would be replied without posting.")
    parser.add_argument("--max-replies", type=int, default=None)
    args = parser.parse_args()
    max_replies = (
        args.max_replies
        if args.max_replies is not None
        else _env_int("COMMENT_REPLY_MAX_PER_RUN", DEFAULT_MAX_REPLIES_PER_RUN)
    )
    try:
        summary = run(dry_run=args.dry_run, max_replies=max_replies)
    except Exception as exc:
        log.error("Comment-reply run failed: %s", exc)
        return 1
    return 1 if summary.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
