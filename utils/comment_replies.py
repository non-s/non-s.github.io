"""
utils/comment_replies.py — Channel-owner auto-replies to top comments.

Comments-per-view is one of the top three documented ranking signals
on Shorts (after swipe-away rate and average view %). Beyond the
single pinned first-comment we already drop on upload, replying to
the FIRST handful of viewer comments multiplies the signal:

  - The reply itself counts as a comment
  - Each reply lifts the parent's visibility (other viewers see the
    notification badge)
  - YouTube's classifier reads channel-owner engagement as "this
    creator is active" — a positive ranking factor

This module fetches the top-level comments on recently published
Shorts and posts ONE channel-owner reply per comment, chosen from a
short panel of templated responses customised by the comment's tone.

Safety
------
The reply panel is deliberately conservative:
  - We never reply to comments we can't classify (sentiment unclear)
  - We never reply to comments calling the channel out (mistakes,
    accusations of AI slop, factual disputes) — those are operator
    business, not bot business.
  - Max 5 replies per video, max 25 per run, max 1 reply per author.

Quota
-----
commentThreads.list = 1 unit, comments.insert = 50 units. Five
replies per video × 5 Shorts/day = 25 inserts = 1,250 units = 12.5 %
of the 10k daily budget. The quota ledger picks this up.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

MAX_REPLIES_PER_VIDEO = int(os.environ.get("COMMENT_REPLIES_MAX_PER_VIDEO", "5"))
MAX_REPLIES_PER_RUN   = int(os.environ.get("COMMENT_REPLIES_MAX_PER_RUN",   "25"))
LOOKBACK_HOURS        = int(os.environ.get("COMMENT_REPLIES_LOOKBACK_H",    "72"))

# Sentiment-keyed reply panel. We pick one at random (hash-derived,
# deterministic per comment) so a viewer scrolling the comments doesn't
# see the same reply twice in a row.
REPLY_PANEL: dict[str, tuple[str, ...]] = {
    "positive": (
        "Thanks for watching — more breaking news every day 🌍",
        "Glad it landed. Subscribe for the next one!",
        "🙌 appreciated. Keep us honest in the next one.",
        "Thanks — sharing helps the channel a lot.",
    ),
    "curious": (
        "Good question — we'll dig into this more soon. Stay tuned 👀",
        "Worth a follow-up Short — adding to next week's list.",
        "Sharp observation. Comment again when the next angle drops.",
    ),
    "agreement": (
        "Exactly — and that's why this one's bigger than people realise.",
        "Same read on it. Watch what happens next.",
        "💯 — pin worthy take.",
    ),
    "geo": (
        "Always good to hear from viewers around the world 🌍",
        "Big shoutout to the international crowd — keep the perspectives coming.",
        "Different countries, same scroll 👋",
    ),
}

# Sentiment classification — string-match heuristics, no AI call.
# Order matters: more specific signals first.
_GEO_PATTERN = re.compile(
    r"\b(from\s+\w+|watching from|here in|in\s+(brazil|brasil|usa|america|"
    r"uk|england|india|germany|france|spain|japan|china|portugal|canada|"
    r"australia|africa|mexico))\b",
    re.IGNORECASE,
)
_POSITIVE_PATTERNS = re.compile(
    r"\b(great|love|good|awesome|nice|thanks?|thank you|amazing|excellent|"
    r"helpful|best channel|brilliant|finally|liked|👍|❤|❤️|🔥|💯|🙌|good job)\b",
    re.IGNORECASE,
)
_CURIOUS_PATTERNS = re.compile(
    r"\?|\b(why|how|what|when|where|wondering|curious|explain)\b",
    re.IGNORECASE,
)
_AGREEMENT_PATTERNS = re.compile(
    r"\b(true|exactly|right|agree|spot on|fact|preach|💯|yep|yes|"
    r"this is correct|nailed it)\b",
    re.IGNORECASE,
)
# Stuff we should NEVER reply to automatically.
_AVOID_PATTERNS = re.compile(
    r"\b(ai (slop|generated|garbage)|bot|fake|wrong|incorrect|"
    r"misinformation|propaganda|nazi|fascist|terror|"
    r"kill (yourself|urself)|kys|sub for sub|sub4sub|"
    r"check out my channel|first|second|early)\b",
    re.IGNORECASE,
)


def classify_comment(text: str) -> str | None:
    """Return one of REPLY_PANEL keys, or None if we shouldn't reply."""
    if not text:
        return None
    text = text.strip()
    if len(text) < 4 or len(text) > 800:
        return None
    if _AVOID_PATTERNS.search(text):
        return None
    if _GEO_PATTERN.search(text):
        return "geo"
    if _AGREEMENT_PATTERNS.search(text):
        return "agreement"
    if _CURIOUS_PATTERNS.search(text):
        return "curious"
    if _POSITIVE_PATTERNS.search(text):
        return "positive"
    return None  # neutral / unclassified → skip


def pick_reply(comment_id: str, sentiment: str) -> str | None:
    """Deterministic reply pick based on comment id + sentiment."""
    panel = REPLY_PANEL.get(sentiment) or ()
    if not panel:
        return None
    import hashlib
    h = hashlib.sha1(f"{sentiment}:{comment_id}".encode()).digest()
    return panel[int.from_bytes(h[:4], "big") % len(panel)]


# ── YouTube wiring ───────────────────────────────────────────────

REPLIES_LOG = Path(os.environ.get("COMMENT_REPLIES_LOG",
                                    "_data/comment_replies.jsonl"))


def _load_replied_ids() -> set[str]:
    """Set of comment IDs we've already replied to (idempotency)."""
    if not REPLIES_LOG.exists():
        return set()
    out: set[str] = set()
    try:
        import json
        for line in REPLIES_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                cid = e.get("comment_id")
                if cid:
                    out.add(cid)
            except Exception:
                continue
    except Exception:
        pass
    return out


def _record(comment_id: str, video_id: str, reply: str,
             sentiment: str) -> None:
    import json
    REPLIES_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "comment_id": comment_id,
        "video_id":   video_id,
        "sentiment":  sentiment,
        "reply":      reply,
        "ts":         datetime.now(timezone.utc).isoformat(),
    }
    with REPLIES_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _recent_video_ids(youtube, lookback_hours: int) -> list[str]:
    """Channel's own Shorts published in the lookback window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    try:
        chan = youtube.channels().list(part="contentDetails", mine=True).execute()
        uploads_pl = chan["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except Exception as exc:
        log.warning("comment_replies: uploads playlist lookup failed: %s", exc)
        return []
    video_ids: list[str] = []
    page_token = None
    while True:
        try:
            resp = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_pl,
                maxResults=50,
                pageToken=page_token,
            ).execute()
        except Exception:
            break
        for item in resp.get("items", []):
            vid = item["contentDetails"]["videoId"]
            ts = item["contentDetails"].get("videoPublishedAt", "")
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                continue
            if t < cutoff:
                page_token = None
                break
            video_ids.append(vid)
        else:
            page_token = resp.get("nextPageToken")
            if page_token:
                continue
        break
    return video_ids


def reply_to_recent(youtube, my_channel_id: str | None = None,
                     max_per_video: int = MAX_REPLIES_PER_VIDEO,
                     max_per_run:   int = MAX_REPLIES_PER_RUN,
                     lookback_hours: int = LOOKBACK_HOURS) -> int:
    """Reply to top-level viewer comments on recently published Shorts.

    Returns the number of replies posted. The quota ledger entries
    are written by the caller (or by upload_youtube when imported).
    """
    from utils import youtube_quota
    replied = _load_replied_ids()
    posted = 0
    video_ids = _recent_video_ids(youtube, lookback_hours=lookback_hours)
    log.info("comment_replies: scanning %d recent video(s)", len(video_ids))
    for vid in video_ids:
        if posted >= max_per_run:
            break
        try:
            threads = youtube.commentThreads().list(
                part="snippet",
                videoId=vid,
                maxResults=20,
                order="time",
                textFormat="plainText",
            ).execute()
            youtube_quota.record("commentThreads.list", video_id=vid)
        except Exception as exc:
            log.debug("comment_replies: fetch failed for %s: %s", vid, exc)
            continue
        per_video = 0
        seen_authors: set[str] = set()
        for thread in threads.get("items", []) or []:
            if per_video >= max_per_video or posted >= max_per_run:
                break
            top = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            cid = thread.get("snippet", {}).get("topLevelComment", {}).get("id")
            author_id = top.get("authorChannelId", {}).get("value", "")
            if not cid or cid in replied:
                continue
            # Skip our own comments (the first-comment pinned by upload).
            if my_channel_id and author_id == my_channel_id:
                continue
            if author_id in seen_authors:
                continue
            text = top.get("textOriginal") or top.get("textDisplay") or ""
            sentiment = classify_comment(text)
            if not sentiment:
                continue
            reply = pick_reply(cid, sentiment)
            if not reply:
                continue
            try:
                youtube.comments().insert(
                    part="snippet",
                    body={"snippet": {"parentId": cid, "textOriginal": reply}},
                ).execute()
                youtube_quota.record("comments.insert", video_id=vid)
                _record(cid, vid, reply, sentiment)
                posted += 1
                per_video += 1
                seen_authors.add(author_id)
                log.info("  💬 replied to %s on %s (%s)", cid[:8], vid, sentiment)
            except Exception as exc:
                log.debug("  ⚠️ reply failed for %s: %s", cid[:8], exc)
                continue
    log.info("comment_replies: posted %d total", posted)
    return posted
