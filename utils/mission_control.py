"""Mission-control synthesis for Wild Brief operations."""
from __future__ import annotations

from collections import Counter


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _top_categories(latest: dict, limit: int = 5) -> list[str]:
    recommendations = latest.get("production_recommendations") or {}
    hot = [str(item) for item in _as_list(recommendations.get("hot_categories")) if item]
    if hot:
        return hot[:limit]
    growth = latest.get("category_avg_growth_score") or {}
    if isinstance(growth, dict):
        return [
            str(key) for key, _ in sorted(
                growth.items(),
                key=lambda kv: float(kv[1] or 0),
                reverse=True,
            )[:limit]
        ]
    return []


def build_mission_control(*,
                          latest: dict | None = None,
                          comments: dict | None = None,
                          queue: dict | None = None) -> dict:
    """Combine analytics, comments and queue health into operator actions."""
    latest = latest or {}
    comments = comments or {}
    queue = queue or {}
    learning = latest.get("learning_profile") or (
        (latest.get("production_recommendations") or {}).get("learning_profile") or {}
    )
    queue_states = queue.get("states") or {}
    queue_commands = _as_list(queue.get("commands"))
    requested_animals = [str(item) for item in _as_list(comments.get("requested_animals"))[:8]]
    viewer_prompts = [str(item) for item in _as_list(comments.get("content_prompts"))[:5]]
    priority_topics = list(dict.fromkeys(
        requested_animals
        + [str(item) for item in _as_list(learning.get("winning_title_keywords"))[:8]]
        + _top_categories(latest)
    ))[:12]

    tasks: list[dict] = []
    if viewer_prompts:
        tasks.append({
            "priority": "high",
            "task": "Turn the strongest viewer question into a Short candidate.",
            "why": viewer_prompts[0],
        })
    approved = int(queue.get("approved", 0) or 0)
    pending = int(queue.get("pending", 0) or 0)
    if pending and approved < 3:
        tasks.append({
            "priority": "high",
            "task": "Refresh discovery before the next publish window.",
            "why": "Approved queue is below the safety floor.",
        })
    if int(queue_states.get("cooldown_subject", 0) or 0) > approved:
        tasks.append({
            "priority": "medium",
            "task": "Shift discovery toward fresh subjects and new angles.",
            "why": "Cooldown pressure is higher than approved inventory.",
        })
    for command in queue_commands[:3]:
        tasks.append({"priority": "medium", "task": str(command), "why": "Queue command center"})
    if not tasks:
        tasks.append({
            "priority": "normal",
            "task": "Keep producing from the top approved candidate pool.",
            "why": "No critical operational risk detected.",
        })

    review_queue: list[dict] = []
    for item in _as_list(latest.get("top_performers"))[:5]:
        review_queue.append({
            "title": item.get("title", ""),
            "video_id": item.get("video_id", ""),
            "reason": "Top performer: consider manual cover/title refinement and pinned comment.",
        })
    for video_id in _as_list(learning.get("avoid_repeating_video_ids"))[:5]:
        review_queue.append({
            "title": "",
            "video_id": video_id,
            "reason": "Weak retention: avoid repeating this subject angle until the hook changes.",
        })

    status_counts = Counter(str(task.get("priority") or "normal") for task in tasks)
    return {
        "status": "action_required" if status_counts.get("high") else "steady",
        "priority_topics": priority_topics,
        "next_tasks": tasks[:8],
        "review_queue": review_queue[:8],
        "viewer_prompts": viewer_prompts,
    }
