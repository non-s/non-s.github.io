#!/usr/bin/env python3
"""Validate repo contracts that commonly drift in automation-heavy runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_slot_contracts import audit_slot_contracts  # noqa: E402
from scripts.check_schedule_sync import check_schedule_sync  # noqa: E402
from utils.feature_flags import docs_coverage  # noqa: E402

REQUIRED_FILES = (
    "404.html",
    "_config.yml",
    "robots.txt",
    "sitemap.xml",
    "scripts/import_studio_reach_export.py",
    "scripts/audit_slot_contracts.py",
    "scripts/security_manifest.py",
    "scripts/media_lifecycle.py",
    "scripts/merge_jsonl_state.py",
    "scripts/upload_intent.py",
    "scripts/production_smoke.py",
    ".well-known/security.txt",
    "utils/studio_reach_schema.py",
    "utils/api_quota_budget.py",
    "utils/feature_flags.py",
    "utils/time_semantics.py",
    "utils/retention_warehouse.py",
    "utils/media_lifecycle.py",
)

WORKFLOW_TOKENS = {
    ".github/workflows/quality-gate.yml": (
        "check_workflow_contracts.py",
        "check_repo_contracts.py",
        "audit_slot_contracts.py",
        "media_lifecycle.py --audit-tracked",
        "quota_preflight.py youtube-bot",
    ),
    ".github/workflows/youtube-bot.yml": (
        "quota_preflight.py youtube-bot",
        "media_lifecycle.py --cleanup --audit-tracked",
        "merge_jsonl_state.py",
        "sync_jamendo_music.py",
        "generate_lofi_short.py",
        "python upload_youtube.py --language=en",
        "upload_intents.jsonl",
    ),
    ".github/workflows/youtube-watchdog.yml": (
        'PUBLISH_SLOT_WINDOW_MINUTES: "120"',
        "PUBLISH_SLOTS_UTC",
        "watchdog recovery for missed slot",
        "python scripts/youtube_slot_dispatch.py watchdog",
    ),
    ".github/workflows/youtube-hourly-heartbeat.yml": (
        'TARGET_WORKFLOW: "youtube-bot.yml"',
        "PUBLISH_HEARTBEAT_RECENT_RUN_TOLERANCE_MINUTES || '20'",
        'PUBLISH_SLOT_WINDOW_MINUTES: "60"',
        "heartbeat recovery for slot",
        "python scripts/youtube_slot_dispatch.py heartbeat",
        "timeout-minutes: 8",
    ),
    ".github/workflows/ops-alert.yml": (
        "YouTube Bot - Shorts only",
        "YouTube hourly heartbeat",
        "YouTube publishing watchdog",
        "Production quality gate",
        "Build + deploy dashboard",
        "CodeQL",
        "Security, SBOM and license audit",
        "Production smoke",
        "OPS_ALERTS_ENABLED",
        "issues: write",
        "gh issue create",
        "gh issue comment",
    ),
    ".github/workflows/dashboard.yml": (
        "import_studio_reach_export.py",
        "build_dashboard.py",
        "Persist refreshed analytics",
    ),
    ".github/workflows/production-smoke.yml": (
        "production_smoke.py --json",
        'cron: "17 */6 * * *"',
    ),
}


def check_repo_contracts(root: Path = ROOT) -> list[str]:
    errors = list(check_schedule_sync(root))
    errors.extend(audit_slot_contracts(root).get("errors", []))
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
