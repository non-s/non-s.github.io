#!/usr/bin/env python3
"""Aggregate rendered opening-audit metadata for the dashboard."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial_guard import editorial_issues
from utils.local_rewriter import rescue_story


def _read_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def _title_payload(marker: dict) -> dict:
    title = str(marker.get("title") or "").strip()
    video_id = str(marker.get("video_id") or "").strip()
    issues = editorial_issues({"title": title, "seo_title": title}, include_script=False) if title else []
    if not issues:
        return {"title": title, "source_title": title, "title_issues": []}
    payload = {
        "title": f"{video_id or 'unknown-video'} (title needs repair: {', '.join(issues[:3])})",
        "source_title": title,
        "title_issues": issues,
    }
    rescued, applied = rescue_story({
        "title": title,
        "seo_title": title,
        "hook": title,
        "script": title,
        "thumbnail_text": str(marker.get("thumbnail_text") or ""),
        "category": str(marker.get("category") or ""),
        "source_url": str(marker.get("url") or marker.get("source_url") or ""),
    }, issues)
    candidate = str(rescued.get("seo_title") or rescued.get("title") or "").strip() if applied else ""
    if candidate and candidate.lower() != title.lower() and not editorial_issues({"title": candidate, "seo_title": candidate}, include_script=False):
        payload["suggested_titles"] = [candidate[:82]]
    return payload


def build_report(root: Path = Path(".")) -> dict:
    rows = []
    for path in sorted((root / "_videos").glob("*.done")) if (root / "_videos").exists() else []:
        marker = _read_json(path, {})
        audit = marker.get("opening_audit") or {}
        if not audit:
            continue
        title_payload = _title_payload(marker)
        rows.append(
            {
                "video_id": marker.get("video_id", ""),
                **title_payload,
                "score": audit.get("score", 0),
                "reasons": audit.get("reasons") or [],
                "approved": audit.get("approved", True),
            }
        )
    worst = sorted(rows, key=lambda row: float(row.get("score") or 0))[:10]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "approved": len([row for row in rows if row.get("approved") is not False]),
        "pass_rate": round(
            len([row for row in rows if row.get("approved") is not False]) / max(len(rows), 1),
            4,
        ),
        "average_score": round(sum(float(row.get("score") or 0) for row in rows) / max(len(rows), 1), 2) if rows else 0,
        "worst_openings": worst,
        "weak_openings": [row for row in worst if float(row.get("score") or 0) < 72 or row.get("approved") is False],
    }
    out = root / "_data" / "opening_audit_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    report = build_report(Path(args.root).resolve())
    print(f"opening audit report: {report['rows']} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
