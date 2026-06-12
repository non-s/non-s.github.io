"""Session handoff graph for post-upload growth."""

from __future__ import annotations

from collections import Counter

from utils.editorial_guard import editorial_issues


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def session_handoff_score(source: dict, candidate: dict) -> float:
    score = 0.0
    if source.get("video_id") == candidate.get("video_id"):
        return -1.0
    if source.get("series") and source.get("series") == candidate.get("series"):
        score += 34
    if source.get("category") and source.get("category") == candidate.get("category"):
        score += 28
    if source.get("story_format") and source.get("story_format") == candidate.get("story_format"):
        score += 18
    score += min(12, _num(candidate.get("views")) / 250)
    score += min(8, _num(candidate.get("subscribers_gained")) * 2)
    return round(score, 2)


def choose_handoff(source: dict, candidates: list[dict], blocked_targets: set[str] | None = None) -> dict:
    blocked_targets = blocked_targets or set()
    ranked = []
    for candidate in candidates:
        video_id = str(candidate.get("video_id") or "")
        if video_id in blocked_targets:
            continue
        title = str(candidate.get("title") or "").strip()
        if title and not _recommendable_title(title):
            continue
        score = session_handoff_score(source, candidate)
        if score >= 0:
            ranked.append(
                {
                    "video_id": video_id,
                    "title": candidate.get("title", ""),
                    "url": candidate.get("url") or f"https://www.youtube.com/shorts/{candidate.get('video_id', '')}",
                    "score": score,
                    "reason": _reason(source, candidate),
                }
            )
    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked[0] if ranked else {}


def _reason(source: dict, candidate: dict) -> str:
    bits = []
    if source.get("series") and source.get("series") == candidate.get("series"):
        bits.append("same series")
    if source.get("category") and source.get("category") == candidate.get("category"):
        bits.append("same category")
    if source.get("story_format") and source.get("story_format") == candidate.get("story_format"):
        bits.append("same format")
    return ", ".join(bits) or "best available session bridge"


def pinned_comment_payload(meta: dict, handoff: dict | None = None) -> str:
    handoff = handoff or {}
    title = str(handoff.get("title") or "").strip()
    url = str(handoff.get("url") or "").strip()
    if title and url:
        return f"Next: {title[:72]} {url}"
    series = str(meta.get("series") or meta.get("category") or "Wild Brief").strip()
    return f"Next Wild Brief: follow the {series} thread."


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def build_session_graph(markers: list[dict], *, max_actions: int = 20) -> dict:
    nodes = [
        {
            "video_id": item.get("video_id", ""),
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "series": item.get("series", ""),
            "story_format": item.get("story_format", ""),
            "views": item.get("views", 0),
            "subscribers_gained": item.get("subscribers_gained", 0),
            "url": item.get("url") or f"https://www.youtube.com/shorts/{item.get('video_id', '')}",
        }
        for item in markers
        if item.get("video_id") and (not item.get("title") or _recommendable_title(str(item.get("title") or "")))
    ]
    edges = []
    actions = []
    target_counts: Counter[str] = Counter()
    target_reuse_limit = 2
    action_score_threshold = 55
    for source in nodes[-max_actions:]:
        blocked_targets = {video_id for video_id, count in target_counts.items() if count >= target_reuse_limit}
        target = choose_handoff(source, nodes, blocked_targets=blocked_targets)
        if not target:
            continue
        target_counts[str(target["video_id"])] += 1
        edge = {
            "source_video_id": source["video_id"],
            "target_video_id": target["video_id"],
            "score": target["score"],
            "reason": target["reason"],
        }
        edges.append(edge)
        if float(target["score"] or 0) >= action_score_threshold:
            actions.append(
                {
                    "video_id": source["video_id"],
                    "action": "operator_assist_pinned_comment",
                    "target_video_id": target["video_id"],
                    "score": target["score"],
                    "comment": pinned_comment_payload(source, target),
                    "apply_safe": False,
                }
            )
    sequel_candidates = [
        {
            "source_video_id": node["video_id"],
            "title": node["title"],
            "category": node["category"],
            "series": node["series"],
            "sequel_timing": "immediate" if _num(node.get("views")) >= 1000 else "late",
            "prompt": f"Make a sequel with a new subject but same payoff: {node['title']}",
        }
        for node in nodes[-max_actions:]
        if _recommendable_title(node["title"])
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "next_session_actions": actions,
        "sequel_candidates": sequel_candidates,
        "action_score_threshold": action_score_threshold,
        "target_reuse_limit": target_reuse_limit,
        "coverage": round(len(actions) / max(len(nodes[-max_actions:]), 1), 4),
    }
