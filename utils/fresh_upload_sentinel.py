"""Fresh-upload observation plan for the first 24 hours after publishing."""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

CHECKPOINT_HOURS = (1, 6, 24)
WATCH_WINDOW_HOURS = 72
MIN_TARGETS = {"1h": 20, "6h": 80, "24h": 300}


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _parse_dt(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _uploaded_at(marker: dict) -> datetime | None:
    for key in ("uploaded_at", "published_at", "publish_ts_utc", "generated_at"):
        parsed = _parse_dt(marker.get(key))
        if parsed:
            return parsed
    intent = marker.get("upload_intent") if isinstance(marker.get("upload_intent"), dict) else {}
    return _parse_dt(intent.get("created_at"))


def _opening_retention(marker: dict) -> dict:
    candidates = [
        (
            (marker.get("publish_score") or {}).get("opening_retention")
            if isinstance(marker.get("publish_score"), dict)
            else {}
        ),
        (
            (marker.get("youtube_brain") or {}).get("opening_retention")
            if isinstance(marker.get("youtube_brain"), dict)
            else {}
        ),
        (
            (((marker.get("opening_audit") or {}).get("checks") or {}).get("retention_opening"))
            if isinstance(marker.get("opening_audit"), dict)
            else {}
        ),
        (
            ((marker.get("opening_gate_v2") or {}).get("subscores") or {}).get("retention_opening")
            if isinstance(marker.get("opening_gate_v2"), dict)
            else {}
        ),
        (
            (marker.get("frame_zero_packaging") or {}).get("retention_opening")
            if isinstance(marker.get("frame_zero_packaging"), dict)
            else {}
        ),
    ]
    for item in candidates:
        if isinstance(item, dict) and item:
            return item
    return {}


def _warning_lookup(early_warning: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    groups = {
        "risk_of_dying_early": "repair_risk",
        "remake_candidates": "remake_candidate",
        "potential_accelerators": "accelerator",
        "sequence_candidates": "sequence_candidate",
        "watchlist_low_confidence": "low_confidence_watch",
    }
    for key, state in groups.items():
        for item in early_warning.get(key) or []:
            if not isinstance(item, dict):
                continue
            video_id = str(item.get("video_id") or "")
            if video_id and video_id not in out:
                out[video_id] = {**item, "warning_state": state}
    return out


def _targets(early_performance: dict) -> dict[str, int]:
    videos = [item for item in (early_performance.get("videos") or {}).values() if isinstance(item, dict)]
    mature_views = [int(_num(item.get("views"))) for item in videos if _num(item.get("age_hours")) >= 24]
    target_24 = int(statistics.median(mature_views)) if mature_views else MIN_TARGETS["24h"]
    target_24 = max(MIN_TARGETS["24h"], min(1500, target_24))
    return {
        "1h": max(MIN_TARGETS["1h"], int(round(target_24 * 0.08))),
        "6h": max(MIN_TARGETS["6h"], int(round(target_24 * 0.35))),
        "24h": target_24,
    }


def _checkpoint(row: dict, uploaded: datetime, now: datetime, label: str, target: int) -> dict:
    hours = int(label.removesuffix("h"))
    due_at = uploaded + timedelta(hours=hours)
    view_metric = (((row.get("checkpoints") or {}).get(label) or {}).get("views") or {}) if row else {}
    source = str(view_metric.get("source") or "missing")
    observed = source == "observed"
    if observed:
        state = "observed"
    elif now < due_at:
        state = "pending"
    else:
        grace = timedelta(minutes=45 if hours == 1 else 90 if hours == 6 else 180)
        state = "overdue" if now > due_at + grace else "due"
    value = int(_num(view_metric.get("value") if view_metric else row.get("views") if row else 0))
    return {
        "label": label,
        "due_at": due_at.isoformat(),
        "state": state,
        "views": value,
        "target_views": target,
        "source": source,
        "delta_to_target": value - target if state in {"observed", "due", "overdue"} else 0,
    }


def _next_checkpoint(checkpoints: list[dict]) -> dict:
    for state in ("due", "overdue", "pending"):
        for item in checkpoints:
            if item.get("state") == state:
                return item
    return checkpoints[-1] if checkpoints else {}


def _state_and_action(
    *,
    checkpoints: list[dict],
    warning: dict,
    opening_score: float,
    row: dict,
) -> tuple[str, str, str]:
    if warning:
        warning_state = str(warning.get("warning_state") or "")
        if warning_state in {"accelerator", "sequence_candidate"}:
            return (
                "accelerating",
                "Queue a sequel or related-video bridge while the session has momentum.",
                "Performance signal is already positive; amplify without changing the opening.",
            )
        if warning_state in {"repair_risk", "remake_candidate"}:
            action = str(warning.get("action") or "Prepare a title, thumbnail, or hook rescue variant.")
            return (
                "repair_candidate",
                action,
                "Observed velocity is weak enough to prepare a package intervention.",
            )
    due_states = {item.get("state") for item in checkpoints}
    if "overdue" in due_states or "due" in due_states:
        return (
            "analytics_due",
            "Run the analytics pull before making a creative decision.",
            "The next checkpoint is due, but the system still needs a fresh measured sample.",
        )
    if opening_score and opening_score < 75:
        return (
            "opening_rewrite_next",
            "Rewrite the next version around a clearer first-frame cue and first sentence.",
            "The published opening was below the retention promise floor.",
        )
    views = int(_num(row.get("views") if row else 0))
    age = _num(row.get("age_hours") if row else 0)
    if age >= 6 and views and checkpoints[1].get("delta_to_target", 0) < 0:
        if opening_score >= 90:
            return (
                "package_test_ready",
                "Keep the opening idea; prepare a title or thumbnail variant if 24h misses.",
                "Opening retention scored strong, so weak velocity points first to packaging/distribution.",
            )
        return (
            "hook_rescue_ready",
            "Prepare a tighter hook variant for the next same-lane attempt.",
            "Velocity is soft and the opening score leaves room for a stronger promise.",
        )
    first = checkpoints[0] if checkpoints else {}
    if first.get("state") == "pending":
        return (
            "awaiting_1h",
            "Wait for the first-hour checkpoint; do not repair before data exists.",
            "The upload is still inside the no-panic observation window.",
        )
    return (
        "watch",
        "Keep observing through the next checkpoint.",
        "No intervention signal is strong enough yet.",
    )


def build_fresh_upload_watchlist(
    markers: list[dict],
    *,
    early_performance: dict | None = None,
    early_warning: dict | None = None,
    now: datetime | None = None,
    window_hours: int = WATCH_WINDOW_HOURS,
    max_items: int = 10,
) -> dict:
    """Build a first-24h watchlist from uploaded marker files and early analytics."""

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    early_performance = early_performance or {}
    warning_by_id = _warning_lookup(early_warning or {})
    targets = _targets(early_performance)
    rows = early_performance.get("videos") if isinstance(early_performance.get("videos"), dict) else {}
    items = []
    for marker in markers:
        video_id = str(marker.get("video_id") or "").strip()
        if not video_id:
            continue
        uploaded = _uploaded_at(marker)
        if not uploaded:
            continue
        age_hours = max(0.0, (now - uploaded).total_seconds() / 3600)
        if age_hours > window_hours:
            continue
        row = rows.get(video_id) if isinstance(rows.get(video_id), dict) else {}
        opening = _opening_retention(marker)
        opening_score = _num(opening.get("score"))
        checkpoints = [
            _checkpoint(row, uploaded, now, label, targets[label])
            for label in (f"{hours}h" for hours in CHECKPOINT_HOURS)
        ]
        warning = warning_by_id.get(video_id, {})
        state, action, hypothesis = _state_and_action(
            checkpoints=checkpoints,
            warning=warning,
            opening_score=opening_score,
            row=row,
        )
        priority = "high" if state in {"analytics_due", "repair_candidate", "hook_rescue_ready"} else "normal"
        if state in {"awaiting_1h", "watch"}:
            priority = "low"
        current_views = int(_num(row.get("views") if row else marker.get("views")))
        item = {
            "video_id": video_id,
            "title": str(marker.get("title") or row.get("title") or ""),
            "url": str(marker.get("url") or f"https://www.youtube.com/shorts/{video_id}"),
            "category": str(marker.get("category") or row.get("category") or ""),
            "series": str(marker.get("series") or row.get("series") or ""),
            "uploaded_at": uploaded.isoformat(),
            "age_hours": round(age_hours, 3),
            "current_views": current_views,
            "views_per_hour": round(_num(row.get("views_per_hour")) if row else 0.0, 3),
            "opening_retention_score": round(opening_score, 2),
            "opening_retention_state": str(opening.get("state") or "unknown"),
            "checkpoints": checkpoints,
            "next_checkpoint": _next_checkpoint(checkpoints),
            "state": state,
            "priority": priority,
            "action": action,
            "hypothesis": hypothesis,
        }
        if warning:
            item["warning"] = warning
        items.append(item)
    items.sort(key=lambda item: item["uploaded_at"], reverse=True)
    items = items[:max_items]
    counts = {
        "tracked": len(items),
        "analytics_due": sum(1 for item in items if item["state"] == "analytics_due"),
        "repair_candidates": sum(1 for item in items if item["state"] == "repair_candidate"),
        "awaiting_1h": sum(1 for item in items if item["state"] == "awaiting_1h"),
        "high_priority": sum(1 for item in items if item["priority"] == "high"),
    }
    return {
        "generated_at": now.isoformat(),
        "window_hours": window_hours,
        "checkpoint_hours": list(CHECKPOINT_HOURS),
        "targets": targets,
        "counts": counts,
        "items": items,
    }
