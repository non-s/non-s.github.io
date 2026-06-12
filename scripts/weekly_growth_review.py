#!/usr/bin/env python3
"""Generate a weekly Wild Brief decision summary from normalized analytics."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ab_selector import BayesianABSelector  # noqa: E402
from utils.analytics_schema import read_jsonl  # noqa: E402
from utils.channel_objective import load_channel_objective, reach_goal_status  # noqa: E402
from utils.studio_reach_schema import summarize_reach  # noqa: E402


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _metric_score(row: dict) -> float:
    metrics = row.get("metrics") or {}
    derived = row.get("derived") or {}
    return (
        _num(metrics.get("average_view_percentage")) * 0.45
        + _num(derived.get("replay_rate_proxy")) * 22
        + _num(derived.get("sub_per_1k_engaged")) * 4
        + _num(derived.get("comment_rate_per_1k_engaged")) * 2
    )


def _top_average(rows: list[dict], field: str, limit: int = 5) -> list[dict]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        key = str(row.get(field) or "unknown")
        grouped[key].append(_metric_score(row))
    return [
        {"value": key, "score": _avg(values), "n": len(values)}
        for key, values in sorted(grouped.items(), key=lambda kv: _avg(kv[1]), reverse=True)[:limit]
    ]


def build_review(root: Path = ROOT) -> dict:
    analytics = root / "_data" / "analytics"
    rows = read_jsonl(analytics / "video_metrics.jsonl")
    reach_rows = read_jsonl(analytics / "studio_reach_daily.jsonl")
    reach_summary = summarize_reach(reach_rows)
    objective = load_channel_objective(root / "_data" / "channel_objective.json")
    reach_goal = reach_goal_status(objective, reach_summary)
    selector = BayesianABSelector()
    axes = [
        "hook_style",
        "opening_visual_pattern",
        "subtitle_density",
        "loop_style",
        "cta_pattern",
        "end_card_style",
        "title_shape",
        "narrator_voice",
    ]
    experiments = {
        axis: selector.rank_axis(rows, axis, min_samples=3, min_days=1, min_engaged_views=0) for axis in axes
    }
    paused_losers = [
        {"axis": axis, "variant": variant}
        for axis, payload in experiments.items()
        for variant in (payload.get("paused_losers") or [])
    ]
    low_openings = [
        {
            "video_id": row.get("video_id"),
            "title": row.get("title"),
            "average_view_percentage": (row.get("metrics") or {}).get("average_view_percentage", 0),
        }
        for row in rows
        if _num((row.get("metrics") or {}).get("average_view_percentage"))
        and _num((row.get("metrics") or {}).get("average_view_percentage")) < 60
    ][:10]
    hook_counter = Counter()
    for row in rows:
        hook = (row.get("variants") or {}).get("hook_style")
        if hook:
            hook_counter[hook] += 1
    next_recommendations = []
    for cat in _top_average(rows, "category", limit=3):
        next_recommendations.append(
            {
                "category": cat["value"],
                "reason": f"weekly growth score {cat['score']}",
                "package_hint": "Lead with a visible subject cue and a callback loop.",
            }
        )
    review = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "winning_categories": _top_average(rows, "category"),
        "winning_formats": _top_average(rows, "format"),
        "winning_hooks": [{"value": key, "n": value} for key, value in hook_counter.most_common(5)],
        "loop_patterns": experiments.get("loop_style", {}),
        "losing_openings": low_openings,
        "reach_summary": reach_summary,
        "reach_goal": reach_goal,
        "experiments": experiments,
        "paused_losers": paused_losers,
        "next_three_experiments": [
            "Compare action_first vs animal_closeup for opening_visual_pattern.",
            "Compare callback vs mirror_opening for loop_style.",
            "Compare mechanism_reveal vs curiosity_gap for title_shape.",
        ],
        "next_ten_package_recommendations": next_recommendations[:10],
    }
    analytics.mkdir(parents=True, exist_ok=True)
    (analytics / "weekly_summary.json").write_text(
        json.dumps(review, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (root / "_data" / "experiments_recommendations.json").write_text(
        json.dumps(
            {"generated_at": review["generated_at"], "experiments": experiments},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (analytics / "weekly_next_recommendations.json").write_text(
        json.dumps(
            {"generated_at": review["generated_at"], "recommendations": next_recommendations[:10]},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    reports_dir = root / "_data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"weekly-growth-{datetime.now(timezone.utc).date().isoformat()}.md"
    lines = [
        "# Weekly Growth Review",
        "",
        f"Generated: {review['generated_at']}",
        "",
        "## Winners",
        "",
    ]
    for item in review["winning_categories"][:5]:
        lines.append(f"- Category `{item['value']}`: score {item['score']} across {item['n']} rows")
    lines += ["", "## Next Experiments", ""]
    lines += [f"- {item}" for item in review["next_three_experiments"]]
    lines += ["", "## Losing Openings", ""]
    if low_openings:
        lines += [
            f"- `{item['video_id']}`: {item['title']} ({item['average_view_percentage']}%)" for item in low_openings[:8]
        ]
    else:
        lines.append("- No low-retention openings in normalized rows.")
    if reach_summary.get("rows") or reach_goal.get("stayed_to_watch_rate"):
        lines += ["", "## Shorts Reach Objective", ""]
        lines.append(
            "- Stayed to watch: "
            f"{round(float(reach_goal.get('stayed_to_watch_rate', 0) or 0) * 100, 1)}%; "
            f"floor: {round(float(reach_goal.get('stayed_to_watch_floor', 0) or 0) * 100, 1)}%; "
            f"swiped away: {round(float(reach_goal.get('swipe_away_rate', 0) or 0) * 100, 1)}%; "
            f"source: {reach_goal.get('source')}."
        )
        for command in (reach_goal.get("commands") or [])[:3]:
            lines.append(f"- {command}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    review = build_review(Path(args.root).resolve())
    print(f"weekly_growth_review: {review['rows']} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
