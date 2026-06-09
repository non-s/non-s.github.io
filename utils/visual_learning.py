"""Learn which visual CTR frame profiles perform after publication."""
from __future__ import annotations

from collections import defaultdict


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def visual_profile_key(marker: dict) -> str:
    profile = ((marker.get("visual_ctr") or {}).get("profile") or {})
    primary = str(profile.get("primary") or "").strip()
    if primary:
        return primary
    quality = str(profile.get("quality") or "").strip()
    if quality:
        return quality
    return "unknown"


def build_visual_learning(observations: list[dict], *, min_samples: int = 2) -> dict:
    """Aggregate performance by visual CTR profile."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in observations:
        key = str(item.get("visual_profile") or "unknown")
        grouped[key].append(item)

    profiles = []
    for key, rows in grouped.items():
        growth = [_num(row.get("growth_score")) for row in rows]
        retention = [_num(row.get("average_view_percentage")) for row in rows]
        views = [_num(row.get("views")) for row in rows]
        ctr_scores = [_num(row.get("visual_ctr_score")) for row in rows if row.get("visual_ctr_score") is not None]
        profiles.append({
            "profile": key,
            "n": len(rows),
            "mean_growth_score": round(sum(growth) / len(growth), 3) if growth else 0.0,
            "mean_retention": round(sum(retention) / len(retention), 3) if retention else 0.0,
            "mean_views": round(sum(views) / len(views), 3) if views else 0.0,
            "mean_visual_ctr_score": round(sum(ctr_scores) / len(ctr_scores), 3) if ctr_scores else 0.0,
        })
    profiles.sort(
        key=lambda item: (
            item["n"] >= min_samples,
            item["mean_growth_score"],
            item["mean_retention"],
            item["mean_visual_ctr_score"],
        ),
        reverse=True,
    )
    winner = ""
    for item in profiles:
        if item["profile"] != "unknown" and item["n"] >= min_samples:
            winner = item["profile"]
            break
    return {
        "min_samples": min_samples,
        "winner": winner,
        "profiles": profiles,
        "policy": (
            "Favor the winning visual profile when available; otherwise keep selecting "
            "the highest local CTR score while collecting samples."
        ),
    }
