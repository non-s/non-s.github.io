"""Zero-cost topic freshness scoring for queue prioritization."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from utils.editorial_guard import editorial_issues


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _tokens(value: str) -> set[str]:
    return {tok for tok in re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split() if len(tok) >= 3}


def queue_age_days(story: dict, *, now: datetime | None = None) -> float:
    created = _parse_date(story.get("fetched_at") or story.get("published_at") or story.get("updated_at"))
    if not created:
        return 999.0
    current = now or _now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0.0, round((current.astimezone(timezone.utc) - created).total_seconds() / 86400, 2))


def score_topic_freshness(story: dict, candidates: list[dict] | None = None, *, now: datetime | None = None) -> dict:
    """Score a story's timeliness from queue age plus cached free signals."""
    candidates = candidates or []
    text = " ".join(
        str(story.get(key) or "") for key in ("title", "seo_title", "hook", "category", "topic_hashtag", "description")
    )
    story_tokens = _tokens(text)
    best_signal: dict = {}
    best_overlap = 0
    for candidate in candidates:
        cand_tokens = _tokens(" ".join(str(candidate.get(key) or "") for key in ("topic", "summary", "sources")))
        overlap = len(story_tokens & cand_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_signal = candidate
    age = queue_age_days(story, now=now)
    age_score = max(0.0, 42.0 - min(age, 21) * 2.0)
    trend_score = float(best_signal.get("score") or 0) if best_signal else 0.0
    signal_score = min(45.0, trend_score * 0.45) if best_overlap else 0.0
    novelty = 13.0 if age <= 3 else 7.0 if age <= 10 else 0.0
    score = round(max(0.0, min(100.0, age_score + signal_score + novelty)), 2)
    source = "trend_signal" if best_signal else "queue_age"
    return {
        "freshness_score": score,
        "queue_age_days": age,
        "signal_source": source,
        "signal_window": "0_3d" if age <= 3 else "4_10d" if age <= 10 else "stale_11d_plus",
        "topic_cluster": str((best_signal or {}).get("topic") or story.get("category") or "unknown"),
        "matched_signal_score": trend_score if best_signal else 0.0,
    }


def annotate_queue(queue: dict, candidates: list[dict] | None = None, *, now: datetime | None = None) -> dict:
    """Return a queue copy with freshness metadata on every pending story."""
    out = dict(queue or {})
    stories = []
    for story in out.get("stories") or []:
        if not isinstance(story, dict):
            continue
        updated = dict(story)
        if not updated.get("consumed"):
            updated["freshness"] = score_topic_freshness(updated, candidates, now=now)
            updated["freshness_score"] = updated["freshness"]["freshness_score"]
            updated["queue_age_days"] = updated["freshness"]["queue_age_days"]
        stories.append(updated)
    out["stories"] = stories
    return out


def _display_title(item: dict) -> tuple[str, list[str]]:
    title = str(item.get("seo_title") or item.get("title") or "").strip()
    issues = editorial_issues({"title": title, "seo_title": title}, include_script=False) if title else []
    if not issues:
        return title, []
    item_id = str(item.get("id") or "queue-item")
    return f"{item_id} (title needs repair: {', '.join(issues[:3])})", issues


def _report_row(item: dict, *, include_topic: bool = False) -> dict:
    title, issues = _display_title(item)
    row = {
        "id": item.get("id", ""),
        "title": title,
        "freshness_score": item.get("freshness_score", 0),
    }
    if issues:
        row["title_issues"] = issues
    if include_topic:
        row["topic_cluster"] = (item.get("freshness") or {}).get("topic_cluster", "")
    else:
        row["queue_age_days"] = item.get("queue_age_days", 0)
    return row


def freshness_report(queue: dict) -> dict:
    stories = [item for item in (queue.get("stories") or []) if isinstance(item, dict) and not item.get("consumed")]
    scored = [float(item.get("freshness_score") or 0) for item in stories]
    stale = [item for item in stories if float(item.get("queue_age_days") or 0) > 14]
    return {
        "pending": len(stories),
        "scored": len([item for item in stories if item.get("freshness")]),
        "coverage": round(len([item for item in stories if item.get("freshness")]) / max(len(stories), 1), 4),
        "average_freshness_score": round(sum(scored) / max(len(scored), 1), 2) if scored else 0.0,
        "stale_over_14d": len(stale),
        "stale": [
            _report_row(item)
            for item in sorted(stale, key=lambda row: float(row.get("queue_age_days") or 0), reverse=True)[:20]
        ],
        "top_fresh": sorted(
            [_report_row(item, include_topic=True) for item in stories],
            key=lambda row: float(row.get("freshness_score") or 0),
            reverse=True,
        )[:20],
    }
