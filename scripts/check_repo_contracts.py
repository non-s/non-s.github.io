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
    "scripts/import_studio_reach_export.py",
    "scripts/apply_topic_freshness.py",
    "scripts/opening_audit_report.py",
    "scripts/comment_to_short_pipeline.py",
    "scripts/compact_analytics.py",
    "scripts/seo_metadata_lint.py",
    "scripts/audit_slot_contracts.py",
    "scripts/fact_guard.py",
    "scripts/build_originality_pack.py",
    "scripts/experiment_governance.py",
    "scripts/reconcile_retention.py",
    "scripts/session_graph_actioner.py",
    "scripts/build_crosspost_pack.py",
    "scripts/render_bench.py",
    "scripts/music_bed_report.py",
    "scripts/security_manifest.py",
    "scripts/media_lifecycle.py",
    "scripts/merge_jsonl_state.py",
    "scripts/reconcile_queue_uploads.py",
    "scripts/doctor.py",
    "scripts/upload_intent.py",
    "scripts/tts_healthcheck.py",
    "utils/studio_reach_schema.py",
    "utils/topic_freshness.py",
    "utils/first_frame_audit.py",
    "utils/session_graph.py",
    "utils/api_quota_budget.py",
    "utils/feature_flags.py",
    "utils/time_semantics.py",
    "utils/opening_gate_v2.py",
    "utils/story_patterns.py",
    "utils/hook_library.py",
    "utils/payoff_controller.py",
    "utils/loop_semantics.py",
    "utils/claim_risk.py",
    "utils/rights_guard.py",
    "utils/originality_pack.py",
    "utils/experiment_registry.py",
    "utils/experiment_scheduler.py",
    "utils/retention_warehouse.py",
    "utils/frame_zero_packaging.py",
    "utils/search_enrichment.py",
    "utils/cohort_memory.py",
    "utils/comment_policy.py",
    "utils/voice_registry.py",
    "utils/music_bed.py",
    "utils/media_lifecycle.py",
    "utils/render_qa.py",
)

WORKFLOW_TOKENS = {
    ".github/workflows/quality-gate.yml": (
        "check_repo_contracts.py",
        "audit_slot_contracts.py",
        "media_lifecycle.py --audit-tracked",
        "tts_healthcheck.py",
        "seo_metadata_lint.py",
    ),
    ".github/workflows/youtube-bot.yml": (
        "quota_preflight.py youtube-bot",
        "comment_to_short_pipeline.py",
        "media_lifecycle.py --cleanup --audit-tracked",
        "merge_jsonl_state.py",
        "reconcile_queue_uploads.py",
        "scripts/queue_ready_count.py --refresh --field publish_ready",
        "scripts/queue_ready_count.py --field pending",
        'target="${QUEUE_TARGET_PUBLISH_READY:-2}"',
        "PUBLISH_BACKFILL_READY_TARGET || '2'",
        'BROLL_SOURCE_MODE: "pexels"',
        "PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY || secrets.PEXELS }}",
        "QUEUE_TARGET_PENDING: ${{ vars.PUBLISH_BACKFILL_QUEUE_TARGET || '18' }}",
        "QUEUE_BACKFILL_PENDING_BATCH: ${{ vars.PUBLISH_BACKFILL_PENDING_BATCH || '6' }}",
        "QUEUE_BACKFILL_TIMEOUT_SECONDS: ${{ vars.PUBLISH_BACKFILL_TIMEOUT_SECONDS || '540' }}",
        "PEXELS_SEARCH_PER_PAGE: ${{ vars.PEXELS_SEARCH_PER_PAGE || '32' }}",
        "PEXELS_DISCOVERY_PAGES: ${{ vars.PEXELS_DISCOVERY_PAGES || '2' }}",
        "PEXELS_BACKFILL_QUERY_TAKE: ${{ vars.PEXELS_BACKFILL_QUERY_TAKE || '6' }}",
        "PEXELS_TOPIC_CALL_BUDGET: ${{ vars.PEXELS_TOPIC_CALL_BUDGET || '2' }}",
        "PEXELS_DEEP_SEARCH_GAP: ${{ vars.PEXELS_DEEP_SEARCH_GAP || '8' }}",
        'while [ "${ready}" -lt "${target}" ]',
        "Publish-ready inventory is enough; raw pending inventory is monitored by fetch-content.",
        "fetch-content owns deeper replenishment",
        'timeout "${backfill_timeout}s" python fetch_animals.py',
        "base_pending_target + (attempt - 1) * pending_batch",
        "upload_intents.jsonl",
    ),
    ".github/workflows/fetch-content.yml": (
        'cron: "9,23 * * * *"',
        "quota_preflight.py fetch-content",
        "apply_topic_freshness.py",
        "FETCH_REFRESH_TIMEOUT_SECONDS || '720'",
        "Pexels refresh timed out; leaving generated diagnostics uncommitted",
        "QUEUE_TARGET_PENDING || '72'",
        "PEXELS_SEARCH_PER_PAGE: ${{ vars.PEXELS_SEARCH_PER_PAGE || '32' }}",
        "PEXELS_DISCOVERY_PAGES: ${{ vars.PEXELS_DISCOVERY_PAGES || '2' }}",
        "PEXELS_BACKFILL_QUERY_TAKE: ${{ vars.PEXELS_BACKFILL_QUERY_TAKE || '6' }}",
        "PEXELS_TOPIC_CALL_BUDGET: ${{ vars.PEXELS_TOPIC_CALL_BUDGET || '2' }}",
        "PEXELS_DEEP_SEARCH_GAP: ${{ vars.PEXELS_DEEP_SEARCH_GAP || '8' }}",
        "merge_jsonl_state.py",
        "reconcile_queue_uploads.py",
    ),
    ".github/workflows/youtube-watchdog.yml": (
        'PUBLISH_SLOT_WINDOW_MINUTES: "60"',
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
    ".github/workflows/dashboard.yml": (
        "compact_analytics.py",
        "opening_audit_report.py",
        "experiment_governance.py",
        "fact_guard.py",
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
