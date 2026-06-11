"""Promote high-signal viewer comments into queueable Short ideas."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

ANIMAL_HINTS = {
    "ant",
    "bear",
    "bird",
    "cat",
    "dog",
    "dolphin",
    "duck",
    "eagle",
    "fox",
    "frog",
    "lion",
    "octopus",
    "orca",
    "owl",
    "penguin",
    "shark",
    "snake",
    "tiger",
    "turtle",
    "whale",
    "wolf",
}


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _comment_id(comment: dict) -> str:
    raw = "|".join(_text(comment.get(key)) for key in ("comment_id", "id", "video_id", "text", "comment"))
    return "comment-short-" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]


def score_comment(comment: dict) -> dict:
    text = _text(comment.get("text") or comment.get("comment"))
    words = _words(text)
    lower = text.lower()
    score = 28.0
    reasons: list[str] = []
    if "?" in text:
        score += 24
        reasons.append("viewer_question")
    if any(token in lower for token in ("can you", "do ", "what about", "why", "how")):
        score += 14
        reasons.append("request_language")
    animals = sorted({word for word in re.findall(r"[a-z]+", lower) if word in ANIMAL_HINTS})
    if animals:
        score += min(18, 6 * len(animals))
        reasons.append("animal_named")
    try:
        likes = int(comment.get("likeCount") or comment.get("likes") or 0)
    except Exception:
        likes = 0
    if likes:
        score += min(14, likes * 2)
        reasons.append("liked_by_viewers")
    if len(words) < 4:
        score -= 18
        reasons.append("too_short")
    if len(words) > 45:
        score -= 8
        reasons.append("too_long")
    if any(token in lower for token in ("subscribe", "http", "crypto", "giveaway")):
        score -= 40
        reasons.append("spam_risk")
    return {
        "score": round(max(0.0, min(100.0, score)), 2),
        "reasons": reasons,
        "animals": animals,
        "text": text,
    }


def build_comment_short_candidate(comment: dict, markers: list[dict] | None = None) -> dict:
    scored = score_comment(comment)
    text = scored["text"]
    animal = (scored["animals"] or ["nature"])[0]
    source_video = _text(comment.get("video_id"))
    title = f"{animal.title()} answer to a viewer question"
    related = ""
    for marker in markers or []:
        if _text(marker.get("video_id")) == source_video:
            related = _text(marker.get("title"))
            break
    prompt = text[:180].rstrip(".")
    return {
        "id": _comment_id(comment),
        "source": "youtube_comment",
        "source_video_id": source_video,
        "source_title": related,
        "source_comment": text[:500],
        "title": title,
        "seo_title": title,
        "category": animal if animal != "nature" else "wildlife",
        "hook": f"A viewer asked: {prompt}",
        "script": (
            f"A viewer asked: {prompt}. Here is the nature answer in one clear example: "
            "watch the behavior first, then connect it to the survival payoff."
        ),
        "thumbnail_text": f"{animal.upper()} ANSWER"[:28],
        "yt_tags": [animal, "viewer question", "nature facts"],
        "score": scored["score"],
        "comment_score": scored,
        "comment_context": {
            "video_id": source_video,
            "published_at": comment.get("publishedAt", ""),
            "author": comment.get("author", ""),
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def build_candidates(comments_payload: dict, markers: list[dict] | None = None) -> list[dict]:
    raw = (
        comments_payload.get("raw_comments")
        or comments_payload.get("top_comments")
        or comments_payload.get("comments")
        or []
    )
    candidates = [build_comment_short_candidate(item, markers) for item in raw if isinstance(item, dict)]
    return sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)


def merge_into_queue(queue: dict, candidates: list[dict], *, min_score: float = 64.0, max_items: int = 6) -> dict:
    stories = list(queue.get("stories") or [])
    seen = {str(item.get("id")) for item in stories if isinstance(item, dict)}
    added = 0
    for candidate in candidates:
        if added >= max_items:
            break
        if float(candidate.get("score") or 0) < min_score or candidate.get("id") in seen:
            continue
        item = dict(candidate)
        item["studio_state"] = "comment_idea"
        item["comment_to_short"] = {
            "score": candidate.get("score", 0),
            "source_video_id": candidate.get("source_video_id", ""),
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }
        stories.append(item)
        seen.add(str(item.get("id")))
        added += 1
    out = dict(queue)
    out["stories"] = stories
    out["comment_to_short_added"] = added
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out
