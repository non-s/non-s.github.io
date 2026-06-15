#!/usr/bin/env python3
"""Reset Wild Brief's local publishing state for a Pexels day-zero restart."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPOCH = "pexels_day_zero_2026-06-15"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def reset_state(root: Path = ROOT, *, dry_run: bool = False) -> dict:
    root = root.resolve()
    stamp = _now()
    deleted: list[str] = []
    written: list[str] = []

    delete_patterns = (
        "_videos/*.done",
        "_videos/*.roundup",
        "_videos/shorts_done.json",
        "_videos_pt-BR/*.done",
        "_videos_pt-BR/*.roundup",
        "_videos_pt-BR/shorts_done.json",
        "_data/published_thumbnails/*.jpg",
        "docs/published_packaging_repair_*.md",
        "_data/reports/weekly*.md",
        "_data/analytics/partitions/**/*.jsonl",
    )
    delete_targets: list[Path] = []
    for pattern in delete_patterns:
        delete_targets.extend(root.glob(pattern))

    selection_rule = "autonomy_priority first, queue_score and publish_score as tie-breakers"
    for path in sorted({target.resolve() for target in delete_targets}):
        if not path.is_file() or not path.is_relative_to(root):
            continue
        deleted.append(path.relative_to(root).as_posix())
        if not dry_run:
            path.unlink()

    json_payloads = {
        "_data/stories_queue.json": {
            "updated_at": stamp,
            "channel_epoch": EPOCH,
            "target_pending": 24,
            "stories": [],
        },
        "_data/published_clips.json": {"updated_at": stamp, "channel_epoch": EPOCH, "clips": []},
        "_data/published_thumbnails_manifest.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/published_packaging_repair.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/studio_title_update_log.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "updates": [],
        },
        "_data/remake_backlog.json": {"generated_at": stamp, "channel_epoch": EPOCH, "remakes": []},
        "_data/remake_factory.json": {"generated_at": stamp, "channel_epoch": EPOCH, "candidates": []},
        "_data/retention_rewrite_queue.json": {"generated_at": stamp, "channel_epoch": EPOCH, "items": []},
        "_data/retention_rewriter.json": {"generated_at": stamp, "channel_epoch": EPOCH, "items": []},
        "_data/channel_epoch.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "policy": "Local publish history, uploaded markers, pending queue inventory, and generated learning reports were reset after the old channel inventory was removed. Production video sourcing is Pexels-only.",
            "cadence": "hourly_active",
            "queue_target_pending": 24,
            "publish_ready_target": 6,
            "youtube_description_mode": "empty",
            "visual_source_strategy": "pexels_only",
        },
        "_data/agency_gate.json": {"generated_at": stamp, "channel_epoch": EPOCH, "approved": [], "held": []},
        "_data/agency_plan.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "status": "active",
            "publish_now_inventory": 0,
            "weekly_goal": "Restart the channel cleanly with Pexels-only visuals, strong animal-first thumbnails, and hourly publishing.",
            "blocked_trends": [],
            "days": [],
        },
        "_data/automation_health.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "state": "active",
            "score": 100,
            "issues": [],
        },
        "_data/autonomous_director.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "sequel_candidates": [],
        },
        "_data/autonomous_growth_plan.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "mode": "day_zero_pexels_restart",
            "pending": 0,
            "actions": [],
        },
        "_data/category_recovery.json": {"generated_at": stamp, "channel_epoch": EPOCH, "plans": []},
        "_data/category_recovery_rewriter.json": {"generated_at": stamp, "channel_epoch": EPOCH, "rewritten": []},
        "_data/analytics/comments.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "comments": [],
            "requested_animals": [],
        },
        "_data/analytics/compaction_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "partitions": [],
        },
        "_data/analytics/experiments.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "winners": {},
            "assignments": [],
        },
        "_data/analytics/extended_collection_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/analytics/latest.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "total_views": 0,
            "views_28d": 0,
            "subscribers_gained": 0,
            "shorts_tracked": 0,
            "avg_view_pct": 0,
            "production_recommendations": {},
            "top_public_videos": [],
            "remake_candidates": [],
        },
        "_data/analytics/legacy_backfill.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/analytics/reporting_bootstrap.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/analytics/reporting_pull.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/analytics/retention_reconciliation.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/analytics/studio_reach_latest.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/analytics/weekly_next_recommendations.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/analytics/weekly_summary.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/audience_memory.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "videos": [],
            "categories": {},
        },
        "_data/channel_success.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "state": "day_zero_pexels_restart",
            "first_24h": {"winners": [], "rework": []},
        },
        "_data/comment_reply_short_candidates.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "candidates": [],
        },
        "_data/comment_to_short_candidates.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "candidates": [],
        },
        "_data/crosspost_pack.json": {"generated_at": stamp, "channel_epoch": EPOCH, "items": []},
        "_data/daily_brief.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
            "actions": [],
        },
        "_data/dry_run_publish.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "selection_rule": selection_rule,
            "eligible_count": 0,
            "would_publish": [],
        },
        "_data/early_performance.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
            "accelerators": [],
            "risks": [],
        },
        "_data/early_warning.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "sequence_candidates": [],
            "remake_candidates": [],
        },
        "_data/fan_growth.json": {"generated_at": stamp, "channel_epoch": EPOCH, "ranked_videos": []},
        "_data/fact_ledger.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "duplicate_clusters": [],
        },
        "_data/fact_guard_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/format_memory.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "winning_title_patterns": {},
            "winning_hook_patterns": {},
        },
        "_data/next_session_actions.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
            "action_score_threshold": 55,
        },
        "_data/music_bed_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "music_bed_enabled": False,
            "archive_audio_enabled": False,
            "rollout_state": "disabled_for_pexels_only_restart",
            "source": "",
        },
        "_data/next_shorts.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "selection_rule": selection_rule,
            "items": [],
            "title_shape_mix": {"status": "clear", "rewrite_candidates": []},
        },
        "_data/opening_audit_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "worst_openings": [],
            "weak_openings": [],
        },
        "_data/ops_guardian.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "paused_topics": [],
            "executive_report": {"what_to_remake": [], "what_to_scale": []},
        },
        "_data/packaging_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "pending": 0,
            "items": [],
        },
        "_data/post24_review.json": {"generated_at": stamp, "channel_epoch": EPOCH, "items": []},
        "_data/post_upload_session_ops.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "related_video_recommendations": [],
            "sequel_opportunities": [],
        },
        "_data/queue_audit.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "pending": 0,
            "items": [],
            "mechanism_clusters": {},
        },
        "_data/related_video_recommendations.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/scale_blueprint.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "state": "day_zero_pexels_restart",
            "lanes": [],
        },
        "_data/seo_metadata_lint.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "pending_checked": 0,
            "uploaded_checked": 0,
            "items": [],
            "errors": [],
        },
        "_data/sequel_candidates.json": {"generated_at": stamp, "channel_epoch": EPOCH, "items": []},
        "_data/sequence_plan.json": {"generated_at": stamp, "channel_epoch": EPOCH, "variants": []},
        "_data/session_graph.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "nodes": [],
            "edges": [],
            "target_reuse_limit": 1,
        },
        "_data/session_graph_actions.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "actions": [],
            "action_score_threshold": 55,
        },
        "_data/success_rewriter.json": {"generated_at": stamp, "channel_epoch": EPOCH, "items": []},
        "_data/visual_qa_backfill.json": {"generated_at": stamp, "channel_epoch": EPOCH, "items": []},
        "_data/winner_patterns.json": {"generated_at": stamp, "channel_epoch": EPOCH, "patterns": []},
        "_data/winner_sequel_factory.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "candidates": [],
        },
        "_data/youtube_brain_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "pending": 0,
            "publish_ready_top": [],
            "risk_watchlist": [],
            "items": [],
        },
        "_data/youtube_intelligence.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "uploaded_video_inventory": [],
            "video_metadata_statistics": {},
            "video_audit": {"top_public_videos": []},
        },
    }
    for rel, payload in json_payloads.items():
        written.append(rel)
        if not dry_run:
            _write_json(root / rel, payload)

    jsonl_files = (
        "_data/upload_intents.jsonl",
        "_data/publish_slot_decisions.jsonl",
        "_data/analytics/retention_curve.jsonl",
        "_data/analytics/reporting_video_metrics.jsonl",
        "_data/analytics/segment_metrics.jsonl",
        "_data/analytics/studio_reach_daily.jsonl",
        "_data/analytics/traffic_source_daily.jsonl",
        "_data/analytics/variant_assignments.jsonl",
        "_data/analytics/video_core_daily.jsonl",
        "_data/analytics/video_metrics.jsonl",
        "_data/channel_memory.jsonl",
        "_data/repair_queue.jsonl",
        "_data/rejected_queue.jsonl",
        "_data/source_provenance.jsonl",
        "_data/fact_sources.jsonl",
        "_data/ai_cache.jsonl",
        "_data/provider_stats.jsonl",
    )
    for rel in jsonl_files:
        written.append(rel)
        if not dry_run:
            _write_text(root / rel)

    originality_seed = {
        "caption_manifest": {},
        "clip_hash": "",
        "complete": True,
        "render_manifest": {},
        "script_hash": "",
        "story_hash": "",
        "story_id": "ledger_initialized",
        "tts_manifest": {},
    }
    written.append("_data/originality_pack.jsonl")
    if not dry_run:
        _write_text(root / "_data/originality_pack.jsonl", json.dumps(originality_seed, sort_keys=True) + "\n")

    report = {
        "generated_at": stamp,
        "channel_epoch": EPOCH,
        "dry_run": dry_run,
        "deleted_count": len(deleted),
        "deleted_patterns": list(delete_patterns),
        "written": written,
    }
    if not dry_run:
        _write_json(root / "_data/day_zero_reset_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(reset_state(dry_run=args.dry_run), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
