#!/usr/bin/env python3
"""Run repeated Wild Brief intelligence/reporting scripts from one entrypoint."""
from __future__ import annotations

import argparse
import subprocess
import sys


SCRIPT_SETS = {
    "pre_generate": [
        "scripts/ops_guardian.py",
        "scripts/trend_radar.py",
        "scripts/category_recovery.py",
        "scripts/category_recovery_rewriter.py",
        "scripts/winner_sequel_factory.py",
        "scripts/fact_ledger.py",
        "scripts/autonomous_director.py",
        "scripts/ai_provider_report.py",
        "scripts/packaging_report.py",
        "scripts/format_memory.py",
        "scripts/youtube_brain_report.py",
        "scripts/post24_review.py",
        "scripts/sequence_plan.py",
        "scripts/publish_schedule.py",
        "scripts/autonomous_growth_loop.py",
        "scripts/channel_success.py",
        "scripts/success_rewriter.py",
        "scripts/agency_gate_report.py",
        "scripts/prune_queue.py",
    ],
    "post_publish": [
        "scripts/analyze_channel.py",
        "scripts/analyze_comments.py",
        "scripts/youtube_intelligence.py",
        "scripts/trend_radar.py",
        "scripts/audit_automation.py",
        "scripts/ops_guardian.py",
        "scripts/remake_engine.py",
        "scripts/winner_sequel_factory.py",
        "scripts/category_recovery.py",
        "scripts/category_recovery_rewriter.py",
        "scripts/fact_ledger.py",
        "scripts/autonomous_director.py",
        "scripts/ai_provider_report.py",
        "scripts/packaging_report.py",
        "scripts/format_memory.py",
        "scripts/youtube_brain_report.py",
        "scripts/post24_review.py",
        "scripts/sequence_plan.py",
        "scripts/publish_schedule.py",
        "scripts/autonomous_growth_loop.py",
        "scripts/channel_success.py",
        "scripts/success_rewriter.py",
        "scripts/agency_gate_report.py",
        "scripts/backfill_done_markers.py",
        "scripts/weekly_report.py",
    ],
    "queue": [
        "scripts/audit_automation.py",
        "scripts/youtube_intelligence.py",
        "scripts/ops_guardian.py",
        "scripts/remake_engine.py",
        "scripts/winner_sequel_factory.py",
        "scripts/category_recovery.py",
        "scripts/category_recovery_rewriter.py",
        "scripts/fact_ledger.py",
        "scripts/autonomous_director.py",
        "scripts/ai_provider_report.py",
        "scripts/packaging_report.py",
        "scripts/format_memory.py",
        "scripts/youtube_brain_report.py",
        "scripts/post24_review.py",
        "scripts/sequence_plan.py",
        "scripts/publish_schedule.py",
        "scripts/autonomous_growth_loop.py",
        "scripts/channel_success.py",
        "scripts/success_rewriter.py",
        "scripts/agency_gate_report.py",
        "scripts/prune_queue.py",
        "scripts/weekly_report.py",
    ],
    "dashboard": [
        "scripts/audit_automation.py",
        "scripts/youtube_intelligence.py",
        "scripts/trend_radar.py",
        "scripts/ops_guardian.py",
        "scripts/remake_engine.py",
        "scripts/remake_factory.py",
        "scripts/winner_sequel_factory.py",
        "scripts/backfill_legacy_analytics.py",
        "scripts/visual_qa_report.py",
        "scripts/visual_qa_backfill.py",
        "scripts/narrator_report.py",
        "scripts/agency_plan.py",
        "scripts/autonomous_director.py",
        "scripts/channel_success.py",
        "scripts/success_rewriter.py",
        "scripts/fact_ledger.py",
        "scripts/retention_rewrite_queue.py",
        "scripts/retention_rewriter.py",
        "scripts/category_recovery.py",
        "scripts/category_recovery_rewriter.py",
        "scripts/agency_gate_report.py",
        "scripts/ai_provider_report.py",
        "scripts/packaging_report.py",
        "scripts/format_memory.py",
        "scripts/youtube_brain_report.py",
        "scripts/post24_review.py",
        "scripts/sequence_plan.py",
        "scripts/publish_schedule.py",
        "scripts/autonomous_growth_loop.py",
        "scripts/daily_brief.py",
        "scripts/backfill_done_markers.py",
        "scripts/weekly_report.py",
    ],
}

OPTIONAL = {
    "scripts/youtube_intelligence.py",
    "scripts/analyze_channel.py",
    "scripts/analyze_comments.py",
    "scripts/trend_radar.py",
    "scripts/ai_provider_report.py",
}


def run_script(script: str, *, strict: bool) -> int:
    result = subprocess.run([sys.executable, script])
    if result.returncode and strict and script not in OPTIONAL:
        return result.returncode
    if result.returncode:
        print(f"warning: {script} exited {result.returncode}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=sorted(SCRIPT_SETS))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    for script in SCRIPT_SETS[args.mode]:
        code = run_script(script, strict=args.strict)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
