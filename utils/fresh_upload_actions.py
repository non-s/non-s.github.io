"""Operator action queue derived from the fresh-upload sentinel."""

from __future__ import annotations

from datetime import datetime, timezone

PRIORITY_RANK = {"urgent": 0, "high": 1, "normal": 2, "low": 3}

STATE_PLAYBOOKS = {
    "analytics_due": {
        "lane": "measurement",
        "action_type": "pull_fresh_analytics",
        "priority": "high",
        "command": "Pull fresh YouTube Studio analytics before changing the package.",
        "automation_safe": True,
        "manual_approval_required": False,
    },
    "repair_candidate": {
        "lane": "package_rescue",
        "action_type": "prepare_package_rescue",
        "priority": "high",
        "command": "Prepare a title, thumbnail, or hook rescue variant for review.",
        "automation_safe": False,
        "manual_approval_required": True,
    },
    "hook_rescue_ready": {
        "lane": "hook_iteration",
        "action_type": "draft_next_hook",
        "priority": "high",
        "command": "Draft a tighter hook for the next same-lane attempt.",
        "automation_safe": False,
        "manual_approval_required": True,
    },
    "package_test_ready": {
        "lane": "package_test",
        "action_type": "draft_package_variant",
        "priority": "normal",
        "command": "Keep the opening idea and draft one package variant if the 24h mark misses.",
        "automation_safe": False,
        "manual_approval_required": True,
    },
    "opening_rewrite_next": {
        "lane": "opening_iteration",
        "action_type": "rewrite_next_opening",
        "priority": "normal",
        "command": "Rewrite the next version around a clearer first-frame cue and first sentence.",
        "automation_safe": False,
        "manual_approval_required": True,
    },
    "accelerating": {
        "lane": "amplify",
        "action_type": "queue_sequel_bridge",
        "priority": "high",
        "command": "Queue a sequel or related-video bridge while momentum is active.",
        "automation_safe": False,
        "manual_approval_required": True,
    },
    "awaiting_1h": {
        "lane": "observe",
        "action_type": "hold_until_first_hour",
        "priority": "low",
        "command": "Hold creative intervention until the first-hour checkpoint exists.",
        "automation_safe": True,
        "manual_approval_required": False,
    },
    "watch": {
        "lane": "observe",
        "action_type": "watch_next_checkpoint",
        "priority": "low",
        "command": "Keep observing through the next checkpoint.",
        "automation_safe": True,
        "manual_approval_required": False,
    },
}


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
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


def _priority_for(state: str, checkpoint: dict, source_priority: str) -> str:
    if str(checkpoint.get("state") or "") == "overdue":
        return "urgent"
    if state == "analytics_due" and str(checkpoint.get("state") or "") == "due":
        return "high"
    if source_priority in PRIORITY_RANK:
        return source_priority
    return str(STATE_PLAYBOOKS.get(state, STATE_PLAYBOOKS["watch"]).get("priority") or "normal")


def _action_id(item: dict, state: str, checkpoint: dict) -> str:
    video_id = str(item.get("video_id") or "unknown")
    label = str(checkpoint.get("label") or "next")
    return f"fresh-upload:{video_id}:{state}:{label}"


def _action_from_item(item: dict) -> dict:
    state = str(item.get("state") or "watch")
    playbook = STATE_PLAYBOOKS.get(state, STATE_PLAYBOOKS["watch"])
    checkpoint = _as_dict(item.get("next_checkpoint"))
    priority = _priority_for(state, checkpoint, str(item.get("priority") or ""))
    video_id = str(item.get("video_id") or "")
    command = str(item.get("action") or playbook["command"])
    if state == "analytics_due" and checkpoint.get("label"):
        command = f"{command} Check the {checkpoint.get('label')} sample first."
    wait_until = checkpoint.get("due_at") if priority == "low" else ""
    return {
        "id": _action_id(item, state, checkpoint),
        "priority": priority,
        "lane": playbook["lane"],
        "action_type": playbook["action_type"],
        "video_id": video_id,
        "title": str(item.get("title") or ""),
        "category": str(item.get("category") or ""),
        "series": str(item.get("series") or ""),
        "url": str(item.get("url") or (f"https://www.youtube.com/shorts/{video_id}" if video_id else "")),
        "state": state,
        "checkpoint_label": str(checkpoint.get("label") or ""),
        "checkpoint_state": str(checkpoint.get("state") or ""),
        "due_at": str(checkpoint.get("due_at") or ""),
        "wait_until": str(wait_until or ""),
        "age_hours": _num(item.get("age_hours")),
        "current_views": int(_num(item.get("current_views"))),
        "target_views": int(_num(checkpoint.get("target_views"))),
        "opening_retention_score": _num(item.get("opening_retention_score")),
        "recommended_action": command,
        "why": str(item.get("hypothesis") or "Fresh-upload checkpoint needs operator attention."),
        "free_only": True,
        "free_resource": "Committed analytics JSON, YouTube Studio free analytics, and GitHub Actions dashboard refresh.",
        "automation_safe": bool(playbook["automation_safe"]),
        "manual_approval_required": bool(playbook["manual_approval_required"]),
    }


def _sort_key(action: dict) -> tuple[int, datetime, float, str]:
    due = _parse_dt(action.get("due_at")) or datetime.max.replace(tzinfo=timezone.utc)
    return (
        PRIORITY_RANK.get(str(action.get("priority") or "normal"), 2),
        due,
        -float(action.get("opening_retention_score") or 0),
        str(action.get("video_id") or ""),
    )


def build_fresh_upload_actions(watchlist: dict | None, *, now: datetime | None = None, max_actions: int = 20) -> dict:
    """Turn fresh upload watch states into a prioritized zero-cost action queue."""

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    watchlist = watchlist or {}
    items = [_action_from_item(item) for item in _as_list(watchlist.get("items")) if isinstance(item, dict)]
    items.sort(key=_sort_key)
    items = items[:max_actions]
    counts = {
        "total": len(items),
        "urgent": sum(1 for item in items if item["priority"] == "urgent"),
        "high": sum(1 for item in items if item["priority"] == "high"),
        "manual_review": sum(1 for item in items if item["manual_approval_required"]),
        "automation_safe": sum(1 for item in items if item["automation_safe"]),
    }
    return {
        "generated_at": now.isoformat(),
        "source_generated_at": str(watchlist.get("generated_at") or ""),
        "source": "fresh_upload_watchlist",
        "free_only": True,
        "counts": counts,
        "items": items,
    }
