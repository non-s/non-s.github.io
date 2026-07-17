#!/usr/bin/env python3
"""scripts/build_dashboard.py — Generate a small static channel status page.

Reads `_data/analytics/latest.json` (channel-level snapshot) and
`_data/analytics/studio_reach_latest.json` (optional manual Shorts Reach
CSV import, see studio-reach-import.yml) plus the `.done` upload markers
in `_videos/`, and writes a single self-contained HTML page to
`_site/index.html` (and mirrored to root `index.html`, since this repo
serves legacy GitHub Pages from the `main` branch root).

Zero external JS/CSS deps so a CDN outage can't blank the page.
"""

from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.studio_reach_schema import summarize_reach  # noqa: E402

ANALYTICS_DIR = Path("_data/analytics")
VIDEOS_DIR = Path("_videos")
SITE_DIR = Path("_site")
OUT = SITE_DIR / "index.html"
ROOT_OUT = Path("index.html")
SECURITY_TXT = Path(".well-known/security.txt")
PUBLIC_SITE_FILES = (
    Path("404.html"),
    Path("robots.txt"),
    Path("sitemap.xml"),
    Path("privacy.html"),
    Path("terms.html"),
    SECURITY_TXT,
)
RECENT_SHORTS_LIMIT = 20


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _recent_shorts(limit: int = RECENT_SHORTS_LIMIT) -> list[dict]:
    markers = []
    for path in VIDEOS_DIR.glob("*.done"):
        data = _safe_json(path)
        if data.get("video_id"):
            markers.append(data)
    markers.sort(key=lambda item: str(item.get("uploaded_at") or ""), reverse=True)
    return markers[:limit]


def _stat_tile(label: str, value: str) -> str:
    return f"<div class='tile'><div class='tile-value'>{html.escape(value)}</div><div class='tile-label'>{html.escape(label)}</div></div>"


def render_html() -> str:
    latest = _safe_json(ANALYTICS_DIR / "latest.json")
    reach = _safe_json(ANALYTICS_DIR / "studio_reach_latest.json")
    reach_summary = summarize_reach(reach.get("items") or [])
    all_shorts = sorted(
        (m for m in (_safe_json(p) for p in VIDEOS_DIR.glob("*.done")) if m.get("video_id")),
        key=lambda item: str(item.get("uploaded_at") or ""),
        reverse=True,
    )
    recent_shorts = all_shorts[:RECENT_SHORTS_LIMIT]

    generated_at = latest.get("generated_at") or reach.get("generated_at") or ""
    total_views = latest.get("total_views") or reach_summary.get("views") or 0
    subscribers_gained = latest.get("subscribers_gained", 0)
    avg_view_pct = latest.get("avg_view_pct") or 0
    stayed_to_watch_rate = reach_summary.get("stayed_to_watch_rate") or 0

    out = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Amber Hours — channel status</title>",
        "<style>",
        "body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:900px;margin:2rem auto;"
        "padding:0 1rem;background:#0b0d12;color:#e6e9ef}",
        "h1{font-size:1.4rem} h2{font-size:1.1rem;margin-top:2rem}",
        ".tiles{display:flex;flex-wrap:wrap;gap:1rem;margin:1rem 0}",
        ".tile{background:#161a22;border-radius:10px;padding:1rem 1.25rem;min-width:140px}",
        ".tile-value{font-size:1.6rem;font-weight:600}",
        ".tile-label{font-size:.8rem;color:#9aa4b2;margin-top:.25rem}",
        "table{border-collapse:collapse;width:100%;margin-top:.5rem}",
        "th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #232833;font-size:.9rem}",
        "th{color:#9aa4b2;font-weight:500}",
        "a{color:#7dd3fc} small{color:#9aa4b2}",
        "</style></head><body>",
        "<h1>Amber Hours — lofi radio</h1>",
        "<small>24/7 lofi live stream + lofi Shorts, no narration. "
        f"Snapshot generated {html.escape(str(generated_at) or 'unknown')}.</small>",
        "<div class='tiles'>",
        _stat_tile("Total views", f"{int(total_views or 0):,}"),
        _stat_tile("Subscribers gained", f"{int(subscribers_gained or 0):,}"),
        _stat_tile(
            "Avg view %" if avg_view_pct else "Stayed to watch",
            f"{float(avg_view_pct):.1f}%" if avg_view_pct else f"{stayed_to_watch_rate * 100:.1f}%",
        ),
        _stat_tile("Shorts published", f"{len(all_shorts):,}"),
        "</div>",
    ]

    if not latest and not reach.get("items"):
        out.append(
            "<p><small>No analytics snapshot yet. Run the "
            "<code>studio-reach-import.yml</code> workflow after exporting a "
            "YouTube Studio Shorts Reach CSV to populate real view/watch-time data.</small></p>"
        )

    out.append("<h2>Recent Shorts</h2>")
    if recent_shorts:
        out.append("<table><tr><th>Uploaded</th><th>Title</th><th>Link</th></tr>")
        for item in recent_shorts:
            title = html.escape(str(item.get("title") or "(untitled)"))
            uploaded_at = html.escape(str(item.get("uploaded_at") or ""))
            url = html.escape(str(item.get("url") or ""))
            link = f"<a href='{url}'>watch</a>" if url else ""
            out.append(f"<tr><td>{uploaded_at}</td><td>{title}</td><td>{link}</td></tr>")
        out.append("</table>")
    else:
        out.append("<p><small>No Shorts published yet.</small></p>")

    out.append(
        "<p><small>Generated by <code>scripts/build_dashboard.py</code>. "
        "Data: <code>_data/analytics/</code> and <code>_videos/*.done</code>.</small></p>"
    )
    out.append("</body></html>")
    return "".join(out)


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    body = render_html()
    OUT.write_text(body, encoding="utf-8")
    ROOT_OUT.write_text(body, encoding="utf-8")
    for source in PUBLIC_SITE_FILES:
        if not source.exists():
            continue
        destination = SITE_DIR / source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
