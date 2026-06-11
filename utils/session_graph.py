"""Session handoff graph for post-upload growth."""

from __future__ import annotations


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


def choose_handoff(source: dict, candidates: list[dict]) -> dict:
    ranked = []
    for candidate in candidates:
        score = session_handoff_score(source, candidate)
        if score >= 0:
            ranked.append(
                {
                    "video_id": candidate.get("video_id", ""),
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
        if item.get("video_id")
    ]
    edges = []
    actions = []
    for source in nodes[-max_actions:]:
        target = choose_handoff(source, nodes)
        if not target:
            continue
        edge = {
            "source_video_id": source["video_id"],
            "target_video_id": target["video_id"],
            "score": target["score"],
            "reason": target["reason"],
        }
        edges.append(edge)
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
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "next_session_actions": actions,
        "sequel_candidates": sequel_candidates,
        "coverage": round(len(actions) / max(len(nodes[-max_actions:]), 1), 4),
    }
