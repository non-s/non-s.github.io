#!/usr/bin/env python3
# ruff: noqa: E402
"""
scripts/build_dashboard.py — Generate a static analytics dashboard.

Reads every CSV in `_data/analytics/*.csv` plus `latest.json`,
`experiments.json`, `cohort_timing.json`, and writes a single
self-contained HTML file at `_site/index.html` that GitHub Pages
serves at `https://<owner>.github.io/<repo>/`.

The dashboard shows:
  * Views + average view % over time (sparkline)
  * Top-performing Shorts (titles + view counts)
  * A/B winners with lift figures
  * Audience cohort timing
  * Per-category retention

Zero external JS deps. Everything inline so a private CDN failure
doesn't blank the page.
"""

from __future__ import annotations

import csv
import html
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analytics_schema import read_jsonl
from utils.automation_health import build_health
from utils.content_agency import agency_snapshot, rank_for_agency
from utils.editorial import rank_candidates
from utils.editorial_guard import editorial_issues
from utils.growth_strategy import load_strategy
from utils.humanity_engine import polish_story
from utils.mission_control import build_mission_control
from utils.studio_reach_schema import summarize_reach

ANALYTICS_DIR = Path("_data/analytics")
SITE_DIR = Path("_site")
OUT = SITE_DIR / "index.html"
SECURITY_TXT = Path(".well-known/security.txt")
QUEUE_FILE = Path("_data/stories_queue.json")
PUBLISH_READY_RESERVE_TARGET = 6


def _read_csvs() -> list[dict]:
    """Read every YYYY-MM-DD.csv into a flat list of rows, with
    `pulled_at` populated from the filename when missing."""
    rows: list[dict] = []
    if not ANALYTICS_DIR.exists():
        return rows
    for csv_path in sorted(ANALYTICS_DIR.glob("20*.csv")):
        try:
            with csv_path.open(encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for r in reader:
                    if not r.get("pulled_at"):
                        r["pulled_at"] = csv_path.stem
                    rows.append(r)
        except Exception:
            continue
    return rows


def _read_partition_rows() -> list[dict]:
    """Read compacted JSONL partitions as a dashboard fallback."""
    rows: list[dict] = []
    partitions = ANALYTICS_DIR / "partitions"
    for path in sorted(partitions.glob("video_metrics/*.jsonl")) if partitions.exists() else []:
        for row in read_jsonl(path):
            metrics = row.get("metrics") or {}
            rows.append(
                {
                    "pulled_at": row.get("pulled_at", ""),
                    "an_views": metrics.get("views", 0),
                    "avg_view_pct": metrics.get("average_view_percentage", 0),
                }
            )
    return rows


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _latest_uploaded_intent(rows: list[dict]) -> dict:
    uploaded = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("status") or "").strip().lower() == "uploaded"
        and str(row.get("slot") or "").strip()
        and str(row.get("video_id") or "").strip()
    ]
    if not uploaded:
        return {}
    return max(uploaded, key=lambda row: str(row.get("created_at") or row.get("slot") or ""))


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _title_keyword_tokens(title: str) -> set[str]:
    stop = {"about", "after", "their", "there", "these", "thing", "things", "watch", "where", "which", "while", "with"}
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", str(title or "").lower()):
        if len(token) >= 5 and token not in stop:
            tokens.add(token)
    return tokens


def _display_title(item: dict, key: str = "title") -> str:
    title = str(item.get(key) or item.get("seo_title") or "").strip()
    issues = editorial_issues({"title": title, "seo_title": title}, include_script=False) if title else []
    if not issues:
        return title or str(item.get("video_id") or item.get("source_video_id") or item.get("id") or "")
    video_id = str(item.get("video_id") or item.get("source_video_id") or item.get("id") or "unknown-video")
    return f"{video_id} (title needs repair: {', '.join(issues[:3])})"


def _queue_commands(
    *, pending: int, approved: int, states: Counter[str], categories: dict[str, Counter[str]]
) -> list[str]:
    """Translate queue health into concrete operator commands."""
    commands: list[str] = []
    if pending and approved == 0:
        commands.append("No approved story is ready: run the fetch + polish pipeline before publishing.")
    elif pending and approved < 3:
        commands.append("Approved queue is thin: refresh discovery before the next publish window.")
    cooldown = states.get("cooldown_subject", 0)
    if pending and cooldown / max(1, pending) >= 0.45:
        commands.append("Too many stories are in cooldown: expand fresh subjects instead of reusing recent angles.")
    weak_categories = [
        cat
        for cat, by_state in sorted(categories.items())
        if by_state.get("publish_now", 0) + by_state.get("polished", 0) == 0
    ]
    if weak_categories:
        commands.append("Search more approved candidates for: " + ", ".join(weak_categories[:5]) + ".")
    strong_categories = [
        cat
        for cat, by_state in sorted(
            categories.items(),
            key=lambda kv: kv[1].get("publish_now", 0) + kv[1].get("polished", 0),
            reverse=True,
        )
        if by_state.get("publish_now", 0) + by_state.get("polished", 0) >= 2
    ]
    if strong_categories:
        commands.append("Use the next publish slot from: " + ", ".join(strong_categories[:3]) + ".")
    return commands[:5]


def _queue_studio_snapshot(path: Path = QUEUE_FILE) -> dict:
    data = _safe_json(path)
    stories = [item for item in (data.get("stories") or []) if isinstance(item, dict) and not item.get("consumed")]
    if not stories:
        return {"pending": 0, "approved": 0, "labels": {}, "top": []}
    polished_stories = [polish_story(item) for item in stories]
    ranked = rank_candidates(polished_stories)
    strategy = load_strategy()
    agency_ranked = rank_for_agency(ranked, strategy)
    agency = agency_snapshot(ranked, strategy)
    labels: Counter[str] = Counter()
    states: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    categories: dict[str, Counter[str]] = {}
    approved = 0
    rescued = 0
    top: list[dict] = []
    for item in agency_ranked:
        editorial = item.get("editorial") or {}
        humanity = editorial.get("humanity") or {}
        studio_polish = item.get("studio_polish") or {}
        if studio_polish.get("applied"):
            rescued += 1
        label = str(humanity.get("label") or "unknown")
        state = str(editorial.get("state") or item.get("studio_state") or "unknown")
        labels[label] += 1
        states[state] += 1
        category = str(item.get("category") or "unknown")
        categories.setdefault(category, Counter())[state] += 1
        reasons.update(str(reason) for reason in (editorial.get("reasons") or []))
        if editorial.get("approved"):
            approved += 1
        if len(top) < 8 and editorial.get("approved"):
            top.append(
                {
                    "title": item.get("seo_title") or item.get("title") or "",
                    "category": item.get("category") or "",
                    "editorial_score": editorial.get("score", 0),
                    "humanity_score": humanity.get("score", 0),
                    "humanity_label": label,
                    "agency_score": (item.get("agency") or {}).get("score", 0),
                    "agency_decision": (item.get("agency") or {}).get("decision", ""),
                }
            )
    return {
        "pending": len(stories),
        "approved": approved,
        "rescued": rescued,
        "labels": dict(sorted(labels.items())),
        "states": dict(sorted(states.items())),
        "categories": {key: dict(sorted(value.items())) for key, value in sorted(categories.items())},
        "commands": _queue_commands(
            pending=len(stories),
            approved=approved,
            states=states,
            categories=categories,
        ),
        "agency": agency,
        "reasons": dict(reasons.most_common(8)),
        "top": top,
    }


def _series_by_day(rows: list[dict]) -> tuple[list[str], list[int], list[float]]:
    """Aggregate per snapshot date — total views + mean avg_view_pct."""
    by_day: dict[str, list[dict]] = {}
    for r in rows:
        day = (r.get("pulled_at") or "")[:10]
        if not day:
            continue
        by_day.setdefault(day, []).append(r)
    days = sorted(by_day)
    views, view_pct = [], []
    for d in days:
        sample = by_day[d]
        try:
            views.append(sum(int(r.get("an_views", 0) or 0) for r in sample))
        except Exception:
            views.append(0)
        try:
            avgs = [float(r.get("avg_view_pct", 0) or 0) for r in sample]
            view_pct.append(round(sum(avgs) / len(avgs), 1) if avgs else 0.0)
        except Exception:
            view_pct.append(0.0)
    return days, views, view_pct


def _sparkline_svg(values: list[float], width: int = 600, height: int = 80, stroke: str = "#0ea5e9") -> str:
    """Minimal inline SVG sparkline. Zero JS, no external assets."""
    if not values:
        return ""
    vmin, vmax = min(values), max(values)
    rng = max(0.001, vmax - vmin)
    step = width / max(1, len(values) - 1)
    points = " ".join(
        f"{i * step:.1f},{height - (v - vmin) / rng * (height - 10) - 5:.1f}" for i, v in enumerate(values)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
        f'<polyline fill="none" stroke="{stroke}" stroke-width="2" points="{points}" />'
        f"</svg>"
    )


CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
       margin: 0; padding: 24px; max-width: 1100px; margin-inline: auto;
       background: #0b0d12; color: #e6e9ef; line-height: 1.5; }
h1, h2, h3 { color: #fff; margin-top: 1.6em; }
h1 { margin-top: 0; }
small { color: #9aa3b2; }
.card { background: #131722; border: 1px solid #1f2433; border-radius: 12px;
        padding: 20px; margin: 16px 0; }
.metric { font-size: 2.4em; font-weight: 600; }
.row { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid #1f2433; padding: 8px 6px; text-align: left;
         vertical-align: top; }
th { color: #9aa3b2; font-weight: 500; font-size: 0.85em; }
a { color: #0ea5e9; text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: #1f2433; padding: 1px 6px; border-radius: 4px; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 99px;
         font-size: 0.78em; background: #1f2433; color: #c0c7d6; }
.green { color: #4ade80; }
.red   { color: #f87171; }
"""


def render_html() -> str:
    rows = _read_csvs() or _read_partition_rows()
    latest = _safe_json(ANALYTICS_DIR / "latest.json")
    health = _safe_json(Path("_data/automation_health.json")) or build_health(Path("."))
    comments = _safe_json(ANALYTICS_DIR / "comments.json")
    experiments = _safe_json(ANALYTICS_DIR / "experiments.json")
    cohort = _safe_json(ANALYTICS_DIR / "cohort_timing.json")
    ops_guardian = _safe_json(Path("_data/ops_guardian.json"))
    remake_backlog = _safe_json(Path("_data/remake_backlog.json"))
    trend_radar = _safe_json(Path("_data/trend_radar.json"))
    agency_plan = _safe_json(Path("_data/agency_plan.json"))
    visual_report = _safe_json(Path("_data/visual_quality_report.json"))
    visual_backfill = _safe_json(Path("_data/visual_qa_backfill.json"))
    narrator_report = _safe_json(Path("_data/narrator_report.json"))
    fact_ledger = _safe_json(Path("_data/fact_ledger.json"))
    legacy_backfill = _safe_json(Path("_data/analytics/legacy_backfill.json"))
    remake_factory = _safe_json(Path("_data/remake_factory.json"))
    rewrite_queue = _safe_json(Path("_data/retention_rewrite_queue.json"))
    retention_rewriter = _safe_json(Path("_data/retention_rewriter.json"))
    category_recovery = _safe_json(Path("_data/category_recovery.json"))
    category_recovery_rewriter = _safe_json(Path("_data/category_recovery_rewriter.json"))
    daily_brief = _safe_json(Path("_data/daily_brief.json"))
    control_plane = _safe_json(Path("_data/control_plane_report.json"))
    agency_gate = _safe_json(Path("_data/agency_gate.json"))
    youtube_intelligence = _safe_json(Path("_data/youtube_intelligence.json"))
    ai_provider_report = _safe_json(Path("_data/ai_provider_report.json"))
    packaging_report = _safe_json(Path("_data/packaging_report.json"))
    youtube_brain_report = _safe_json(Path("_data/youtube_brain_report.json"))
    autonomous_director = _safe_json(Path("_data/autonomous_director.json"))
    autonomous_growth_plan = _safe_json(Path("_data/autonomous_growth_plan.json"))
    channel_success = _safe_json(Path("_data/channel_success.json"))
    scale_blueprint = _safe_json(Path("_data/scale_blueprint.json"))
    success_rewriter = _safe_json(Path("_data/success_rewriter.json"))
    winner_sequels = _safe_json(Path("_data/winner_sequel_factory.json"))
    queue_audit = _safe_json(Path("_data/queue_audit.json"))
    reject_report = _safe_json(Path("_data/reject_report.json"))
    next_shorts = _safe_json(Path("_data/next_shorts.json"))
    weekly_growth = _safe_json(Path("_data/analytics/weekly_summary.json"))
    experiment_recommendations = _safe_json(Path("_data/experiments_recommendations.json"))
    topic_candidates = _safe_json(Path("_data/trends/topic_candidates.json"))
    session_ops = _safe_json(Path("_data/post_upload_session_ops.json"))
    related_video_recommendations = _safe_json(Path("_data/related_video_recommendations.json"))
    comment_reply_short_candidates = _safe_json(Path("_data/comment_reply_short_candidates.json"))
    dry_run_publish = _safe_json(Path("_data/dry_run_publish.json"))
    sequence_plan = _safe_json(Path("_data/sequence_plan.json"))
    post24_review = _safe_json(Path("_data/post24_review.json"))
    publish_schedule = _safe_json(Path("_data/publish_schedule.json"))
    studio_reach_latest = _safe_json(Path("_data/analytics/studio_reach_latest.json"))
    studio_reach_summary = studio_reach_latest.get("summary") or summarize_reach(
        read_jsonl(Path("_data/analytics/studio_reach_daily.jsonl"))
    )
    freshness_report = _safe_json(Path("_data/trends/freshness_report.json"))
    opening_audit_report = _safe_json(Path("_data/opening_audit_report.json"))
    session_graph = _safe_json(Path("_data/session_graph.json"))
    next_session_actions = _safe_json(Path("_data/next_session_actions.json"))
    sequel_candidates = _safe_json(Path("_data/sequel_candidates.json"))
    quota_latest = _safe_json(Path("_data/analytics/api_quota_latest.json"))
    compaction_report = _safe_json(Path("_data/analytics/compaction_report.json"))
    reporting_bootstrap = _safe_json(Path("_data/analytics/reporting_bootstrap.json"))
    reporting_pull = _safe_json(Path("_data/analytics/reporting_pull.json"))
    comment_to_short = _safe_json(Path("_data/comment_to_short_candidates.json"))
    seo_metadata_lint = _safe_json(Path("_data/seo_metadata_lint.json"))
    fact_guard_report = _safe_json(Path("_data/fact_guard_report.json"))
    experiment_registry = _safe_json(Path("_data/experiment_registry.json"))
    underpowered_tests = _safe_json(Path("_data/underpowered_tests.json"))
    music_bed_report = _safe_json(Path("_data/music_bed_report.json"))
    retention_reconciliation = _safe_json(Path("_data/analytics/retention_reconciliation.json"))
    crosspost_pack = _safe_json(Path("_data/crosspost_pack.json"))
    render_bench = _safe_json(Path("_data/render_bench.json"))
    security_manifest = _safe_json(Path("_data/security_manifest.json"))
    upload_intents = read_jsonl(Path("_data/upload_intents.jsonl"))
    originality_rows = read_jsonl(Path("_data/originality_pack.jsonl"))
    provenance_rows = read_jsonl(Path("_data/source_provenance.jsonl"))
    days, views_series, view_pct_series = _series_by_day(rows)

    total_views_14d = latest.get("total_views_14d", 0)
    total_views = latest.get("total_views", total_views_14d)
    avg_view_pct = latest.get("avg_view_pct", latest.get("avg_view_percentage", 0))
    avg_engagement = latest.get("avg_engagement_score", 0)
    avg_humanity = latest.get("avg_humanity_score", 0)
    humanity_counts = latest.get("humanity_label_counts") or {}
    pulled_at = latest.get("pulled_at", "—")
    underperformers = latest.get("below_62_pct") or latest.get("below_60_pct") or []
    cat_perf = latest.get("category_avg_view_pct") or {}
    cat_engagement = latest.get("category_avg_engagement") or {}
    cat_growth = latest.get("category_avg_growth_score") or {}
    format_growth = latest.get("format_avg_growth_score") or {}
    series_engagement = latest.get("series_avg_engagement") or {}
    top_performers = latest.get("top_performers") or []
    recommendations = latest.get("production_recommendations") or {}
    learning_profile = latest.get("learning_profile") or recommendations.get("learning_profile") or {}
    weekly_brief = latest.get("weekly_brief") or {}
    winner_loser = latest.get("winner_loser_map") or recommendations.get("winner_loser_map") or {}
    remake_candidates = latest.get("remake_candidates") or recommendations.get("remake_candidates") or []
    good_title_keywords: set[str] = set()
    bad_title_keywords: set[str] = set()
    for item in top_performers:
        title = str(item.get("title") or "")
        if _recommendable_title(title):
            good_title_keywords.update(_title_keyword_tokens(title))
        else:
            bad_title_keywords.update(_title_keyword_tokens(title))
    stale_bad_title_keywords = bad_title_keywords - good_title_keywords
    queue_studio = _queue_studio_snapshot()
    mission_control = build_mission_control(
        latest=latest,
        comments=comments,
        queue=queue_studio,
    )

    out: list[str] = []
    out.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    out.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    out.append("<title>Wild Brief — channel dashboard</title>")
    out.append(f"<style>{CSS}</style></head><body>")

    out.append("<h1>Wild Brief — channel dashboard</h1>")
    out.append(
        f"<small>Generated {html.escape(datetime.now(timezone.utc).isoformat())} UTC · "
        f"last analytics snapshot {html.escape(str(pulled_at))}</small>"
    )

    # ── Top-line metrics ───────────────────────────────────────
    out.append("<section class='row'>")
    out.append(
        f"<div class='card'><small>Total tracked views</small>" f"<div class='metric'>{int(total_views):,}</div></div>"
    )
    out.append(
        f"<div class='card'><small>Public engagement score</small>" f"<div class='metric'>{avg_engagement}</div></div>"
    )
    out.append(f"<div class='card'><small>Avg view %</small>" f"<div class='metric'>{avg_view_pct}</div></div>")
    out.append(f"<div class='card'><small>Avg humanity score</small>" f"<div class='metric'>{avg_humanity}</div></div>")
    out.append(
        f"<div class='card'><small>Shorts under 62 % retention</small>"
        f"<div class='metric'>{len(underperformers)}</div></div>"
    )
    out.append("</section>")

    latest_upload = _latest_uploaded_intent(upload_intents)
    if health or latest_upload or next_shorts:
        queue_health = health.get("queue") or {}
        issues = health.get("issues") or []
        publish_ready = int(queue_health.get("publish_ready", 0) or 0)
        next_items = next_shorts.get("items") or []
        reserve_label = f"{publish_ready}/{PUBLISH_READY_RESERVE_TARGET}"
        latest_slot = str(latest_upload.get("slot") or "none")
        latest_video_id = str(latest_upload.get("video_id") or "")
        latest_title = str(latest_upload.get("title") or "")
        out.append("<div class='card'><h2>v1.0 closure status</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Operational state</small><div class='metric'>{html.escape(str(health.get('state', 'unknown')))}</div></div>"
        )
        out.append(f"<div><small>Last uploaded slot</small><div class='metric'>{html.escape(latest_slot)}</div></div>")
        out.append(
            f"<div><small>Publish-ready reserve</small><div class='metric'>{html.escape(reserve_label)}</div></div>"
        )
        out.append(f"<div><small>Next Shorts listed</small><div class='metric'>{len(next_items)}</div></div>")
        out.append("</section>")
        if latest_video_id:
            url = f"https://www.youtube.com/shorts/{html.escape(latest_video_id)}"
            out.append(
                f"<p><strong>Latest upload:</strong> <a href='{url}'>{html.escape(latest_video_id)}</a>"
                f" - {html.escape(latest_title[:120])}</p>"
            )
        if issues:
            out.append("<p><strong>Action required:</strong> review health issues below before changing cadence.</p>")
        elif publish_ready >= PUBLISH_READY_RESERVE_TARGET:
            out.append("<p><strong>Closure gate:</strong> no required operator action pending.</p>")
        else:
            out.append("<p><strong>Closure gate:</strong> reserve is operational but still below the v1.0 target.</p>")
        out.append("</div>")

    if health:
        queue_health = health.get("queue") or {}
        seo_health = health.get("seo") or {}
        out.append("<div class='card'><h2>Automation health</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Health score</small><div class='metric'>{int(health.get('score', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>State</small><div class='metric'>{html.escape(str(health.get('state', 'unknown')))}</div></div>"
        )
        out.append(
            f"<div><small>Pending queue</small><div class='metric'>{int(queue_health.get('pending', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>SEO avg</small><div class='metric'>{float(seo_health.get('average_score', 0) or 0):.1f}</div></div>"
        )
        out.append("</section>")
        issues = health.get("issues") or []
        if issues:
            out.append("<h3>Health issues</h3><ul>")
            for issue in issues[:8]:
                out.append(f"<li><code>{html.escape(str(issue))}</code></li>")
            out.append("</ul>")
        out.append("</div>")

    if (
        weekly_growth
        or next_shorts
        or session_ops
        or topic_candidates
        or studio_reach_summary.get("rows")
        or freshness_report
        or opening_audit_report
        or quota_latest
        or session_graph
        or comment_to_short
    ):
        out.append("<div class='card'><h2>World-class growth cockpit</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Studio Reach rows</small><div class='metric'>{int(studio_reach_summary.get('rows', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Stayed to watch</small><div class='metric'>{float(studio_reach_summary.get('stayed_to_watch_rate', 0) or 0) * 100:.1f}%</div></div>"
        )
        out.append(
            f"<div><small>Fresh queue coverage</small><div class='metric'>{float(freshness_report.get('coverage', 0) or 0) * 100:.0f}%</div></div>"
        )
        out.append(
            f"<div><small>Opening audit pass</small><div class='metric'>{float(opening_audit_report.get('pass_rate', 0) or 0) * 100:.0f}%</div></div>"
        )
        out.append(
            f"<div><small>Session coverage</small><div class='metric'>{float(session_graph.get('coverage', 0) or 0) * 100:.0f}%</div></div>"
        )
        session_targets = {
            str(edge.get("target_video_id") or "")
            for edge in (session_graph.get("edges") or [])
            if edge.get("target_video_id")
        }
        out.append(f"<div><small>Session targets</small><div class='metric'>{len(session_targets)}</div></div>")
        quota_guard = quota_latest.get("guard") or {}
        out.append(
            f"<div><small>Quota guard</small><div class='metric'>{html.escape(str(quota_guard.get('mode') or 'ok'))}</div></div>"
        )
        out.append("</section>")
        if weekly_growth:
            out.append("<section class='row'>")
            out.append(
                f"<div><small>Normalized rows</small><div class='metric'>{int(weekly_growth.get('rows', weekly_growth.get('video_metric_rows', 0)) or 0)}</div></div>"
            )
            winners = weekly_growth.get("winning_categories") or []
            top_category = winners[0].get("value") if winners else ""
            out.append(
                f"<div><small>Top category</small><div class='metric'>{html.escape(str(top_category or 'none'))}</div></div>"
            )
            low = weekly_growth.get("losing_openings") or []
            out.append(f"<div><small>Swipe/retention alerts</small><div class='metric'>{len(low)}</div></div>")
            out.append("</section>")
            experiments_list = weekly_growth.get("next_three_experiments") or []
            if experiments_list:
                out.append("<h3>Next experiments</h3><ul>")
                for item in experiments_list[:3]:
                    out.append(f"<li>{html.escape(str(item))}</li>")
                out.append("</ul>")
            if low:
                out.append("<h3>Swipe risk alerts</h3><table><tr><th>Video</th><th>Title</th><th>Avg view %</th></tr>")
                for item in low[:6]:
                    out.append(
                        f"<tr><td><code>{html.escape(str(item.get('video_id', '')))}</code></td>"
                        f"<td>{html.escape(_display_title(item)[:90])}</td>"
                        f"<td>{html.escape(str(item.get('average_view_percentage', 0)))}</td></tr>"
                    )
                out.append("</table>")
        recs = next_shorts.get("recommendations") or weekly_growth.get("next_ten_package_recommendations") or []
        if recs:
            out.append(
                "<h3>What to publish next</h3><table><tr><th>Category</th><th>Reason</th><th>Package hint</th></tr>"
            )
            for item in recs[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{html.escape(str(item.get('reason', ''))[:120])}</td>"
                    f"<td>{html.escape(str(item.get('package_hint', ''))[:140])}</td></tr>"
                )
            out.append("</table>")
        topics = topic_candidates.get("candidates") or []
        if topics:
            out.append("<h3>Free signal topics</h3><table><tr><th>Topic</th><th>Score</th><th>Sources</th></tr>")
            for item in topics[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('topic', ''))[:90])}</td>"
                    f"<td>{float(item.get('score', 0) or 0):.1f}</td>"
                    f"<td>{html.escape(', '.join(map(str, item.get('sources') or []))[:140])}</td></tr>"
                )
            out.append("</table>")
        worst_reach = studio_reach_summary.get("worst_swipe_videos") or []
        if worst_reach:
            out.append(
                "<h3>Shorts Reach: worst swipe risk</h3><table><tr><th>Video</th><th>Title</th><th>STW</th><th>Swipe</th></tr>"
            )
            for item in worst_reach[:6]:
                metrics = item.get("metrics") or {}
                out.append(
                    f"<tr><td><code>{html.escape(str(item.get('video_id', '')))}</code></td>"
                    f"<td>{html.escape(str(item.get('title', ''))[:90])}</td>"
                    f"<td>{float(metrics.get('stayed_to_watch_rate', 0) or 0) * 100:.1f}%</td>"
                    f"<td>{float(metrics.get('swipe_away_rate', 0) or 0) * 100:.1f}%</td></tr>"
                )
            out.append("</table>")
        stale = freshness_report.get("stale") or freshness_report.get("stale_items") or []
        if stale:
            out.append("<h3>Freshness queue watchlist</h3><table><tr><th>Story</th><th>Age</th><th>Freshness</th></tr>")
            for item in stale[:6]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title') or item.get('id') or '')[:100])}</td>"
                    f"<td>{float(item.get('queue_age_days', 0) or 0):.1f}d</td>"
                    f"<td>{float(item.get('freshness_score', 0) or 0):.1f}</td></tr>"
                )
            out.append("</table>")
        opening_items = opening_audit_report.get("weak_openings") or opening_audit_report.get("items") or []
        if opening_items:
            out.append("<h3>Opening audit watchlist</h3><table><tr><th>Video</th><th>Score</th><th>Reasons</th></tr>")
            for item in opening_items[:6]:
                audit = item.get("opening_audit") or item
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title') or item.get('video_id') or '')[:100])}</td>"
                    f"<td>{float(audit.get('score', 0) or 0):.1f}</td>"
                    f"<td>{html.escape(', '.join(map(str, audit.get('reasons') or []))[:140])}</td></tr>"
                )
            out.append("</table>")
        related = related_video_recommendations.get("items") or session_ops.get("related_video_recommendations") or []
        if related:
            out.append(
                "<h3>Related video suggestions</h3><table><tr><th>New Short</th><th>Set related to</th><th>Why</th></tr>"
            )
            for item in related[:8]:
                rec = item.get("recommendation") or {}
                out.append(
                    f"<tr><td><code>{html.escape(str(item.get('source_video_id', '')))}</code></td>"
                    f"<td>{html.escape(str(rec.get('title', ''))[:90])}</td>"
                    f"<td>{html.escape(str(rec.get('reason', ''))[:120])}</td></tr>"
                )
            out.append("</table>")
        comment_items = (
            comment_to_short.get("candidates")
            or comment_to_short.get("items")
            or comment_reply_short_candidates.get("items")
            or session_ops.get("comment_reply_short_candidates")
            or []
        )
        if comment_items:
            out.append("<h3>Reply with a Short</h3><ul>")
            for item in comment_items[:6]:
                out.append(
                    f"<li>{html.escape(str(item.get('short_prompt') or item.get('hook') or item.get('comment') or item.get('source_comment') or '')[:180])}</li>"
                )
            out.append("</ul>")
        session_actions = next_session_actions.get("items") or session_graph.get("next_session_actions") or []
        if session_actions:
            out.append("<h3>Next session actions</h3><table><tr><th>Action</th><th>Video</th><th>Why</th></tr>")
            for item in session_actions[:6]:
                out.append(
                    f"<tr><td><span class='badge'>{html.escape(str(item.get('action', 'handoff')))}</span></td>"
                    f"<td>{html.escape(str(item.get('video_id') or item.get('source_video_id') or '')[:40])}</td>"
                    f"<td>{html.escape(str(item.get('reason') or item.get('title') or '')[:140])}</td></tr>"
                )
            out.append("</table>")
        sequels = sequel_candidates.get("items") or []
        if sequels:
            out.append("<h3>Sequel candidates</h3><ul>")
            for item in sequels[:5]:
                out.append(f"<li>{html.escape(str(item.get('prompt') or item.get('title') or '')[:180])}</li>")
            out.append("</ul>")
        if quota_latest:
            estimate = quota_latest.get("estimate") or {}
            guard = quota_latest.get("guard") or {}
            out.append(
                "<p><strong>Quota:</strong> "
                f"{float(estimate.get('units', estimate.get('cost', 0)) or 0):.0f} projected units; "
                f"guard <span class='badge'>{html.escape(str(guard.get('status') or guard.get('mode') or 'ok'))}</span>.</p>"
            )
        if compaction_report:
            datasets = compaction_report.get("datasets") or {}
            partitions_count = sum(len((item or {}).get("partitions") or []) for item in datasets.values())
            out.append(
                f"<p><strong>Warehouse compaction:</strong> {partitions_count} partition file(s) across {len(datasets)} dataset(s).</p>"
            )
        if reporting_bootstrap or reporting_pull:
            out.append(
                "<p><strong>Reporting backfill:</strong> "
                f"{html.escape(str(reporting_bootstrap.get('status', 'not configured')))}; "
                f"{int(reporting_pull.get('rows', 0) or 0)} imported row(s).</p>"
            )
        if seo_metadata_lint:
            out.append(
                f"<p><strong>SEO metadata lint:</strong> {int(seo_metadata_lint.get('checked', 0) or 0)} checked, "
                f"{int(seo_metadata_lint.get('errors', 0) or 0)} error(s).</p>"
            )
        if experiment_recommendations:
            out.append(
                "<p><strong>Experiment recommendations updated:</strong> "
                + html.escape(str(experiment_recommendations.get("generated_at", "")))
                + "</p>"
            )
        out.append("</div>")

    # ── Sparklines ─────────────────────────────────────────────
    if days:
        out.append("<div class='card'>")
        out.append(f"<h3>Daily views <small>({days[0]} → {days[-1]})</small></h3>")
        out.append(_sparkline_svg(views_series, stroke="#0ea5e9"))
        out.append("<h3>Avg view % per day</h3>")
        out.append(_sparkline_svg(view_pct_series, stroke="#f59e0b"))
        out.append("</div>")

    # ── Top performers ────────────────────────────────────────
    if recommendations:
        hot = recommendations.get("hot_categories") or []
        slow = recommendations.get("slow_categories") or []
        actions = recommendations.get("next_actions") or []
        titles = recommendations.get("double_down_titles") or []
        formats = recommendations.get("hot_formats") or []
        out.append("<div class='card'><h2>Production recommendations</h2>")
        if hot:
            out.append("<p><strong>Prioritize:</strong> " + html.escape(", ".join(map(str, hot))) + "</p>")
        if slow:
            out.append("<p><strong>Watch carefully:</strong> " + html.escape(", ".join(map(str, slow))) + "</p>")
        if formats:
            out.append("<p><strong>Winning formats:</strong> " + html.escape(", ".join(map(str, formats))) + "</p>")
        if recommendations.get("exploit_mode"):
            out.append("<p><span class='badge green'>Exploit mode active</span></p>")
        if titles:
            out.append("<h3>Double down on story shapes</h3><ul>")
            for title in titles[:5]:
                out.append(f"<li>{html.escape(str(title)[:120])}</li>")
            out.append("</ul>")
        if actions:
            out.append("<h3>Next actions</h3><ul>")
            for action in actions[:5]:
                out.append(f"<li>{html.escape(str(action))}</li>")
            out.append("</ul>")
        out.append("</div>")

    if weekly_brief or winner_loser or remake_candidates:
        out.append("<div class='card'><h2>Growth studio</h2>")
        if weekly_brief:
            out.append(f"<p><strong>Weekly brief:</strong> {html.escape(str(weekly_brief.get('headline', '')))}</p>")
            mix = weekly_brief.get("production_mix") or {}
            if mix:
                out.append(
                    "<p><strong>Production mix:</strong> "
                    f"{int(mix.get('exploit', 0) or 0)}% exploit, "
                    f"{int(mix.get('explore', 0) or 0)}% explore, "
                    f"{int(mix.get('moonshot', 0) or 0)}% moonshot</p>"
                )
            for label, key in (
                ("Best category", "best_category"),
                ("Best format", "best_format"),
                ("Best narrator", "best_narrator"),
            ):
                value = weekly_brief.get(key)
                if value:
                    out.append(f"<p><strong>{label}:</strong> {html.escape(str(value))}</p>")
            actions = weekly_brief.get("next_actions") or []
            if actions:
                out.append("<h3>Studio actions</h3><ul>")
                for action in actions[:5]:
                    out.append(f"<li>{html.escape(str(action))}</li>")
                out.append("</ul>")
        winners = winner_loser.get("winners") or {}
        if winners:
            out.append(
                "<h3>Winner map</h3><table><tr><th>Axis</th><th>Winner</th><th>Growth</th><th>Retention</th><th>n</th></tr>"
            )
            for axis, item in winners.items():
                out.append(
                    f"<tr><td>{html.escape(str(axis))}</td>"
                    f"<td><span class='badge green'>{html.escape(str(item.get('value', '')))}</span></td>"
                    f"<td>{float(item.get('mean_growth', 0) or 0):.1f}</td>"
                    f"<td>{float(item.get('mean_retention', 0) or 0):.1f}</td>"
                    f"<td>{int(item.get('n', 0) or 0)}</td></tr>"
                )
            out.append("</table>")
        if remake_candidates:
            out.append(
                "<h3>Remake candidates</h3><table><tr><th>Title</th><th>Retention</th><th>Views</th><th>Action</th></tr>"
            )
            for item in remake_candidates[:6]:
                out.append(
                    f"<tr><td>{html.escape(_display_title(item)[:90])}</td>"
                    f"<td>{float(item.get('retention', 0) or 0):.1f}%</td>"
                    f"<td>{int(item.get('views', 0) or 0):,}</td>"
                    f"<td>{html.escape(str(item.get('action', '')))}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if ops_guardian:
        risk = ops_guardian.get("risk") or {}
        scheduler = ops_guardian.get("scheduler") or {}
        visual = ops_guardian.get("visual_quality") or {}
        series_plan = ops_guardian.get("series_plan") or {}
        inventory = ops_guardian.get("inventory_forecast") or {}
        executive = ops_guardian.get("executive_report") or {}
        out.append("<div class='card'><h2>Operations guardian</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Risk level</small><div class='metric'>{html.escape(str(risk.get('level', 'unknown')))}</div></div>"
        )
        out.append(f"<div><small>Risk score</small><div class='metric'>{int(risk.get('score', 0) or 0)}</div></div>")
        out.append(
            f"<div><small>Avg retention</small><div class='metric'>{float(risk.get('avg_retention', 0) or 0):.1f}</div></div>"
        )
        out.append(
            f"<div><small>Weak ratio</small><div class='metric'>{float(risk.get('weak_retention_ratio', 0) or 0):.2f}</div></div>"
        )
        out.append("</section>")
        if inventory:
            out.append(
                f"<p><strong>Inventory forecast:</strong> {float(inventory.get('days_remaining', 0) or 0):.1f} days "
                f"at {int(inventory.get('daily_posts', 0) or 0)} posts/day "
                f"(<span class='badge'>{html.escape(str(inventory.get('state', 'unknown')))}</span>)</p>"
            )
        if executive.get("summary"):
            out.append(f"<p><strong>Executive read:</strong> {html.escape(str(executive.get('summary')))}</p>")
        paused = ops_guardian.get("paused_topics") or []
        if paused:
            out.append(
                "<h3>Paused topics</h3><table><tr><th>Category</th><th>Reason</th><th>Retention</th><th>Growth</th></tr>"
            )
            for item in paused[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td><code>{html.escape(str(item.get('reason', '')))}</code></td>"
                    f"<td>{float(item.get('retention', 0) or 0):.1f}</td>"
                    f"<td>{float(item.get('growth_score', 0) or 0):.1f}</td></tr>"
                )
            out.append("</table>")
        hours = scheduler.get("recommended_utc_hours") or []
        if hours:
            out.append(
                "<h3>Recommended publish windows</h3><table><tr><th>UTC hour</th><th>Country</th><th>Reason</th></tr>"
            )
            for item in hours[:5]:
                out.append(
                    f"<tr><td>{int(item.get('utc_hour', 0) or 0):02d}:00 UTC</td>"
                    f"<td>{html.escape(str(item.get('country', 'global')))}</td>"
                    f"<td>{html.escape(str(item.get('reason', '')))}</td></tr>"
                )
            out.append("</table>")
        out.append("<h3>Visual quality</h3>")
        out.append(
            f"<p>Checked: {int(visual.get('checked', 0) or 0)} · "
            f"Rejected: {int(visual.get('rejected', 0) or 0)} · "
            f"Low quality: {int(visual.get('low_quality', 0) or 0)} · "
            f"Local checked: {int(visual.get('local_checked', 0) or 0)} · "
            f"Local low quality: {int(visual.get('local_low_quality', 0) or 0)}</p>"
        )
        top_series = series_plan.get("series_to_scale") or []
        if top_series:
            out.append("<p><strong>Series to scale:</strong> " + html.escape(", ".join(map(str, top_series))) + "</p>")
        actions = executive.get("next_actions") or []
        if actions:
            out.append("<h3>Guardian actions</h3><ul>")
            for action in actions[:5]:
                out.append(f"<li>{html.escape(str(action))}</li>")
            out.append("</ul>")
        out.append("</div>")

    if trend_radar:
        summary = trend_radar.get("summary") or {}
        topics = trend_radar.get("topics") or []
        out.append("<div class='card'><h2>Trend radar</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Items scanned</small><div class='metric'>{int(summary.get('items_scanned', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Animal topics</small><div class='metric'>{int(summary.get('animal_topics', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Top animal</small><div class='metric'>{html.escape(str(summary.get('top_animal', '') or 'none'))}</div></div>"
        )
        out.append(
            f"<div><small>Top category</small><div class='metric'>{html.escape(str(summary.get('top_category', '') or 'none'))}</div></div>"
        )
        out.append("</section>")
        if topics:
            out.append(
                "<table><tr><th>Animal</th><th>Category</th><th>Score</th><th>Opportunity</th><th>Posture</th><th>Why now</th></tr>"
            )
            for item in topics[:8]:
                titles = item.get("top_titles") or []
                safety = item.get("trend_safety") or {}
                out.append(
                    f"<tr><td>{html.escape(str(item.get('animal', '')))}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{float(item.get('trend_score', 0) or 0):.1f}</td>"
                    f"<td>{float(safety.get('opportunity_score', 0) or 0):.1f}</td>"
                    f"<td><span class='badge'>{html.escape(str(safety.get('posture', 'unknown')))}</span></td>"
                    f"<td>{html.escape(str(titles[0] if titles else '')[:120])}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if remake_backlog:
        remakes = remake_backlog.get("remakes") or []
        out.append("<div class='card'><h2>Remake engine</h2>")
        out.append(
            f"<p><strong>Backlog:</strong> {int(remake_backlog.get('count', len(remakes)) or 0)} candidate(s)</p>"
        )
        if remakes:
            out.append("<table><tr><th>Source title</th><th>Retention</th><th>Views</th><th>Action</th></tr>")
            for item in remakes[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('source_title', ''))[:100])}</td>"
                    f"<td>{float(item.get('retention', 0) or 0):.1f}%</td>"
                    f"<td>{int(item.get('views', 0) or 0):,}</td>"
                    f"<td>{html.escape(str(item.get('action', '')))}</td></tr>"
                )
            out.append("</table>")
        reports = sorted(Path("_data/reports").glob("weekly-*.md"))
        if reports:
            out.append(f"<p><strong>Latest weekly report:</strong> <code>{html.escape(str(reports[-1]))}</code></p>")
        out.append("</div>")

    if mission_control:
        out.append("<div class='card'><h2>Mission control</h2>")
        out.append(
            f"<p><strong>Status:</strong> <span class='badge'>{html.escape(str(mission_control.get('status', 'steady')))}</span></p>"
        )
        priority_topics = mission_control.get("priority_topics") or []
        if priority_topics:
            out.append(
                "<p><strong>Priority topics:</strong> "
                + html.escape(", ".join(map(str, priority_topics[:12])))
                + "</p>"
            )
        tasks = mission_control.get("next_tasks") or []
        if tasks:
            out.append("<h3>Next moves</h3><table><tr><th>Priority</th><th>Task</th><th>Why</th></tr>")
            for task in tasks[:8]:
                out.append(
                    f"<tr><td><span class='badge'>{html.escape(str(task.get('priority', 'normal')))}</span></td>"
                    f"<td>{html.escape(str(task.get('task', '')))}</td>"
                    f"<td>{html.escape(str(task.get('why', '')))}</td></tr>"
                )
            out.append("</table>")
        review = mission_control.get("review_queue") or []
        if review:
            out.append("<h3>Human review queue</h3><table><tr><th>Video</th><th>Title</th><th>Reason</th></tr>")
            for item in review[:8]:
                out.append(
                    f"<tr><td><code>{html.escape(str(item.get('video_id', '')))}</code></td>"
                    f"<td>{html.escape(str(item.get('title', ''))[:100])}</td>"
                    f"<td>{html.escape(str(item.get('reason', '')))}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    agency = queue_studio.get("agency") or {}
    if agency:
        out.append("<div class='card'><h2>Agency brain</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Average agency score</small><div class='metric'>{float(agency.get('average_score', 0) or 0):.1f}</div></div>"
        )
        decisions = agency.get("decisions") or {}
        for label in ("publish_now", "strong_candidate", "needs_polish", "hold"):
            out.append(
                f"<div><small>{html.escape(label.replace('_', ' ').title())}</small>"
                f"<div class='metric'>{int(decisions.get(label, 0) or 0)}</div></div>"
            )
        out.append("</section>")
        top_agency = agency.get("top") or []
        if top_agency:
            out.append(
                "<h3>Best agency bets</h3><table><tr><th>Title</th><th>Category</th><th>Score</th><th>Decision</th><th>Strengths</th></tr>"
            )
            for item in top_agency[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:100])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{int(item.get('score', 0) or 0)}</td>"
                    f"<td><span class='badge'>{html.escape(str(item.get('decision', '')))}</span></td>"
                    f"<td>{html.escape(', '.join(map(str, item.get('strengths') or [])))}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if agency_plan:
        out.append("<div class='card'><h2>7-day agency plan</h2>")
        out.append(
            f"<p><strong>Status:</strong> <span class='badge'>{html.escape(str(agency_plan.get('status', '')))}</span></p>"
        )
        out.append(f"<p>{html.escape(str(agency_plan.get('weekly_goal', '')))}</p>")
        days_plan = agency_plan.get("days") or []
        if days_plan:
            out.append("<table><tr><th>Day</th><th>Focus</th><th>Trend</th><th>Mix</th><th>Goal</th></tr>")
            for item in days_plan[:7]:
                out.append(
                    f"<tr><td>{int(item.get('day', 0) or 0)}</td>"
                    f"<td>{html.escape(str(item.get('focus', '')))}</td>"
                    f"<td>{html.escape(str(item.get('trend_animal', '')))}</td>"
                    f"<td>{html.escape(str(item.get('mix', '')))}</td>"
                    f"<td>{html.escape(str(item.get('goal', '')))}</td></tr>"
                )
            out.append("</table>")
        blocked_trends = agency_plan.get("blocked_trends") or []
        if blocked_trends:
            out.append("<h3>Blocked trend conflicts</h3><table><tr><th>Category</th><th>Trend</th><th>Reason</th></tr>")
            for item in blocked_trends[:6]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{html.escape(str(item.get('animal', '')))}</td>"
                    f"<td><code>{html.escape(str(item.get('reason', '')))}</code></td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if daily_brief:
        out.append("<div class='card'><h2>Daily agency brief</h2>")
        out.append(
            f"<p><strong>Status:</strong> <span class='badge'>{html.escape(str(daily_brief.get('status', '')))}</span></p>"
        )
        today = daily_brief.get("today") or {}
        if today:
            out.append(
                f"<p><strong>Today:</strong> focus {html.escape(str(today.get('focus', '')))} "
                f"with {html.escape(str(today.get('mix', '')))}.</p>"
            )
        orders = daily_brief.get("orders") or []
        if orders:
            out.append("<ul>")
            for order in orders[:5]:
                out.append(f"<li>{html.escape(str(order))}</li>")
            out.append("</ul>")
        out.append("</div>")

    if agency_gate:
        out.append("<div class='card'><h2>Agency publish gate</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Approved</small><div class='metric'>{int(agency_gate.get('approved', 0) or 0)}</div></div>"
        )
        out.append(f"<div><small>Held</small><div class='metric'>{int(agency_gate.get('held', 0) or 0)}</div></div>")
        out.append("</section>")
        reasons = agency_gate.get("reasons") or {}
        if reasons:
            out.append("<h3>Hold reasons</h3><table><tr><th>Reason</th><th>Stories</th></tr>")
            for reason, count in reasons.items():
                out.append(f"<tr><td><code>{html.escape(str(reason))}</code></td><td>{int(count)}</td></tr>")
            out.append("</table>")
        out.append("</div>")

    if youtube_intelligence:
        out.append("<div class='card'><h2>YouTube API intelligence</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>API coverage</small><div class='metric'>{int(youtube_intelligence.get('coverage_score', 0) or 0)}</div></div>"
        )
        channel = youtube_intelligence.get("channel") or {}
        out.append(
            f"<div><small>Subscribers</small><div class='metric'>{int(channel.get('subscriber_count', 0) or 0):,}</div></div>"
        )
        uploads = youtube_intelligence.get("uploads_inventory") or {}
        out.append(
            f"<div><small>Uploads checked</small><div class='metric'>{int(uploads.get('uploads_checked', 0) or 0)}</div></div>"
        )
        video_audit = youtube_intelligence.get("video_audit") or {}
        out.append(
            f"<div><small>Videos checked</small><div class='metric'>{int(video_audit.get('videos_checked', 0) or 0)}</div></div>"
        )
        out.append("</section>")
        reports = youtube_intelligence.get("analytics_reports") or []
        if reports:
            out.append(
                "<h3>Analytics reports</h3><table><tr><th>Report</th><th>Status</th><th>Rows</th><th>Use</th></tr>"
            )
            for item in reports[:8]:
                out.append(
                    f"<tr><td><code>{html.escape(str(item.get('id', '')))}</code></td>"
                    f"<td>{html.escape(str(item.get('status', '')))}</td>"
                    f"<td>{int(item.get('rows', 0) or 0)}</td>"
                    f"<td>{html.escape(str(item.get('use', ''))[:140])}</td></tr>"
                )
            out.append("</table>")
        capabilities = youtube_intelligence.get("capabilities") or []
        if capabilities:
            out.append("<h3>Data API coverage</h3><table><tr><th>Feature</th><th>Coverage</th><th>Risk</th></tr>")
            for item in capabilities[:10]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('id', '')))}</td>"
                    f"<td><span class='badge'>{html.escape(str(item.get('coverage', '')))}</span></td>"
                    f"<td>{html.escape(str(item.get('risk', '')))}</td></tr>"
                )
            out.append("</table>")
        issues = youtube_intelligence.get("issues") or []
        if issues:
            out.append("<h3>API issues</h3><ul>")
            for issue in issues[:8]:
                out.append(f"<li><code>{html.escape(str(issue))}</code></li>")
            out.append("</ul>")
        out.append("</div>")

    if ai_provider_report:
        out.append("<div class='card'><h2>AI provider router</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Default chain</small><div>{html.escape(' > '.join(map(str, ai_provider_report.get('default_chain') or [])))}</div></div>"
        )
        out.append(
            f"<div><small>JSON chain</small><div>{html.escape(' > '.join(map(str, ai_provider_report.get('json_chain') or [])))}</div></div>"
        )
        out.append(
            f"<div><small>Rewrite chain</small><div>{html.escape(' > '.join(map(str, ai_provider_report.get('rewrite_chain') or [])))}</div></div>"
        )
        out.append("</section>")
        providers = ai_provider_report.get("providers") or []
        if providers:
            out.append(
                "<h3>Provider health</h3><table><tr><th>Provider</th><th>Configured</th><th>Recent success</th><th>Cooldown</th></tr>"
            )
            for item in providers:
                rate = item.get("success_rate")
                rate_text = "unknown" if rate is None else f"{float(rate) * 100:.1f}%"
                out.append(
                    f"<tr><td><code>{html.escape(str(item.get('provider', '')))}</code></td>"
                    f"<td>{'yes' if item.get('configured') else 'no'}</td>"
                    f"<td>{html.escape(rate_text)}</td>"
                    f"<td>{int(item.get('cooldown_seconds', 0) or 0)}s</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if youtube_brain_report:
        summary = youtube_brain_report.get("summary") or {}
        ready_summary = youtube_brain_report.get("publish_ready_summary") or summary
        risk_watchlist = youtube_brain_report.get("risk_watchlist") or []
        out.append("<div class='card'><h2>YouTube brain</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Ready creator score</small><div class='metric'>{float(ready_summary.get('average_score', 0) or 0):.1f}</div></div>"
        )
        states = ready_summary.get("states") or {}
        out.append(
            f"<div><small>Publish-minded</small><div class='metric'>{int(states.get('publish_minded', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Rewrite first</small><div class='metric'>{int(states.get('rewrite_before_publish', 0) or 0)}</div></div>"
        )
        out.append(f"<div><small>Rewrite watchlist</small><div class='metric'>{len(risk_watchlist)}</div></div>")
        out.append("</section>")
        principle = youtube_brain_report.get("operating_principle")
        if principle:
            out.append(f"<p><strong>Principle:</strong> {html.escape(str(principle))}</p>")
        risks = ready_summary.get("top_risks") or {}
        if risks:
            out.append("<h3>Ready creator risks</h3><table><tr><th>Risk</th><th>Stories</th></tr>")
            for risk, count in risks.items():
                out.append(f"<tr><td><code>{html.escape(str(risk))}</code></td><td>{int(count)}</td></tr>")
            out.append("</table>")
        if risk_watchlist:
            out.append("<h3>Creator rewrite watchlist</h3><table><tr><th>Title</th><th>Queue</th><th>Risks</th></tr>")
            for item in risk_watchlist[:8]:
                brain = item.get("youtube_brain") or {}
                out.append(
                    f"<tr><td>{html.escape(_display_title(item)[:100])}</td>"
                    f"<td><code>{html.escape(str(item.get('queue_state', '')))}</code></td>"
                    f"<td>{html.escape(', '.join(map(str, brain.get('risks') or []))[:140])}</td></tr>"
                )
            out.append("</table>")
        top = youtube_brain_report.get("publish_ready_top") or youtube_brain_report.get("top") or []
        if top:
            out.append(
                "<h3>Best creator-minded candidates</h3><table><tr><th>Title</th><th>State</th><th>Score</th><th>Promise</th></tr>"
            )
            for item in top[:8]:
                brain = item.get("youtube_brain") or {}
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:100])}</td>"
                    f"<td><span class='badge'>{html.escape(str(brain.get('state', '')))}</span></td>"
                    f"<td>{float(brain.get('score', 0) or 0):.1f}</td>"
                    f"<td>{html.escape(str(brain.get('viewer_promise', ''))[:120])}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if packaging_report:
        out.append("<div class='card'><h2>Magnetic packaging</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Pending audited</small><div class='metric'>{int(packaging_report.get('pending', 0) or 0)}</div></div>"
        )
        states = packaging_report.get("states") or {}
        out.append(f"<div><small>Magnetic</small><div class='metric'>{int(states.get('magnetic', 0) or 0)}</div></div>")
        out.append(
            f"<div><small>Rewrite packaging</small><div class='metric'>{int(states.get('rewrite_packaging', 0) or 0)}</div></div>"
        )
        out.append("</section>")
        risks = packaging_report.get("top_risks") or {}
        if risks:
            out.append("<h3>Packaging risks</h3><table><tr><th>Risk</th><th>Stories</th></tr>")
            for risk, count in risks.items():
                out.append(f"<tr><td><code>{html.escape(str(risk))}</code></td><td>{int(count)}</td></tr>")
            out.append("</table>")
        top = packaging_report.get("top") or []
        if top:
            out.append(
                "<h3>Strongest packages</h3><table><tr><th>Title</th><th>Thumbnail</th><th>Score</th><th>Comment hook</th></tr>"
            )
            for item in top[:8]:
                pkg = item.get("packaging") or {}
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:100])}</td>"
                    f"<td><strong>{html.escape(str(item.get('thumbnail_text', ''))[:40])}</strong></td>"
                    f"<td>{float(pkg.get('score', 0) or 0):.1f}</td>"
                    f"<td>{html.escape(str(pkg.get('pinned_comment', ''))[:120])}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if autonomous_director:
        out.append("<div class='card'><h2>Autonomous director</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Autonomy score</small><div class='metric'>{int(autonomous_director.get('autonomy_score', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>State</small><div class='metric'>{html.escape(str(autonomous_director.get('state', 'unknown')))}</div></div>"
        )
        conversion = autonomous_director.get("subscriber_conversion") or {}
        out.append(
            f"<div><small>Subs / 1k views</small><div class='metric'>{float(conversion.get('subs_per_1000_views', 0) or 0):.2f}</div></div>"
        )
        quota = autonomous_director.get("quota_budget") or {}
        out.append(
            f"<div><small>API quota risk</small><div class='metric'>{int(quota.get('risk_score', 0) or 0)}</div></div>"
        )
        out.append("</section>")
        decisions = autonomous_director.get("decisions") or []
        if decisions:
            out.append("<h3>Decisions</h3><ul>")
            for decision in decisions[:8]:
                out.append(f"<li>{html.escape(str(decision))}</li>")
            out.append("</ul>")
        mix = autonomous_director.get("publish_mix") or {}
        if mix:
            out.append("<h3>Publish mix</h3><table><tr><th>Lane</th><th>%</th></tr>")
            for lane, pct in mix.items():
                out.append(f"<tr><td>{html.escape(str(lane))}</td><td>{int(pct or 0)}</td></tr>")
            out.append("</table>")
        priorities = autonomous_director.get("category_priorities") or []
        if priorities:
            out.append("<h3>Category priorities</h3><table><tr><th>Category</th><th>Score</th></tr>")
            for item in priorities[:6]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('value', '')))}</td><td>{float(item.get('score', 0) or 0):.1f}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if autonomous_growth_plan:
        out.append("<div class='card'><h2>Autonomous growth loop</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Loop score</small><div class='metric'>{int(autonomous_growth_plan.get('autonomy_score', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Mode</small><div class='metric'>{html.escape(str(autonomous_growth_plan.get('operating_mode', 'unknown')))}</div></div>"
        )
        data_status = autonomous_growth_plan.get("data_status") or {}
        out.append(
            f"<div><small>Tracked Shorts</small><div class='metric'>{int(data_status.get('shorts_tracked', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Queue annotated</small><div class='metric'>{int(autonomous_growth_plan.get('queue_annotations_written', 0) or 0)}</div></div>"
        )
        out.append("</section>")
        policy = autonomous_growth_plan.get("production_policy") or {}
        if policy:
            out.append("<h3>Production policy</h3><table><tr><th>Lane</th><th>%</th></tr>")
            for key in ("exploit_percent", "sequence_percent", "experiment_percent", "recovery_percent"):
                out.append(
                    f"<tr><td>{html.escape(str(key).replace('_percent', ''))}</td><td>{int(policy.get(key, 0) or 0)}</td></tr>"
                )
            out.append("</table>")
        sequence_bank = autonomous_growth_plan.get("sequence_bank") or {}
        audience_requests = autonomous_growth_plan.get("audience_requests") or {}
        if sequence_bank or audience_requests:
            out.append("<section class='row'>")
            out.append(
                f"<div><small>Sequence variants</small><div class='metric'>{int(sequence_bank.get('variant_count', 0) or 0)}</div></div>"
            )
            out.append(
                f"<div><small>Source winners</small><div class='metric'>{int(sequence_bank.get('source_winners', 0) or 0)}</div></div>"
            )
            requested = audience_requests.get("requested_animals") or []
            out.append(f"<div><small>Viewer animal requests</small><div class='metric'>{len(requested)}</div></div>")
            out.append("</section>")
        hypotheses = (autonomous_growth_plan.get("experiment_bank") or {}).get("hypotheses") or []
        if hypotheses:
            out.append(
                "<h3>Active hypotheses</h3><table><tr><th>ID</th><th>Lane</th><th>Statement</th><th>Target</th></tr>"
            )
            for item in hypotheses[:8]:
                out.append(
                    f"<tr><td><code>{html.escape(str(item.get('id', '')))}</code></td>"
                    f"<td><span class='badge'>{html.escape(str(item.get('lane', '')))}</span></td>"
                    f"<td>{html.escape(str(item.get('statement', ''))[:140])}</td>"
                    f"<td>{html.escape(str(item.get('target', '')))}</td></tr>"
                )
            out.append("</table>")
        loop_queue = autonomous_growth_plan.get("queue") or {}
        candidates = loop_queue.get("top_candidates") or []
        if candidates:
            out.append(
                "<h3>Autonomous queue order</h3><table><tr><th>Title</th><th>Lane</th><th>Hypothesis</th><th>Test title</th><th>Priority</th></tr>"
            )
            for item in candidates[:8]:
                lab = item.get("packaging_lab") or {}
                test_titles = lab.get("title_variants") or []
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:100])}</td>"
                    f"<td><span class='badge'>{html.escape(str(item.get('lane', '')))}</span></td>"
                    f"<td><code>{html.escape(str(item.get('hypothesis_id', '')))}</code></td>"
                    f"<td>{html.escape(str((test_titles or [''])[0])[:80])}</td>"
                    f"<td>{float(item.get('autonomy_priority', 0) or 0):.1f}</td></tr>"
                )
            out.append("</table>")
        decisions = autonomous_growth_plan.get("decisions") or []
        if decisions:
            out.append("<h3>Loop decisions</h3><ul>")
            for decision in decisions[:8]:
                out.append(f"<li>{html.escape(str(decision))}</li>")
            out.append("</ul>")
        out.append("</div>")

    if scale_blueprint:
        out.append("<div class='card'><h2>Million-view scale blueprint</h2>")
        summary = scale_blueprint.get("dashboard_summary") or {}
        baseline = scale_blueprint.get("baseline") or {}
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Phase</small><div class='metric'>{html.escape(str(summary.get('phase') or scale_blueprint.get('phase') or 'unknown'))}</div></div>"
        )
        out.append(
            f"<div><small>28d views</small><div class='metric'>{int(baseline.get('views', 0) or 0):,}</div></div>"
        )
        out.append(
            f"<div><small>Stayed to watch</small><div class='metric'>{float(baseline.get('stayed_to_watch_rate', 0) or 0) * 100:.1f}%</div></div>"
        )
        out.append(
            f"<div><small>Recurring viewers</small><div class='metric'>{float(baseline.get('recurring_viewer_rate', 0) or 0) * 100:.1f}%</div></div>"
        )
        out.append(
            f"<div><small>Subs / 1k views</small><div class='metric'>{float(baseline.get('subs_per_1000_views', 0) or 0):.2f}</div></div>"
        )
        out.append(
            f"<div><small>Top bottleneck</small><div class='metric'>{html.escape(str(summary.get('top_bottleneck', 'none')))}</div></div>"
        )
        out.append("</section>")
        north_star = scale_blueprint.get("north_star")
        if north_star:
            out.append(f"<p><strong>North star:</strong> {html.escape(str(north_star))}</p>")
        commands = scale_blueprint.get("production_commands") or []
        if commands:
            out.append("<h3>Scale commands</h3><ul>")
            for command in commands[:8]:
                out.append(f"<li>{html.escape(str(command))}</li>")
            out.append("</ul>")
        bottlenecks_rows = scale_blueprint.get("bottlenecks") or []
        if bottlenecks_rows:
            out.append(
                "<h3>Bottlenecks</h3><table><tr><th>Severity</th><th>Metric</th><th>Current</th><th>Target</th><th>Action</th></tr>"
            )
            for item in bottlenecks_rows[:6]:
                out.append(
                    f"<tr><td><span class='badge'>{html.escape(str(item.get('severity', '')))}</span></td>"
                    f"<td><code>{html.escape(str(item.get('metric', '')))}</code></td>"
                    f"<td>{html.escape(str(item.get('current', '')))}</td>"
                    f"<td>{html.escape(str(item.get('target', '')))}</td>"
                    f"<td>{html.escape(str(item.get('action', ''))[:150])}</td></tr>"
                )
            out.append("</table>")
        lanes = scale_blueprint.get("series_lanes") or []
        if lanes:
            out.append(
                "<h3>Series lanes</h3><table><tr><th>Lane</th><th>State</th><th>Retention</th><th>Supply</th><th>Promise</th></tr>"
            )
            for item in lanes[:6]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('lane', '')))}</td>"
                    f"<td><span class='badge'>{html.escape(str(item.get('state', '')))}</span></td>"
                    f"<td>{float(item.get('retention', 0) or 0):.1f}%</td>"
                    f"<td>{int(item.get('publish_ready_supply', 0) or 0)}</td>"
                    f"<td>{html.escape(str(item.get('promise', ''))[:130])}</td></tr>"
                )
            out.append("</table>")
        video_actions = (scale_blueprint.get("video_action_plan") or {}).get("actions") or []
        if video_actions:
            out.append(
                "<h3>Winner actions</h3><table><tr><th>Action</th><th>Title</th><th>Views</th><th>Retention</th><th>Why</th></tr>"
            )
            for item in video_actions[:8]:
                out.append(
                    f"<tr><td><span class='badge'>{html.escape(str(item.get('action', '')))}</span></td>"
                    f"<td>{html.escape(str(item.get('title', ''))[:90])}</td>"
                    f"<td>{int(item.get('views', 0) or 0):,}</td>"
                    f"<td>{float(item.get('retention', 0) or 0):.1f}%</td>"
                    f"<td>{html.escape(str(item.get('reason', ''))[:120])}</td></tr>"
                )
            out.append("</table>")
        milestones = scale_blueprint.get("milestone_path") or []
        if milestones:
            out.append("<h3>Milestone path</h3><table><tr><th>Milestone</th><th>Remaining</th><th>Job</th></tr>")
            for item in milestones[:4]:
                remaining = item.get("remaining_subscribers", item.get("remaining_views_28d", 0))
                out.append(
                    f"<tr><td>{html.escape(str(item.get('milestone', '')))}</td>"
                    f"<td>{int(remaining or 0):,}</td>"
                    f"<td>{html.escape(str(item.get('job', ''))[:140])}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if channel_success:
        out.append("<div class='card'><h2>Channel success engine</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Success score</small><div class='metric'>{float(channel_success.get('success_score', 0) or 0):.1f}</div></div>"
        )
        out.append(
            f"<div><small>State</small><div class='metric'>{html.escape(str(channel_success.get('state', 'unknown')))}</div></div>"
        )
        retention = channel_success.get("retention") or {}
        out.append(
            f"<div><small>Retention gap</small><div class='metric'>{float(retention.get('gap_to_floor', 0) or 0):.1f}</div></div>"
        )
        reach = channel_success.get("studio_reach") or {}
        out.append(
            f"<div><small>Stayed to watch</small><div class='metric'>{float(reach.get('stayed_to_watch_rate', 0) or 0) * 100:.1f}%</div></div>"
        )
        out.append(
            f"<div><small>Swiped away</small><div class='metric'>{float(reach.get('swipe_away_rate', 0) or 0) * 100:.1f}%</div></div>"
        )
        conversion = channel_success.get("subscriber_conversion") or {}
        out.append(
            f"<div><small>Subs / 1k target gap</small><div class='metric'>{float(conversion.get('gap_to_target', 0) or 0):.2f}</div></div>"
        )
        recurrence = channel_success.get("audience_recurrence") or {}
        out.append(
            f"<div><small>Recurring audience</small><div class='metric'>{float(recurrence.get('recurring_viewer_rate', 0) or 0) * 100:.1f}%</div></div>"
        )
        out.append("</section>")
        if reach.get("diagnosis") or recurrence.get("diagnosis"):
            out.append("<h3>Objective diagnosis</h3><ul>")
            if reach.get("diagnosis"):
                out.append(f"<li>{html.escape(str(reach.get('diagnosis')))}</li>")
            if recurrence.get("diagnosis"):
                out.append(f"<li>{html.escape(str(recurrence.get('diagnosis')))}</li>")
            out.append("</ul>")
        principle = channel_success.get("operating_principle")
        if principle:
            out.append(f"<p><strong>Principle:</strong> {html.escape(str(principle))}</p>")
        actions = channel_success.get("next_actions") or []
        if actions:
            out.append("<h3>Success actions</h3><ul>")
            for action in actions[:10]:
                out.append(f"<li>{html.escape(str(action))}</li>")
            out.append("</ul>")
        first_day = channel_success.get("first_24h") or {}
        winners_24h = first_day.get("winners") or []
        rework_24h = first_day.get("rework") or []
        if winners_24h or rework_24h:
            out.append(
                "<h3>First 24h reactions</h3><table><tr><th>Lane</th><th>Title</th><th>Views</th><th>Growth</th><th>Retention</th></tr>"
            )
            for lane, items in (("Winner", winners_24h), ("Rework hook", rework_24h)):
                for item in items[:4]:
                    out.append(
                        f"<tr><td><span class='badge'>{html.escape(lane)}</span></td>"
                        f"<td>{html.escape(_display_title(item)[:90])}</td>"
                        f"<td>{int(item.get('views', 0) or 0):,}</td>"
                        f"<td>{float(item.get('growth_score', 0) or 0):.1f}</td>"
                        f"<td>{float(item.get('retention', 0) or 0):.1f}%</td></tr>"
                    )
            out.append("</table>")
        series = (channel_success.get("series_system") or {}).get("lanes") or []
        if series:
            out.append(
                "<h3>Series lanes</h3><table><tr><th>Series</th><th>State</th><th>Score</th><th>Promise</th></tr>"
            )
            for item in series[:6]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('series', '')))}</td>"
                    f"<td><span class='badge'>{html.escape(str(item.get('state', '')))}</span></td>"
                    f"<td>{float(item.get('priority_score', 0) or 0):.1f}</td>"
                    f"<td>{html.escape(str(item.get('promise', '')))}</td></tr>"
                )
            out.append("</table>")
        audience = channel_success.get("audience_loop") or {}
        prompts = audience.get("prompts") or []
        if prompts:
            out.append("<h3>Audience loop prompts</h3><ul>")
            for prompt in prompts[:5]:
                out.append(f"<li>{html.escape(str(prompt))}</li>")
            out.append("</ul>")
        identity = channel_success.get("identity") or {}
        if identity:
            out.append(f"<p><strong>Brand promise:</strong> {html.escape(str(identity.get('brand_promise', '')))}</p>")
        out.append("</div>")

    if success_rewriter:
        out.append("<div class='card'><h2>Success rewriter</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Rewritten</small><div class='metric'>{int(success_rewriter.get('rewritten', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Held before</small><div class='metric'>{int(success_rewriter.get('before_held', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Held after</small><div class='metric'>{int(success_rewriter.get('after_held', 0) or 0)}</div></div>"
        )
        out.append("</section>")
        before_reasons = success_rewriter.get("before_reasons") or {}
        after_reasons = success_rewriter.get("after_reasons") or {}
        if before_reasons or after_reasons:
            out.append("<h3>Gate reasons</h3><table><tr><th>Reason</th><th>Before</th><th>After</th></tr>")
            reason_keys = sorted(set(before_reasons) | set(after_reasons))
            for reason in reason_keys[:10]:
                out.append(
                    f"<tr><td><code>{html.escape(str(reason))}</code></td>"
                    f"<td>{int(before_reasons.get(reason, 0) or 0)}</td>"
                    f"<td>{int(after_reasons.get(reason, 0) or 0)}</td></tr>"
                )
            out.append("</table>")
        items = success_rewriter.get("items") or []
        if items:
            out.append(
                "<h3>Recovered candidates</h3><table><tr><th>Title</th><th>Category</th><th>Words</th><th>Reasons</th></tr>"
            )
            for item in items[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:90])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{int(item.get('script_words', 0) or 0)}</td>"
                    f"<td>{html.escape(', '.join(map(str, item.get('reasons') or []))[:140])}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if winner_sequels:
        out.append("<div class='card'><h2>Winner sequel factory</h2>")
        out.append(
            f"<p><strong>Created:</strong> {int(winner_sequels.get('created', 0) or 0)} "
            f"from {int(winner_sequels.get('candidate_count', 0) or 0)} candidate(s).</p>"
        )
        candidates = winner_sequels.get("candidates") or []
        if candidates:
            out.append("<table><tr><th>Source</th><th>Category</th><th>Growth</th><th>Views</th></tr>")
            for item in candidates[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('source_title', ''))[:90])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{float(item.get('growth_score', 0) or 0):.1f}</td>"
                    f"<td>{int(item.get('views', 0) or 0):,}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if remake_factory:
        out.append("<div class='card'><h2>Remake factory</h2>")
        out.append(f"<p><strong>Drafts created:</strong> {int(remake_factory.get('created', 0) or 0)}</p>")
        ids = remake_factory.get("created_ids") or []
        if ids:
            out.append("<p><strong>Queue ids:</strong> " + html.escape(", ".join(map(str, ids[:8]))) + "</p>")
        out.append("</div>")

    if rewrite_queue:
        out.append("<div class='card'><h2>Retention rewrite queue</h2>")
        out.append(f"<p><strong>Needs rewrite:</strong> {int(rewrite_queue.get('count', 0) or 0)}</p>")
        items = rewrite_queue.get("items") or []
        if items:
            out.append("<table><tr><th>Title</th><th>Category</th><th>Score</th><th>Fixes</th></tr>")
            for item in items[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:90])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{int(item.get('score', 0) or 0)}</td>"
                    f"<td>{html.escape('; '.join(map(str, item.get('fixes') or []))[:140])}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if retention_rewriter:
        out.append("<div class='card'><h2>Retention rewriter</h2>")
        out.append(f"<p><strong>Rewritten:</strong> {int(retention_rewriter.get('rewritten', 0) or 0)}</p>")
        items = retention_rewriter.get("items") or []
        if items:
            out.append("<table><tr><th>Title</th><th>Before</th><th>After</th></tr>")
            for item in items[:8]:
                title = _display_title(item)
                out.append(
                    f"<tr><td>{html.escape(title[:100])}</td>"
                    f"<td>{int(item.get('before', 0) or 0)}</td>"
                    f"<td>{int(item.get('after', 0) or 0)}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if category_recovery:
        out.append("<div class='card'><h2>Category recovery</h2>")
        plans = category_recovery.get("plans") or []
        if plans:
            out.append("<table><tr><th>Category</th><th>Retention</th><th>Allowed formats</th><th>Rules</th></tr>")
            for item in plans[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{float(item.get('retention', 0) or 0):.1f}</td>"
                    f"<td>{html.escape(', '.join(map(str, item.get('allowed_formats') or [])))}</td>"
                    f"<td>{html.escape('; '.join(map(str, item.get('rules') or []))[:150])}</td></tr>"
                )
            out.append("</table>")
        else:
            out.append("<p>No paused categories need recovery.</p>")
        out.append("</div>")

    if category_recovery_rewriter:
        out.append("<div class='card'><h2>Category recovery rewriter</h2>")
        out.append(f"<p><strong>Rewritten:</strong> {int(category_recovery_rewriter.get('rewritten', 0) or 0)}</p>")
        items = category_recovery_rewriter.get("items") or []
        if items:
            out.append("<table><tr><th>Title</th><th>Category</th><th>Format</th><th>Angle</th></tr>")
            for item in items[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:90])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{html.escape(str(item.get('format', '')))}</td>"
                    f"<td>{html.escape(str(item.get('angle', '')))}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if visual_report:
        out.append("<div class='card'><h2>Visual QA coverage</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Coverage</small><div class='metric'>{float(visual_report.get('coverage_pct', 0) or 0):.1f}%</div></div>"
        )
        out.append(
            f"<div><small>Legacy inferred</small><div class='metric'>{int(visual_report.get('inferred_legacy_checked', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Checked</small><div class='metric'>{int(visual_report.get('checked', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Rejected</small><div class='metric'>{int(visual_report.get('rejected', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>CTR frames</small><div class='metric'>{int(visual_report.get('ctr_checked', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Strong CTR</small><div class='metric'>{int(visual_report.get('ctr_strong', 0) or 0)}</div></div>"
        )
        out.append("</section>")
        visual_learning = visual_report.get("visual_learning") or {}
        if visual_learning:
            out.append(
                f"<p><strong>Winning visual profile:</strong> <code>{html.escape(str(visual_learning.get('winner') or 'collecting samples'))}</code></p>"
            )
            profiles = visual_learning.get("profiles") or []
            if profiles:
                out.append(
                    "<table><tr><th>Profile</th><th>n</th><th>Growth</th><th>Retention</th><th>CTR score</th></tr>"
                )
                for item in profiles[:6]:
                    out.append(
                        f"<tr><td><code>{html.escape(str(item.get('profile', '')))}</code></td>"
                        f"<td>{int(item.get('n', 0) or 0)}</td>"
                        f"<td>{float(item.get('mean_growth_score', 0) or 0):.1f}</td>"
                        f"<td>{float(item.get('mean_retention', 0) or 0):.1f}</td>"
                        f"<td>{float(item.get('mean_visual_ctr_score', 0) or 0):.1f}</td></tr>"
                    )
                out.append("</table>")
        out.append("</div>")

    if visual_backfill:
        out.append("<div class='card'><h2>Visual QA backfill</h2>")
        out.append(
            f"<p><strong>Legacy unchecked:</strong> {int(visual_backfill.get('legacy_unchecked', 0) or 0)} "
            f"- <strong>Inferred approved:</strong> {int(visual_backfill.get('inferred_approved', 0) or 0)} "
            f"- <strong>Inferred rejected:</strong> {int(visual_backfill.get('inferred_rejected', 0) or 0)}</p>"
        )
        out.append("</div>")

    if narrator_report:
        out.append("<div class='card'><h2>Narrator optimizer</h2>")
        winner = narrator_report.get("winner") or "exploring"
        out.append(f"<p><strong>Current winner:</strong> <span class='badge'>{html.escape(str(winner))}</span></p>")
        voices = narrator_report.get("voices") or []
        backfill = narrator_report.get("legacy_marker_backfill") or {}
        if backfill:
            out.append(
                f"<p><strong>Matched legacy markers:</strong> {int(backfill.get('matched_top_performers', 0) or 0)}</p>"
            )
        if voices:
            out.append("<table><tr><th>Voice</th><th>n</th><th>Growth</th><th>Retention</th></tr>")
            for item in voices[:8]:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('voice', '')))}</td>"
                    f"<td>{int(item.get('n', 0) or 0)}</td>"
                    f"<td>{float(item.get('mean_growth', 0) or 0):.1f}</td>"
                    f"<td>{float(item.get('mean_retention', 0) or 0):.1f}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if fact_ledger:
        out.append("<div class='card'><h2>Fact ledger</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Duplicate risk</small><div class='metric'>{int(fact_ledger.get('risk_score', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Duplicate clusters</small><div class='metric'>{len(fact_ledger.get('duplicate_clusters') or [])}</div></div>"
        )
        out.append("</section>")
        phrases = fact_ledger.get("repeated_phrases") or {}
        if phrases:
            out.append("<h3>Repeated phrases</h3><table><tr><th>Phrase</th><th>Uses</th></tr>")
            for phrase, count in list(phrases.items())[:8]:
                out.append(f"<tr><td>{html.escape(str(phrase))}</td><td>{int(count)}</td></tr>")
            out.append("</table>")
        out.append("</div>")

    if legacy_backfill:
        out.append("<div class='card'><h2>Legacy analytics backfill</h2>")
        out.append(
            f"<p><strong>Markers needing derived metadata:</strong> "
            f"{int(legacy_backfill.get('derived_missing_count', legacy_backfill.get('count', 0)) or 0)}</p>"
        )
        if legacy_backfill.get("source_missing_count"):
            out.append(
                f"<p><strong>Markers missing original hook:</strong> "
                f"{int(legacy_backfill.get('source_missing_count', 0) or 0)}</p>"
            )
        missing_label_key = (
            "missing_derived_fields" if legacy_backfill.get("derived_missing_count") is not None else "missing"
        )
        markers = legacy_backfill.get("markers") or []
        if markers:
            out.append("<table><tr><th>Title</th><th>Missing</th><th>Derived format</th><th>Retention fix</th></tr>")
            for item in markers[:8]:
                derived = item.get("derived") or {}
                surgery = derived.get("retention_surgery") or {}
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:90])}</td>"
                    f"<td>{html.escape(', '.join(map(str, item.get(missing_label_key) or [])))}</td>"
                    f"<td>{html.escape(str(derived.get('story_format', '')))}</td>"
                    f"<td>{html.escape('; '.join(map(str, surgery.get('fixes') or []))[:120])}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if any(
        (
            fact_guard_report,
            experiment_registry,
            underpowered_tests,
            music_bed_report,
            retention_reconciliation,
            crosspost_pack,
            render_bench,
            security_manifest,
            upload_intents,
            originality_rows,
            provenance_rows,
        )
    ):
        out.append("<div class='card'><h2>Zero-cost governance</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Fact guard items</small><div class='metric'>{int(fact_guard_report.get('items', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Experiment axes</small><div class='metric'>{len((experiment_registry.get('axes') or {}))}</div></div>"
        )
        out.append(
            f"<div><small>Underpowered tests</small><div class='metric'>{len(underpowered_tests.get('underpowered_tests') or [])}</div></div>"
        )
        out.append(f"<div><small>Upload intents</small><div class='metric'>{len(upload_intents)}</div></div>")
        out.append(f"<div><small>Originality packs</small><div class='metric'>{len(originality_rows)}</div></div>")
        out.append(f"<div><small>Provenance rows</small><div class='metric'>{len(provenance_rows)}</div></div>")
        out.append("</section>")
        if retention_reconciliation:
            out.append(
                f"<p><strong>Retention reconciliation:</strong> {int(retention_reconciliation.get('matched_videos', 0) or 0)} matched, "
                f"{len(retention_reconciliation.get('out_of_tolerance') or [])} outside 2% delta.</p>"
            )
        if music_bed_report:
            out.append(
                f"<p><strong>Music bed canary:</strong> {html.escape(str(music_bed_report.get('rollout_state', 'unknown')))} "
                f"at {int(music_bed_report.get('canary_percent', 0) or 0)}%.</p>"
            )
        if security_manifest:
            out.append(
                f"<p><strong>SBOM:</strong> {int(security_manifest.get('component_count', 0) or 0)} Python components recorded.</p>"
            )
        out.append("</div>")

    if control_plane:
        metrics = control_plane.get("metrics") or {}
        out.append("<div class='card'><h2>Control plane pressure</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>State</small><div class='metric'>{html.escape(str(control_plane.get('state', 'unknown')))}</div></div>"
        )
        out.append(
            f"<div><small>Pressure</small><div class='metric'>{int(control_plane.get('pressure_score', 0) or 0)}/100</div></div>"
        )
        out.append(
            f"<div><small>Live state files</small><div class='metric'>{int(metrics.get('live_state_files', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Queue size</small><div class='metric'>{int(metrics.get('stories_queue_lines', 0) or 0):,}</div></div>"
        )
        out.append(
            f"<div><small>Workflow state refs</small><div class='metric'>{int(metrics.get('state_path_refs', 0) or 0)}</div></div>"
        )
        out.append("</section>")
        commands = control_plane.get("commands") or []
        if commands:
            out.append("<h3>Control commands</h3><ul>")
            for command in commands[:5]:
                out.append(f"<li>{html.escape(str(command))}</li>")
            out.append("</ul>")
        lanes = control_plane.get("migration_lanes") or []
        if lanes:
            out.append(
                "<h3>Migration lanes</h3><table><tr><th>Priority</th><th>Lane</th><th>Target</th><th>Reason</th></tr>"
            )
            for lane in sorted(lanes, key=lambda item: int(item.get("priority", 99) or 99))[:5]:
                out.append(
                    f"<tr><td>{int(lane.get('priority', 0) or 0)}</td>"
                    f"<td><code>{html.escape(str(lane.get('lane', '')))}</code></td>"
                    f"<td>{html.escape(str(lane.get('target', '')))}</td>"
                    f"<td>{html.escape(str(lane.get('reason', '')))}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if any((queue_audit, reject_report, next_shorts, dry_run_publish, sequence_plan, post24_review, publish_schedule)):
        out.append("<div class='card'><h2>Operations cockpit</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Queue audited</small><div class='metric'>{int(queue_audit.get('pending', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Dry-run eligible</small><div class='metric'>{int(dry_run_publish.get('eligible_count', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Scale-ready</small><div class='metric'>{int(dry_run_publish.get('scale_ready_count', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Observe first</small><div class='metric'>{int(dry_run_publish.get('observe_before_scaling_count', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Rejected queue</small><div class='metric'>{int(reject_report.get('total', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Sequence variants</small><div class='metric'>{len(sequence_plan.get('variants') or [])}</div></div>"
        )
        out.append("</section>")
        schedule_slots = publish_schedule.get("recommended_slots") or []
        if publish_schedule:
            out.append(
                f"<p><strong>Publish cadence:</strong> {int(publish_schedule.get('recommended_shorts_per_day', 0) or 0)} "
                f"Shorts/day at {html.escape(', '.join(map(str, schedule_slots)))} "
                f"{html.escape(str(publish_schedule.get('timezone', 'UTC')))}.</p>"
            )
        post_counts = post24_review.get("counts") or {}
        if post_counts:
            out.append("<h3>24h decisions</h3><table><tr><th>Decision</th><th>Shorts</th></tr>")
            for state, count in post_counts.items():
                out.append(f"<tr><td><code>{html.escape(str(state))}</code></td><td>{int(count)}</td></tr>")
            out.append("</table>")
        states = queue_audit.get("states") or {}
        rights = queue_audit.get("rights") or {}
        if states or rights:
            out.append("<h3>Publish gates</h3><table><tr><th>Gate</th><th>State</th><th>Count</th></tr>")
            for state, count in states.items():
                out.append(
                    f"<tr><td>publish_score</td><td><code>{html.escape(str(state))}</code></td><td>{int(count)}</td></tr>"
                )
            for state, count in rights.items():
                out.append(
                    f"<tr><td>rights</td><td><code>{html.escape(str(state))}</code></td><td>{int(count)}</td></tr>"
                )
            out.append("</table>")
        mechanism_clusters = queue_audit.get("mechanism_clusters") or {}
        if mechanism_clusters:
            out.append("<h3>Mechanism concentration</h3><table><tr><th>Mechanism</th><th>Stories</th></tr>")
            for mechanism, count in list(mechanism_clusters.items())[:8]:
                out.append(f"<tr><td><code>{html.escape(str(mechanism))}</code></td><td>{int(count)}</td></tr>")
            out.append("</table>")
        title_shape_mix = next_shorts.get("title_shape_mix") or {}
        title_shape_warnings = title_shape_mix.get("warnings") or []
        if title_shape_warnings:
            out.append(
                "<h3>Title shape concentration</h3>"
                "<table><tr><th>Window</th><th>Repeated promise</th><th>Share</th><th>Action</th></tr>"
            )
            for warning in title_shape_warnings[:5]:
                share = float(warning.get("share", 0) or 0) * 100
                out.append(
                    f"<tr><td>Top {int(warning.get('window', 0) or 0)}</td>"
                    f"<td><code>{html.escape(str(warning.get('shape', '')))}</code></td>"
                    f"<td>{int(warning.get('count', 0) or 0)} shorts / {share:.0f}%</td>"
                    f"<td>{html.escape(str(warning.get('action', 'alternate title promises')))}</td></tr>"
                )
            out.append("</table>")
            rewrite_candidates = title_shape_mix.get("rewrite_candidates") or []
            if rewrite_candidates:
                out.append("<h3>Title rewrites to queue</h3><table><tr><th>Rank</th><th>Title</th><th>Action</th></tr>")
                for item in rewrite_candidates[:6]:
                    suggestions = item.get("suggested_titles") or []
                    suggestion_text = "; ".join(str(title) for title in suggestions[:2])
                    title_cell = html.escape(str(item.get("title", ""))[:100])
                    if suggestion_text:
                        title_cell += f"<br><small>{html.escape(suggestion_text[:160])}</small>"
                    out.append(
                        f"<tr><td>{int(item.get('rank', 0) or 0)}</td>"
                        f"<td>{title_cell}</td>"
                        f"<td>{html.escape(str(item.get('action', '')))}</td></tr>"
                    )
                out.append("</table>")
        next_items = next_shorts.get("items") or []
        if next_items:
            out.append(
                "<h3>Next Shorts by score</h3><table><tr><th>Title</th><th>Category</th><th>Mechanism</th><th>Score</th><th>State</th></tr>"
            )
            for item in next_items[:8]:
                score = item.get("score") or {}
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:100])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td><code>{html.escape(str(item.get('mechanism_cluster', '') or 'unique'))}</code></td>"
                    f"<td>{float(score.get('score', 0) or 0):.1f}</td>"
                    f"<td><code>{html.escape(str(score.get('state', '')))}</code></td></tr>"
                )
            out.append("</table>")
        latest_rejections = reject_report.get("latest") or []
        if latest_rejections:
            out.append("<h3>Latest rejections</h3><table><tr><th>Title</th><th>Stage</th><th>Reasons</th></tr>")
            for item in latest_rejections[-8:]:
                title = _display_title(item)
                out.append(
                    f"<tr><td>{html.escape(title[:100])}</td>"
                    f"<td><code>{html.escape(str(item.get('stage', '')))}</code></td>"
                    f"<td>{html.escape(', '.join(map(str, item.get('reasons') or []))[:140])}</td></tr>"
                )
            out.append("</table>")
        variants = sequence_plan.get("variants") or []
        if variants:
            out.append("<h3>Sequence factory</h3><table><tr><th>Variant</th><th>Title</th><th>Category</th></tr>")
            for item in variants[:8]:
                out.append(
                    f"<tr><td><code>{html.escape(str(item.get('sequence_variant', '')))}</code></td>"
                    f"<td>{html.escape(str(item.get('title') or item.get('seo_title') or '')[:100])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if queue_studio.get("pending"):
        out.append("<div class='card'><h2>Studio queue health</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Pending stories</small><div class='metric'>{int(queue_studio.get('pending', 0))}</div></div>"
        )
        out.append(
            f"<div><small>Editor-approved</small><div class='metric'>{int(queue_studio.get('approved', 0))}</div></div>"
        )
        out.append(
            f"<div><small>Studio-polished</small><div class='metric'>{int(queue_studio.get('rescued', 0))}</div></div>"
        )
        out.append("</section>")
        labels = queue_studio.get("labels") or {}
        if labels:
            out.append("<h3>Humanity labels in queue</h3><table><tr><th>Label</th><th>Stories</th></tr>")
            for label, count in labels.items():
                out.append(
                    f"<tr><td><span class='badge'>{html.escape(str(label))}</span></td><td>{int(count)}</td></tr>"
                )
            out.append("</table>")
        states = queue_studio.get("states") or {}
        if states:
            out.append("<h3>Editorial states</h3><table><tr><th>State</th><th>Stories</th></tr>")
            for state, count in states.items():
                out.append(f"<tr><td><code>{html.escape(str(state))}</code></td><td>{int(count)}</td></tr>")
            out.append("</table>")
        commands = queue_studio.get("commands") or []
        if commands:
            out.append("<h3>Command center</h3><ul>")
            for command in commands:
                out.append(f"<li>{html.escape(str(command))}</li>")
            out.append("</ul>")
        categories = queue_studio.get("categories") or {}
        if categories:
            all_states = sorted({state for by_state in categories.values() for state in (by_state or {}).keys()})
            out.append("<h3>Queue by category</h3><table><tr><th>Category</th>")
            for state in all_states:
                out.append(f"<th>{html.escape(str(state))}</th>")
            out.append("</tr>")
            for category, by_state in categories.items():
                out.append(f"<tr><td>{html.escape(str(category))}</td>")
                for state in all_states:
                    out.append(f"<td>{int((by_state or {}).get(state, 0) or 0)}</td>")
                out.append("</tr>")
            out.append("</table>")
        reasons = queue_studio.get("reasons") or {}
        if reasons:
            out.append("<h3>Top blocking reasons</h3><table><tr><th>Reason</th><th>Stories</th></tr>")
            for reason, count in reasons.items():
                out.append(f"<tr><td>{html.escape(str(reason))}</td><td>{int(count)}</td></tr>")
            out.append("</table>")
        top_queue = queue_studio.get("top") or []
        if top_queue:
            out.append(
                "<h3>Next best candidates</h3><table><tr><th>Title</th><th>Category</th><th>Editorial</th><th>Humanity</th><th>Agency</th></tr>"
            )
            for item in top_queue:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:100])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{int(item.get('editorial_score', 0) or 0)}</td>"
                    f"<td>{int(item.get('humanity_score', 0) or 0)} "
                    f"<span class='badge'>{html.escape(str(item.get('humanity_label', '')))}</span></td>"
                    f"<td>{int(item.get('agency_score', 0) or 0)} "
                    f"<span class='badge'>{html.escape(str(item.get('agency_decision', '')))}</span></td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if learning_profile:
        out.append("<div class='card'><h2>Learning profile</h2>")
        tiers = learning_profile.get("retention_tiers") or {}
        if tiers:
            out.append("<h3>Retention tiers</h3><table><tr><th>Tier</th><th>Shorts</th></tr>")
            for tier, count in tiers.items():
                out.append(
                    f"<tr><td><span class='badge'>{html.escape(str(tier))}</span></td><td>{int(count)}</td></tr>"
                )
            out.append("</table>")
        for label, key in (
            ("Winning categories", "winning_categories"),
            ("Winning formats", "winning_formats"),
            ("Winning title keywords", "winning_title_keywords"),
            ("Winning humanity labels", "winning_humanity_labels"),
        ):
            values = learning_profile.get(key) or []
            if key == "winning_title_keywords":
                values = [value for value in values if str(value).lower() not in stale_bad_title_keywords]
            if values:
                out.append(f"<p><strong>{label}:</strong> {html.escape(', '.join(map(str, values[:12])))}</p>")
        rules = learning_profile.get("rules") or []
        if rules:
            out.append("<h3>Production rules</h3><ul>")
            for rule in rules[:5]:
                out.append(f"<li>{html.escape(str(rule))}</li>")
            out.append("</ul>")
        out.append("</div>")

    if comments:
        out.append("<div class='card'><h2>Audience requests</h2>")
        out.append("<section class='row'>")
        out.append(
            f"<div><small>Comments sampled</small><div class='metric'>{int(comments.get('comments_sampled', 0) or 0)}</div></div>"
        )
        out.append(
            f"<div><small>Viewer questions</small><div class='metric'>{int(comments.get('question_count', 0) or 0)}</div></div>"
        )
        out.append("</section>")
        for label, key in (
            ("Requested animals", "requested_animals"),
            ("Comment keywords", "topic_keywords"),
        ):
            values = comments.get(key) or []
            if values:
                out.append(f"<p><strong>{label}:</strong> {html.escape(', '.join(map(str, values[:12])))}</p>")
        prompts = comments.get("content_prompts") or []
        if prompts:
            out.append("<h3>Viewer-led prompts</h3><ul>")
            for prompt in prompts[:5]:
                out.append(f"<li>{html.escape(str(prompt))}</li>")
            out.append("</ul>")
        out.append("</div>")

    if top_performers:
        out.append("<div class='card'><h2>Top performers (last 14 d)</h2>")
        out.append(
            "<table><tr><th>Title</th><th>Format</th><th>Views</th><th>Velocity</th><th>Growth</th><th>Humanity</th><th>Retention</th></tr>"
        )
        for t in top_performers[:10]:
            url = t.get("share_url") or (f"https://www.youtube.com/shorts/{t.get('video_id', '')}")
            out.append(
                f"<tr><td><a href='{html.escape(url)}'>"
                f"{html.escape(_display_title(t)[:90])}</a></td>"
                f"<td>{html.escape(str(t.get('story_format', '')))}</td>"
                f"<td>{int(t.get('views', 0)):,}</td>"
                f"<td>{float(t.get('views_per_hour', 0) or 0):.1f}/h</td>"
                f"<td>{float(t.get('growth_score', 0) or 0):.1f}</td>"
                f"<td>{float(t.get('humanity_score', 0) or 0):.0f} "
                f"<span class='badge'>{html.escape(str(t.get('humanity_label', '')))}</span></td>"
                f"<td>{t.get('view_pct', t.get('average_view_percentage', 0))} %</td></tr>"
            )
        out.append("</table></div>")

    if humanity_counts:
        out.append("<div class='card'><h2>Humanity mix</h2>")
        out.append("<table><tr><th>Label</th><th>Shorts</th></tr>")
        for label, count in sorted(humanity_counts.items(), key=lambda kv: str(kv[0])):
            out.append(
                f"<tr><td><span class='badge'>{html.escape(str(label))}</span></td>" f"<td>{int(count)}</td></tr>"
            )
        out.append("</table></div>")

    # ── Category retention ────────────────────────────────────
    if cat_perf:
        out.append("<div class='card'><h2>Retention by category</h2>")
        out.append("<table><tr><th>Category</th><th>Avg view %</th></tr>")
        for cat, pct in sorted(cat_perf.items(), key=lambda kv: kv[1], reverse=True):
            cls = "green" if pct >= 60 else ("red" if pct < 30 else "")
            out.append(f"<tr><td>{html.escape(str(cat))}</td>" f"<td class='{cls}'>{pct} %</td></tr>")
        out.append("</table></div>")

    if cat_engagement:
        out.append("<div class='card'><h2>Public engagement by category</h2>")
        out.append("<table><tr><th>Category</th><th>Score</th></tr>")
        for cat, score in sorted(cat_engagement.items(), key=lambda kv: kv[1], reverse=True):
            out.append(f"<tr><td>{html.escape(str(cat))}</td><td>{score}</td></tr>")
        out.append("</table></div>")

    if cat_growth:
        out.append("<div class='card'><h2>Growth score by category</h2>")
        out.append("<table><tr><th>Category</th><th>Score</th></tr>")
        for cat, score in sorted(cat_growth.items(), key=lambda kv: kv[1], reverse=True):
            out.append(f"<tr><td>{html.escape(str(cat))}</td><td>{score}</td></tr>")
        out.append("</table></div>")

    if format_growth:
        out.append("<div class='card'><h2>Growth score by story format</h2>")
        out.append("<table><tr><th>Format</th><th>Score</th></tr>")
        for fmt, score in sorted(format_growth.items(), key=lambda kv: kv[1], reverse=True):
            out.append(f"<tr><td>{html.escape(str(fmt))}</td><td>{score}</td></tr>")
        out.append("</table></div>")

    if series_engagement:
        out.append("<div class='card'><h2>Editorial series performance</h2>")
        out.append("<table><tr><th>Series</th><th>Score</th></tr>")
        for series_name, score in sorted(series_engagement.items(), key=lambda kv: kv[1], reverse=True):
            out.append(f"<tr><td>{html.escape(str(series_name))}</td><td>{score}</td></tr>")
        out.append("</table></div>")

    # ── A/B winners ──────────────────────────────────────────
    winners = experiments.get("winners") or {}
    if winners:
        out.append("<div class='card'><h2>A/B experiment winners</h2>")
        out.append("<table><tr><th>Axis</th><th>Winner</th><th>Lift over runner-up</th></tr>")
        for axis, variant in winners.items():
            lift = (experiments.get("lift") or {}).get(axis, {}).get("lift")
            lift_s = f"+{lift:.1f} pp" if isinstance(lift, (int, float)) else "—"
            out.append(
                f"<tr><td>{html.escape(axis)}</td>"
                f"<td><code>{html.escape(variant)}</code></td>"
                f"<td class='green'>{lift_s}</td></tr>"
            )
        out.append("</table></div>")

    # Show ALL axis stats too (warm-up phase visibility).
    axis_stats = experiments.get("axis_stats") or {}
    if axis_stats:
        out.append("<div class='card'><h3>Experiment data so far</h3>")
        for axis, by_variant in axis_stats.items():
            out.append(f"<h4>{html.escape(axis)}</h4>")
            out.append("<table><tr><th>Variant</th><th>Samples</th><th>Mean</th></tr>")
            for variant, stats in by_variant.items():
                out.append(
                    f"<tr><td><code>{html.escape(variant)}</code></td>"
                    f"<td>{stats.get('n', 0)}</td>"
                    f"<td>{stats.get('mean', 0)}</td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    # ── Audience cohort timing ───────────────────────────────
    slots = cohort.get("recommended_utc_hours") or []
    if slots:
        out.append("<div class='card'><h2>Recommended posting times</h2>")
        out.append("<small>One slot per top audience cohort, evening peak in their local time.</small>")
        out.append("<table><tr><th>Country</th><th>Views</th><th>Local offset</th><th>Post at</th></tr>")
        for s in slots:
            out.append(
                f"<tr><td>{html.escape(s.get('country','?'))}</td>"
                f"<td>{int(s.get('views',0)):,}</td>"
                f"<td>UTC{int(s.get('local_offset_h',0)):+d}</td>"
                f"<td><strong>{int(s.get('utc_hour',0)):02d}:00 UTC</strong></td></tr>"
            )
        out.append("</table></div>")

    out.append(
        "<small>Generated by <code>scripts/build_dashboard.py</code>. " "Data: <code>_data/analytics/</code>.</small>"
    )
    out.append("</body></html>")
    return "".join(out)


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_html(), encoding="utf-8")
    if SECURITY_TXT.exists():
        destination = SITE_DIR / SECURITY_TXT
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SECURITY_TXT, destination)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
