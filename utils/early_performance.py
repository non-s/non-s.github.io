"""Early distribution velocity and breakout memory for Wild Brief."""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from utils.confidence_engine import assess_confidence
from utils.editorial_guard import editorial_issues

EARLY_PERFORMANCE_PATH = Path("_data/early_performance.json")
EARLY_WARNING_PATH = Path("_data/early_warning.json")
WINNER_PATTERNS_PATH = Path("_data/winner_patterns.json")
CHECKPOINTS = (1, 6, 24, 48)
BREAKOUT_THRESHOLDS = (500, 1000, 5000, 10000, 50000)


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", str(text or "").lower())


def _pattern(text: str) -> str:
    words = _words(text)
    out = []
    for word in words[:8]:
        if word in {"watch", "why", "how", "before", "after"}:
            out.append(word)
        elif word in {"because", "reason", "explains", "turns", "changes"}:
            out.append("{payoff}")
        elif len(word) > 3:
            out.append("{subject}")
        else:
            out.append(word)
    return " ".join(out)


def _stats(marker: dict) -> dict:
    return marker.get("analytics") if isinstance(marker.get("analytics"), dict) else {}


def _video_row(marker: dict, now: datetime) -> dict:
    stats = _stats(marker)
    uploaded_at = str(marker.get("uploaded_at") or marker.get("published_at") or "")
    uploaded = _parse_dt(uploaded_at)
    age_hours = max(0.01, (now - uploaded).total_seconds() / 3600) if uploaded else 0.0
    views = _num(stats.get("views") or stats.get("viewCount") or marker.get("views"))
    likes = _num(stats.get("likes") or stats.get("likeCount") or marker.get("likes"))
    comments = _num(stats.get("comments") or stats.get("commentCount") or marker.get("comments"))
    subs = _num(stats.get("subscribersGained") or marker.get("subscribers_gained"))
    return {
        "video_id": str(marker.get("video_id") or ""),
        "title": str(marker.get("title") or ""),
        "category": str(marker.get("category") or "").lower(),
        "story_format": str(marker.get("story_format") or "").lower(),
        "series": re.sub(r"\s+#\d+$", "", str(marker.get("series") or "Unassigned")),
        "hook": str(marker.get("hook") or ""),
        "thumbnail_text": str(marker.get("thumbnail_text") or ""),
        "cta_prompt": str(marker.get("cta_prompt") or ""),
        "uploaded_at": uploaded_at,
        "age_hours": round(age_hours, 3),
        "views": int(views),
        "likes": int(likes),
        "comments": int(comments),
        "subscribers": int(subs),
        "views_per_hour": round(views / max(age_hours, 1), 3) if age_hours else 0.0,
    }


def _title_issues(title: str) -> list[str]:
    title = str(title or "").strip()
    if not title:
        return []
    return editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _load_previous(path: Path = EARLY_PERFORMANCE_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _snapshots(previous: dict, row: dict, now: datetime) -> list[dict]:
    by_video = previous.get("videos") if isinstance(previous.get("videos"), dict) else {}
    old = ((by_video.get(row["video_id"]) or {}).get("snapshots") or []) if row["video_id"] else []
    snapshots = [item for item in old if isinstance(item, dict)]
    current = {
        "at": now.isoformat(),
        "age_hours": row["age_hours"],
        "views": row["views"],
        "likes": row["likes"],
        "comments": row["comments"],
        "subscribers": row["subscribers"],
    }
    if not snapshots or snapshots[-1].get("views") != current["views"] or snapshots[-1].get("age_hours") != current["age_hours"]:
        snapshots.append(current)
    return snapshots[-30:]


def _checkpoint_value(snapshots: list[dict], current: dict, hours: int, metric: str = "views") -> dict:
    eligible = [s for s in snapshots if _num(s.get("age_hours")) >= hours]
    if eligible:
        best = min(eligible, key=lambda s: abs(_num(s.get("age_hours")) - hours))
        age = _num(best.get("age_hours"))
        if age <= max(hours * 1.35, hours + 2):
            return {"value": int(_num(best.get(metric))), "source": "observed", "age_hours": age}
    age = _num(current.get("age_hours"))
    if age <= 0:
        return {"value": 0, "source": "missing", "age_hours": 0}
    estimate = min(_num(current.get(metric)), _num(current.get(metric)) * hours / max(age, 1))
    return {"value": int(estimate), "source": "estimated", "age_hours": age}


def _velocity_score(row: dict, checkpoints: dict) -> int:
    v1 = checkpoints["1h"]["views"]["value"]
    v6 = checkpoints["6h"]["views"]["value"]
    v24 = checkpoints["24h"]["views"]["value"]
    likes24 = checkpoints["24h"]["likes"]["value"]
    comments24 = checkpoints["24h"]["comments"]["value"]
    subs24 = checkpoints["24h"]["subscribers"]["value"]
    score = (
        min(35, math.log10(max(v1, 1)) * 12)
        + min(30, math.log10(max(v6, 1)) * 10)
        + min(20, math.log10(max(v24, 1)) * 6)
        + min(10, likes24 * 0.7 + comments24 * 2)
        + min(10, subs24 * 3)
    )
    if row["age_hours"] > 6 and row["views"] < 500:
        score -= 12
    return int(max(0, min(100, round(score))))


def _acceleration(snapshots: list[dict], row: dict) -> dict:
    if len(snapshots) < 2:
        avg = row["views"] / max(row["age_hours"], 1)
        return {
            "recent_views_per_hour": round(avg, 3),
            "lifetime_views_per_hour": round(avg, 3),
            "acceleration": 0.0,
            "state": "insufficient_snapshots",
        }
    prev, cur = snapshots[-2], snapshots[-1]
    dt = max(0.01, _num(cur.get("age_hours")) - _num(prev.get("age_hours")))
    recent = max(0.0, (_num(cur.get("views")) - _num(prev.get("views"))) / dt)
    lifetime = row["views"] / max(row["age_hours"], 1)
    accel = recent / max(lifetime, 0.01)
    if row["age_hours"] >= 24 and accel >= 1.8 and recent >= 20:
        state = "second_wave"
    elif accel >= 1.15 and recent >= 10:
        state = "accelerating"
    elif row["age_hours"] >= 6 and recent < 3 and row["views"] < 1000:
        state = "dying_early"
    else:
        state = "steady"
    return {
        "recent_views_per_hour": round(recent, 3),
        "lifetime_views_per_hour": round(lifetime, 3),
        "acceleration": round(accel, 3),
        "state": state,
    }


def _breakout_probabilities(row: dict, historical: list[dict]) -> dict:
    mature = [item for item in historical if item.get("age_hours", 0) >= 24 and item.get("views", 0) > 0]
    if not mature:
        return {f"pass_{t}": 0.0 for t in BREAKOUT_THRESHOLDS}
    vph_values = sorted(item.get("views_per_hour", 0) for item in mature)
    median_vph = vph_values[len(vph_values) // 2] or 1
    velocity_factor = max(0.45, min(2.2, row.get("views_per_hour", 0) / max(median_vph, 1)))
    probs = {}
    n = len(mature)
    for threshold in BREAKOUT_THRESHOLDS:
        base = sum(1 for item in mature if item.get("views", 0) >= threshold) / n
        current_floor = 1.0 if row["views"] >= threshold else 0.0
        adjusted = max(current_floor, min(0.98, base * velocity_factor))
        probs[f"pass_{threshold}"] = round(adjusted, 3)
    stop_500 = 1 - probs["pass_1000"]
    probs["stop_under_500"] = round(max(0.0, min(1.0, stop_500)), 3)
    return probs


def _early_confidence(row: dict, checkpoints: dict, snapshots: list[dict]) -> dict:
    observed = 0
    estimated = 0
    missing = 0
    for checkpoint in checkpoints.values():
        for metric in checkpoint.values():
            source = metric.get("source")
            if source == "observed":
                observed += 1
            elif source == "estimated":
                estimated += 1
            else:
                missing += 1
    if len(snapshots) >= 2:
        observed += 1
    elif row.get("age_hours", 0) >= 24:
        estimated += 1
    return assess_confidence(
        "video",
        max(1, len(snapshots)),
        observed=observed,
        estimated=estimated,
        missing=missing,
        minimum_sample_size=2,
    )


def build_early_performance(markers: list[dict], previous: dict | None = None,
                            now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    previous = previous or {}
    rows = [_video_row(marker, now) for marker in markers if marker.get("video_id")]
    historical = [row for row in rows if row["age_hours"] >= 24]
    videos = {}
    for row in rows:
        snapshots = _snapshots(previous, row, now)
        checkpoints = {}
        for hours in CHECKPOINTS:
            label = f"{hours}h"
            checkpoints[label] = {
                "views": _checkpoint_value(snapshots, row, hours, "views"),
            }
            if hours == 24:
                checkpoints[label]["likes"] = _checkpoint_value(snapshots, row, hours, "likes")
                checkpoints[label]["comments"] = _checkpoint_value(snapshots, row, hours, "comments")
                checkpoints[label]["subscribers"] = _checkpoint_value(snapshots, row, hours, "subscribers")
        acceleration = _acceleration(snapshots, row)
        velocity = _velocity_score(row, checkpoints)
        breakout = _breakout_probabilities(row, historical)
        confidence = _early_confidence(row, checkpoints, snapshots)
        videos[row["video_id"]] = {
            **row,
            "checkpoints": checkpoints,
            "early_velocity_score": velocity,
            "early_confidence_score": confidence["confidence_score"],
            "confidence": confidence,
            "acceleration": acceleration,
            "breakout_probability": breakout,
            "snapshots": snapshots,
        }
    return {
        "updated_at": now.isoformat(),
        "sample_count": len(videos),
        "checkpoint_hours": list(CHECKPOINTS),
        "videos": videos,
        "top_velocity": sorted(
            ({k: v for k, v in item.items() if k != "snapshots"} for item in videos.values()),
            key=lambda item: (item["early_velocity_score"], item["views_per_hour"], item["views"]),
            reverse=True,
        )[:20],
    }


def build_winner_patterns(early: dict) -> dict:
    videos = list((early.get("videos") or {}).values())
    winners = [
        item for item in videos
        if (
            item.get("early_confidence_score", 0) >= 0.50
            and (item.get("early_velocity_score", 0) >= 62 or item.get("views", 0) >= 5000)
        )
    ]
    losers = [
        item for item in videos
        if (
            item.get("early_confidence_score", 0) >= 0.65
            and item.get("age_hours", 0) >= 24
            and item.get("views", 0) < 1000
        )
    ]

    def counts(items: list[dict], key: str) -> dict:
        return dict(Counter(str(item.get(key) or "unknown") for item in items).most_common(12))

    qualified = winners + losers
    pattern_confidence = assess_confidence(
        "distribution",
        len(qualified),
        observed=sum(1 for item in qualified if (item.get("confidence") or {}).get("data_quality") == "observed"),
        inferred=sum(1 for item in qualified if (item.get("confidence") or {}).get("data_quality") == "inferred"),
        estimated=sum(1 for item in qualified if (item.get("confidence") or {}).get("data_quality") == "estimated"),
        missing=max(0, len(videos) - len(qualified)),
    )
    return {
        "sample_count": len(videos),
        "winner_count": len(winners),
        "loser_count": len(losers),
        "confidence": pattern_confidence,
        "confidence_score": pattern_confidence["confidence_score"],
        "recommendation_strength": pattern_confidence["recommendation_strength"],
        "reasoning": pattern_confidence["reasoning"],
        "winning_hooks": dict(Counter(_pattern(item.get("hook", "")) for item in winners if item.get("hook")).most_common(12)),
        "winning_thumbnails": dict(Counter(_pattern(item.get("thumbnail_text", "")) for item in winners if item.get("thumbnail_text")).most_common(12)),
        "winning_ctas": dict(Counter(_pattern(item.get("cta_prompt", "")) for item in winners if item.get("cta_prompt")).most_common(12)),
        "winning_categories": counts(winners, "category"),
        "winning_series": counts(winners, "series"),
        "winning_formats": counts(winners, "story_format"),
        "losing_categories": counts(losers, "category"),
        "losing_series": counts(losers, "series"),
        "losing_formats": counts(losers, "story_format"),
    }


def build_early_warning(early: dict) -> dict:
    risks = []
    accelerators = []
    watchlist = []
    remakes = []
    sequences = []
    for item in (early.get("videos") or {}).values():
        state = (item.get("acceleration") or {}).get("state")
        confidence = item.get("confidence") or {}
        confidence_score = float(item.get("early_confidence_score") or confidence.get("confidence_score") or 0)
        reason = confidence.get("reasoning", "")
        title_issues = _title_issues(item.get("title", ""))
        if confidence_score < 0.45:
            if state in {"dying_early", "accelerating", "second_wave"} or item.get("early_velocity_score", 0) >= 70:
                entry = {
                    "video_id": item["video_id"],
                    "title": item["title"],
                    "state": state,
                    "confidence_score": confidence_score,
                    "reason": "low confidence early signal; keep observing",
                }
                if title_issues:
                    entry["title_issues"] = title_issues
                watchlist.append(entry)
            continue
        if title_issues:
            remakes.append({
                "video_id": item["video_id"],
                "title": item["title"],
                "action": "repair title/package before scaling angle",
                "confidence_score": confidence_score,
                "reasoning": reason,
                "title_issues": title_issues,
            })
        if confidence_score >= 0.55 and (state == "dying_early" or (item.get("age_hours", 0) >= 6 and item.get("views", 0) < 500)):
            entry = {
                "video_id": item["video_id"],
                "title": item["title"],
                "reason": "low early velocity",
                "views": item["views"],
                "confidence_score": confidence_score,
                "reasoning": reason,
            }
            if title_issues:
                entry["title_issues"] = title_issues
            risks.append(entry)
        if state in {"accelerating", "second_wave"} or item.get("early_velocity_score", 0) >= 70:
            entry = {
                "video_id": item["video_id"],
                "title": item["title"],
                "state": state,
                "score": item.get("early_velocity_score", 0),
                "confidence_score": confidence_score,
                "reasoning": reason,
            }
            if title_issues:
                entry["title_issues"] = title_issues
            accelerators.append(entry)
        if (
            not title_issues
            and confidence_score >= 0.65
            and item.get("age_hours", 0) >= 24
            and item.get("views", 0) < 1000
        ):
            remakes.append({
                "video_id": item["video_id"],
                "title": item["title"],
                "action": "remake hook/title or retire angle",
                "confidence_score": confidence_score,
                "reasoning": reason,
            })
        if (
            not title_issues
            and confidence_score >= 0.55
            and item.get("views", 0) >= 1000
            and item.get("breakout_probability", {}).get("pass_5000", 0) >= 0.25
        ):
            sequences.append({
                "video_id": item["video_id"],
                "title": item["title"],
                "action": "make sequel within same series",
                "confidence_score": confidence_score,
                "reasoning": reason,
            })
    return {
        "risk_of_dying_early": risks[:20],
        "potential_accelerators": accelerators[:20],
        "watchlist_low_confidence": watchlist[:20],
        "remake_candidates": remakes[:20],
        "sequence_candidates": sequences[:20],
    }


def write_reports(markers: list[dict],
                  early_path: Path = EARLY_PERFORMANCE_PATH,
                  warning_path: Path = EARLY_WARNING_PATH,
                  patterns_path: Path = WINNER_PATTERNS_PATH) -> dict:
    previous = _load_previous(early_path)
    early = build_early_performance(markers, previous=previous)
    warning = build_early_warning(early)
    patterns = build_winner_patterns(early)
    for path, payload in ((early_path, early), (warning_path, warning), (patterns_path, patterns)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"early_performance": early, "early_warning": warning, "winner_patterns": patterns}
