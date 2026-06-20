#!/usr/bin/env python3
"""Merge free external/manual signals into cached topic candidate files."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analytics_schema import build_trend_signal_row, write_jsonl_row  # noqa: E402
from utils.trend_bridge import build_topic_candidates, load_google_trends_snapshots, normalize_rss_items  # noqa: E402


def _fetch_rss(url: str, timeout: float = 6.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "WildBriefBot/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def harvest(root: Path = ROOT) -> dict:
    trends_dir = root / "_data" / "trends"
    manual_dir = trends_dir / "manual_import"
    trends_dir.mkdir(parents=True, exist_ok=True)
    rows = load_google_trends_snapshots(manual_dir)
    rss_urls = [url.strip() for url in os.environ.get("WILD_BRIEF_RSS_URLS", "").split(",") if url.strip()]
    failures = []
    for url in rss_urls[:6]:
        try:
            rows.extend(normalize_rss_items(url, _fetch_rss(url)))
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)[:160]})
    signals_path = trends_dir / "trend_signals.jsonl"
    signals_path.write_text("", encoding="utf-8")
    for row in rows:
        write_jsonl_row(
            signals_path,
            build_trend_signal_row(
                source=str(row.get("source") or "manual"),
                topic=str(row.get("topic") or ""),
                score=float(row.get("score") or 0),
                observed_at=str(row.get("observed_at") or datetime.now(timezone.utc).isoformat()),
                context={"url": row.get("url", ""), "notes": row.get("notes", [])},
            ),
        )
    candidates = build_topic_candidates(rows)
    (trends_dir / "topic_candidates.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "candidates": candidates[:50],
                "source_rows": len(rows),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"rows": len(rows), "candidates": len(candidates), "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    report = harvest(Path(args.root).resolve())
    print(f"free_signal_harvester: {report['rows']} signal rows, {report['candidates']} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
