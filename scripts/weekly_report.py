#!/usr/bin/env python3
"""Generate a weekly Markdown executive report from local analytics."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial_guard import editorial_issues  # noqa: E402

REPORT_DIR = ROOT / "_data" / "reports"


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _title_issues(title: str) -> list[str]:
    title = str(title or "").strip()
    if not title:
        return []
    return editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _display_title(item: dict, key: str = "title") -> str:
    title = str(item.get(key) or "").strip()
    issues = _title_issues(title)
    if not issues:
        return title or str(item.get("video_id") or item.get("source_video_id") or "untitled")
    video_id = str(item.get("video_id") or item.get("source_video_id") or "unknown-video")
    return f"{video_id} (title needs repair: {', '.join(issues[:3])})"


def build_markdown(root: Path = ROOT) -> str:
    latest = _safe_json(root / "_data" / "analytics" / "latest.json")
    ops = _safe_json(root / "_data" / "ops_guardian.json")
    health = _safe_json(root / "_data" / "automation_health.json")
    remakes = _safe_json(root / "_data" / "remake_backlog.json")
    trends = _safe_json(root / "_data" / "trend_radar.json")
    memory = _safe_json(root / "_data" / "format_memory.json")
    fan = _safe_json(root / "_data" / "fan_growth.json")
    audience = _safe_json(root / "_data" / "audience_memory.json")
    early = _safe_json(root / "_data" / "early_performance.json")
    warning = _safe_json(root / "_data" / "early_warning.json")
    patterns = _safe_json(root / "_data" / "winner_patterns.json")
    data_quality = _safe_json(root / "_data" / "data_quality_report.json")
    now = datetime.now(timezone.utc)
    risk = ops.get("risk") or {}
    brief = latest.get("weekly_brief") or {}
    lines = [
        f"# Wild Brief Weekly Report - {now.date().isoformat()}",
        "",
        f"- Automation health: {health.get('state', 'unknown')} ({health.get('score', 0)}/100)",
        f"- Operations risk: {risk.get('level', 'unknown')} ({risk.get('score', 0)}/100)",
        f"- Total views tracked: {latest.get('total_views', 0)}",
        f"- Avg retention: {latest.get('avg_view_pct', latest.get('avg_view_percentage', 0))}%",
        f"- Subscribers gained: {latest.get('subscribers_gained', 0)}",
        f"- Learning confidence: {data_quality.get('overall_confidence_score', 0)}"
        f"{' (bootstrap)' if data_quality.get('bootstrap_mode') else ''}",
        "",
        "## What To Scale",
    ]
    scale = (ops.get("executive_report") or {}).get("what_to_scale")
    if scale is None:
        paused_names = {str(item.get("category")) for item in (ops.get("paused_topics") or [])}
        scale = [
            item for item in (latest.get("production_recommendations") or {}).get("hot_categories", [])[:8]
            if str(item) not in paused_names
        ]
    for item in scale[:8]:
        lines.append(f"- {item}")
    if not scale:
        lines.append("- Nothing to scale yet.")
    lines.extend(["", "## What To Pause"])
    paused = ops.get("paused_topics") or []
    if paused:
        for item in paused:
            lines.append(f"- {item.get('category')}: {item.get('reason')} ({item.get('retention')}% retention)")
    else:
        lines.append("- Nothing paused.")
    lines.extend(["", "## Trend Radar"])
    topics = trends.get("topics") or []
    if topics:
        for item in topics[:5]:
            title = (item.get("top_titles") or [""])[0]
            lines.append(
                f"- {item.get('animal')} ({item.get('category')}): "
                f"{item.get('trend_score')} score, {item.get('mentions')} mentions"
                + (f" - {title}" if title else "")
            )
    else:
        lines.append("- No public trend signal captured yet.")
    lines.extend(["", "## Format Memory"])
    categories = sorted(
        (memory.get("category_scores") or {}).items(),
        key=lambda item: item[1],
        reverse=True,
    )
    formats = sorted(
        (memory.get("format_scores") or {}).items(),
        key=lambda item: item[1],
        reverse=True,
    )
    if categories:
        lines.append("- Winning categories: " + ", ".join(f"{k} ({v})" for k, v in categories[:5]))
    else:
        lines.append("- Winning categories: not enough data yet.")
    if formats:
        lines.append("- Winning formats: " + ", ".join(f"{k} ({v})" for k, v in formats[:5]))
    else:
        lines.append("- Winning formats: not enough data yet.")
    hooks = list((memory.get("winning_hook_patterns") or {}).keys())[:3]
    if hooks:
        lines.append("- Hook patterns to reuse: " + "; ".join(hooks))
    lines.extend(["", "## Subscriber Conversion"])
    fan_rows = fan.get("videos_ranked_by_subs_per_1k") or []
    if fan_rows:
        for item in fan_rows[:5]:
            lines.append(
                f"- {_display_title(item)}: {item.get('subs_per_1k_views')} subs/1k views, "
                f"{item.get('comments_per_1k_views')} comments/1k"
            )
    else:
        lines.append("- No subscriber conversion ranking yet.")
    cat_rates = fan.get("category_subscriber_rates") or memory.get("category_subscriber_rates") or {}
    if cat_rates:
        top = sorted(cat_rates.items(), key=lambda item: item[1], reverse=True)[:5]
        lines.append("- Best converting categories: " + ", ".join(f"{k} ({v})" for k, v in top))
    lines.extend(["", "## Audience Memory"])
    coverage = audience.get("coverage") or {}
    if audience:
        lines.append(
            f"- Samples: {audience.get('sample_count', 0)} videos; "
            f"retention={coverage.get('with_retention', 0)}, "
            f"subscribers={coverage.get('with_subscribers', 0)}, "
            f"comments={coverage.get('with_comments', 0)}"
        )
        lines.append(f"- Bootstrap mode: {audience.get('bootstrap_mode', True)}")
        winners = (audience.get("winners") or {}).get("series") or []
        if winners:
            lines.append("- Strongest return series: " + ", ".join(str(item.get("value")) for item in winners[:5]))
    else:
        lines.append("- No audience memory yet.")
    lines.extend(["", "## Early Distribution"])
    top_velocity = early.get("top_velocity") or []
    if top_velocity:
        for item in top_velocity[:5]:
            probs = item.get("breakout_probability") or {}
            lines.append(
                f"- {_display_title(item)}: velocity {item.get('early_velocity_score')}/100, "
                f"{item.get('views_per_hour')} views/hour, P>5k={probs.get('pass_5000', 0)}"
            )
    else:
        lines.append("- No early velocity history yet.")
    risks = warning.get("risk_of_dying_early") or []
    accelerators = warning.get("potential_accelerators") or []
    watchlist = warning.get("watchlist_low_confidence") or []
    lines.append(f"- Early risks: {len(risks)}; accelerators: {len(accelerators)}; low-confidence watchlist: {len(watchlist)}")
    if patterns:
        lines.append(
            f"- Winner-pattern confidence: {patterns.get('confidence_score', 0)} "
            f"({patterns.get('recommendation_strength', 'observe')})"
        )
        cats = patterns.get("winning_categories") or {}
        series = patterns.get("winning_series") or {}
        if cats:
            lines.append("- Velocity-winning categories: " + ", ".join(list(cats)[:5]))
        if series:
            lines.append("- Velocity-winning series: " + ", ".join(list(series)[:5]))
    lines.extend(["", "## Remake Backlog"])
    for item in (remakes.get("remakes") or [])[:8]:
        lines.append(f"- {_display_title(item, 'source_title')} -> {item.get('action')}")
    if not remakes.get("remakes"):
        lines.append("- No remake candidates yet.")
    lines.extend(["", "## Next Actions"])
    actions = (ops.get("executive_report") or {}).get("next_actions") or brief.get("next_actions") or []
    for action in actions[:8]:
        lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    out = REPORT_DIR / f"weekly-{today}.md"
    out.write_text(build_markdown(ROOT), encoding="utf-8")
    print(f"weekly report: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
