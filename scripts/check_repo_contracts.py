#!/usr/bin/env python3
"""Validate repo contracts that commonly drift in automation-heavy runs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_schedule_sync import check_schedule_sync  # noqa: E402
from utils.feature_flags import docs_coverage  # noqa: E402

REQUIRED_FILES = (
    "scripts/import_studio_reach_export.py",
    "scripts/apply_topic_freshness.py",
    "scripts/opening_audit_report.py",
    "scripts/comment_to_short_pipeline.py",
    "scripts/compact_analytics.py",
    "scripts/seo_metadata_lint.py",
    "scripts/tts_healthcheck.py",
    "utils/studio_reach_schema.py",
    "utils/topic_freshness.py",
    "utils/first_frame_audit.py",
    "utils/session_graph.py",
    "utils/api_quota_budget.py",
    "utils/feature_flags.py",
)

WORKFLOW_TOKENS = {
    ".github/workflows/quality-gate.yml": (
        "check_repo_contracts.py",
        "tts_healthcheck.py",
        "seo_metadata_lint.py",
    ),
    ".github/workflows/youtube-bot.yml": (
        "quota_preflight.py youtube-bot",
        "comment_to_short_pipeline.py",
    ),
    ".github/workflows/fetch-content.yml": (
        "quota_preflight.py fetch-content",
        "apply_topic_freshness.py",
    ),
    ".github/workflows/dashboard.yml": (
        "compact_analytics.py",
        "opening_audit_report.py",
    ),
}


def check_repo_contracts(root: Path = ROOT) -> list[str]:
    errors = list(check_schedule_sync(root))
    for rel in REQUIRED_FILES:
        if not (root / rel).exists():
            errors.append(f"required file missing: {rel}")
    coverage = docs_coverage(root)
    for name in coverage.get("environment_doc_missing", []):
        errors.append(f"{name} is missing from docs/ENVIRONMENT.md")
    for name in coverage.get("env_example_missing", []):
        errors.append(f"{name} is missing from .env.example")
    for rel, tokens in WORKFLOW_TOKENS.items():
        text = (root / rel).read_text(encoding="utf-8") if (root / rel).exists() else ""
        for token in tokens:
            if token not in text:
                errors.append(f"{rel} is missing workflow token: {token}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    errors = check_repo_contracts(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"repo contract: {error}", file=sys.stderr)
        return 1
    print("repo contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
