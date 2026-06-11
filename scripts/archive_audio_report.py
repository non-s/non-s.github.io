#!/usr/bin/env python3
"""Discover public-domain Internet Archive audio candidates for Shorts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.internet_archive import discover_public_domain_audio  # noqa: E402

DEFAULT_QUERIES = {
    "upbeat": "collection:audio_music AND (ambient OR background OR nature OR instrumental)",
    "reflective": "collection:audio_music AND (nature OR forest OR birds OR ocean OR ambient OR instrumental)",
    "tense": "collection:audio_music AND (suspense OR drone OR ambient OR nature OR instrumental)",
}


def build_report(rows: int) -> dict:
    candidates = []
    for mood, query in DEFAULT_QUERIES.items():
        for asset in discover_public_domain_audio(query, mood=mood, rows=rows):
            candidates.append(asset.to_manifest_row())
    return {
        "source": "Internet Archive",
        "license_policy": "public-domain-or-cc0-only",
        "queries": DEFAULT_QUERIES,
        "candidate_count": len(candidates),
        "tracks": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default="_data/archive_audio_candidates.json")
    args = parser.parse_args()

    report = build_report(args.rows)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    if not args.json:
        print(f"archive audio candidates: {report['candidate_count']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
