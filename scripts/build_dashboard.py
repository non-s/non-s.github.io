#!/usr/bin/env python3
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
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial import rank_candidates
from utils.humanity_engine import polish_story

ANALYTICS_DIR = Path("_data/analytics")
SITE_DIR      = Path("_site")
OUT           = SITE_DIR / "index.html"
QUEUE_FILE    = Path("_data/stories_queue.json")


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


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _queue_studio_snapshot(path: Path = QUEUE_FILE) -> dict:
    data = _safe_json(path)
    stories = [
        item for item in (data.get("stories") or [])
        if isinstance(item, dict) and not item.get("consumed")
    ]
    if not stories:
        return {"pending": 0, "approved": 0, "labels": {}, "top": []}
    polished_stories = [polish_story(item) for item in stories]
    ranked = rank_candidates(polished_stories)
    labels: Counter[str] = Counter()
    approved = 0
    rescued = 0
    top: list[dict] = []
    for item in ranked:
        editorial = item.get("editorial") or {}
        humanity = editorial.get("humanity") or {}
        studio_polish = item.get("studio_polish") or {}
        if studio_polish.get("applied"):
            rescued += 1
        label = str(humanity.get("label") or "unknown")
        labels[label] += 1
        if editorial.get("approved"):
            approved += 1
        if len(top) < 8 and editorial.get("approved"):
            top.append({
                "title": item.get("seo_title") or item.get("title") or "",
                "category": item.get("category") or "",
                "editorial_score": editorial.get("score", 0),
                "humanity_score": humanity.get("score", 0),
                "humanity_label": label,
            })
    return {
        "pending": len(stories),
        "approved": approved,
        "rescued": rescued,
        "labels": dict(sorted(labels.items())),
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


def _sparkline_svg(values: list[float], width: int = 600, height: int = 80,
                    stroke: str = "#0ea5e9") -> str:
    """Minimal inline SVG sparkline. Zero JS, no external assets."""
    if not values:
        return ""
    vmin, vmax = min(values), max(values)
    rng = max(0.001, vmax - vmin)
    step = width / max(1, len(values) - 1)
    points = " ".join(
        f"{i * step:.1f},{height - (v - vmin) / rng * (height - 10) - 5:.1f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
        f'<polyline fill="none" stroke="{stroke}" stroke-width="2" points="{points}" />'
        f'</svg>'
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
    rows = _read_csvs()
    latest = _safe_json(ANALYTICS_DIR / "latest.json")
    experiments = _safe_json(ANALYTICS_DIR / "experiments.json")
    cohort = _safe_json(ANALYTICS_DIR / "cohort_timing.json")
    days, views_series, view_pct_series = _series_by_day(rows)

    total_views_14d = latest.get("total_views_14d", 0)
    total_views      = latest.get("total_views", total_views_14d)
    avg_view_pct    = latest.get("avg_view_pct", latest.get("avg_view_percentage", 0))
    avg_engagement  = latest.get("avg_engagement_score", 0)
    avg_humanity    = latest.get("avg_humanity_score", 0)
    humanity_counts = latest.get("humanity_label_counts") or {}
    pulled_at       = latest.get("pulled_at", "—")
    underperformers = latest.get("below_60_pct") or []
    cat_perf        = latest.get("category_avg_view_pct") or {}
    cat_engagement  = latest.get("category_avg_engagement") or {}
    cat_growth      = latest.get("category_avg_growth_score") or {}
    format_growth   = latest.get("format_avg_growth_score") or {}
    series_engagement = latest.get("series_avg_engagement") or {}
    top_performers  = latest.get("top_performers") or []
    recommendations = latest.get("production_recommendations") or {}
    queue_studio = _queue_studio_snapshot()

    out: list[str] = []
    out.append(f"<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    out.append(f"<meta name='viewport' content='width=device-width,initial-scale=1'>")
    out.append(f"<title>Wild Brief — channel dashboard</title>")
    out.append(f"<style>{CSS}</style></head><body>")

    out.append("<h1>Wild Brief — channel dashboard</h1>")
    out.append(f"<small>Generated {html.escape(datetime.utcnow().isoformat())} UTC · "
                f"last analytics snapshot {html.escape(str(pulled_at))}</small>")

    # ── Top-line metrics ───────────────────────────────────────
    out.append("<section class='row'>")
    out.append(
        f"<div class='card'><small>Total tracked views</small>"
        f"<div class='metric'>{int(total_views):,}</div></div>"
    )
    out.append(
        f"<div class='card'><small>Public engagement score</small>"
        f"<div class='metric'>{avg_engagement}</div></div>"
    )
    out.append(
        f"<div class='card'><small>Avg view %</small>"
        f"<div class='metric'>{avg_view_pct}</div></div>"
    )
    out.append(
        f"<div class='card'><small>Avg humanity score</small>"
        f"<div class='metric'>{avg_humanity}</div></div>"
    )
    out.append(
        f"<div class='card'><small>Shorts under 60 % retention</small>"
        f"<div class='metric'>{len(underperformers)}</div></div>"
    )
    out.append("</section>")

    # ── Sparklines ─────────────────────────────────────────────
    if days:
        out.append("<div class='card'>")
        out.append(f"<h3>Daily views <small>({days[0]} → {days[-1]})</small></h3>")
        out.append(_sparkline_svg(views_series, stroke="#0ea5e9"))
        out.append(f"<h3>Avg view % per day</h3>")
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

    if queue_studio.get("pending"):
        out.append("<div class='card'><h2>Studio queue health</h2>")
        out.append("<section class='row'>")
        out.append(f"<div><small>Pending stories</small><div class='metric'>{int(queue_studio.get('pending', 0))}</div></div>")
        out.append(f"<div><small>Editor-approved</small><div class='metric'>{int(queue_studio.get('approved', 0))}</div></div>")
        out.append(f"<div><small>Studio-polished</small><div class='metric'>{int(queue_studio.get('rescued', 0))}</div></div>")
        out.append("</section>")
        labels = queue_studio.get("labels") or {}
        if labels:
            out.append("<h3>Humanity labels in queue</h3><table><tr><th>Label</th><th>Stories</th></tr>")
            for label, count in labels.items():
                out.append(f"<tr><td><span class='badge'>{html.escape(str(label))}</span></td><td>{int(count)}</td></tr>")
            out.append("</table>")
        top_queue = queue_studio.get("top") or []
        if top_queue:
            out.append("<h3>Next best candidates</h3><table><tr><th>Title</th><th>Category</th><th>Editorial</th><th>Humanity</th></tr>")
            for item in top_queue:
                out.append(
                    f"<tr><td>{html.escape(str(item.get('title', ''))[:100])}</td>"
                    f"<td>{html.escape(str(item.get('category', '')))}</td>"
                    f"<td>{int(item.get('editorial_score', 0) or 0)}</td>"
                    f"<td>{int(item.get('humanity_score', 0) or 0)} "
                    f"<span class='badge'>{html.escape(str(item.get('humanity_label', '')))}</span></td></tr>"
                )
            out.append("</table>")
        out.append("</div>")

    if top_performers:
        out.append("<div class='card'><h2>Top performers (last 14 d)</h2>")
        out.append("<table><tr><th>Title</th><th>Format</th><th>Views</th><th>Velocity</th><th>Growth</th><th>Humanity</th><th>Retention</th></tr>")
        for t in top_performers[:10]:
            url = t.get("share_url") or (
                f"https://www.youtube.com/shorts/{t.get('video_id', '')}"
            )
            out.append(
                f"<tr><td><a href='{html.escape(url)}'>"
                f"{html.escape(t.get('title', '')[:90])}</a></td>"
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
            out.append(f"<tr><td><span class='badge'>{html.escape(str(label))}</span></td>"
                       f"<td>{int(count)}</td></tr>")
        out.append("</table></div>")

    # ── Category retention ────────────────────────────────────
    if cat_perf:
        out.append("<div class='card'><h2>Retention by category</h2>")
        out.append("<table><tr><th>Category</th><th>Avg view %</th></tr>")
        for cat, pct in sorted(cat_perf.items(), key=lambda kv: kv[1], reverse=True):
            cls = "green" if pct >= 60 else ("red" if pct < 30 else "")
            out.append(f"<tr><td>{html.escape(str(cat))}</td>"
                        f"<td class='{cls}'>{pct} %</td></tr>")
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
            out.append(f"<tr><td>{html.escape(axis)}</td>"
                        f"<td><code>{html.escape(variant)}</code></td>"
                        f"<td class='green'>{lift_s}</td></tr>")
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

    out.append("<small>Generated by <code>scripts/build_dashboard.py</code>. "
                "Data: <code>_data/analytics/</code>.</small>")
    out.append("</body></html>")
    return "".join(out)


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_html(), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
