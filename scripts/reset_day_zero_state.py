#!/usr/bin/env python3
"""Reset Wild Brief's local publishing state for a Pexels day-zero restart."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPOCH = os.environ.get("CHANNEL_EPOCH") or f"channel_reset_{datetime.now(timezone.utc).date().isoformat()}"
SELECTION_RULE = "autonomy_priority with retention lift, then queue_score and publish_score"


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
        "_videos/shorts_done_es.json",
        "_videos_pt-BR/*.done",
        "_videos_pt-BR/*.roundup",
        "_videos_pt-BR/shorts_done.json",
        "_videos_es-MX/*.done",
        "_videos_es-MX/*.roundup",
        "_videos_es-MX/shorts_done.json",
        "_videos_es-ES/*.done",
        "_videos_es-ES/*.roundup",
        "_videos_es-ES/shorts_done.json",
        "_data/published_thumbnails/*.jpg",
        "docs/published_packaging_repair_*.md",
        "_data/reports/weekly*.md",
        "_data/analytics/partitions/**/*.jsonl",
    )
    delete_targets: list[Path] = []
    for pattern in delete_patterns:
        delete_targets.extend(root.glob(pattern))

    selection_rule = SELECTION_RULE
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
            "publish_ready_target": 24,
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
        "_data/ai_provider_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "default_chain": [],
            "json_chain": [],
            "rewrite_chain": [],
            "longform_chain": [],
            "providers": [],
        },
        "_data/category_recovery.json": {"generated_at": stamp, "channel_epoch": EPOCH, "plans": []},
        "_data/category_recovery_rewriter.json": {"generated_at": stamp, "channel_epoch": EPOCH, "rewritten": []},
        "_data/comment_idea_clusters.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "clusters": [],
        },
        "_data/comment_replies.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "replied_comment_ids": [],
            "replies": [],
        },
        "_data/control_plane_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "state": "channel_reset",
            "pressure_score": 0,
            "metrics": {},
            "largest_state_files": [],
            "migration_lanes": [],
            "commands": [],
        },
        "_data/data_quality_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "status": "channel_reset",
            "metrics": {},
            "issues": [],
        },
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
        "_data/analytics/api_quota_latest.json": {
            "timestamp_utc": stamp,
            "channel_epoch": EPOCH,
            "quota_day_pt": "",
            "workflow": "channel_reset",
            "calls": {},
            "estimated_daily_calls": {},
            "estimated_units": 0,
            "guard": {
                "enabled": True,
                "mode": "block",
                "block": False,
                "spent_today": 0,
                "projected_today": 0,
                "projected_ratio": 0,
                "reason": "channel_reset",
            },
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
        "_data/experiments_recommendations.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "experiments": {},
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
        "_data/frame_zero_preflight.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "floor": 82.0,
            "pending": 0,
            "ready": 0,
            "held": 0,
            "rewritten": 0,
            "average_opening_score": 0,
            "render_gate": "channel_reset",
            "counts": {},
            "items": [],
        },
        "_data/legacy_copy_sanitize_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/level_system.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "mode": "free_resources_only",
            "status": "channel_reset",
            "overall_progress_pct": 0,
            "current_level": {
                "number": 1,
                "name": "Clean restart",
                "mission": "Rebuild the channel from an empty public inventory.",
                "status": "current",
                "progress_pct": 0,
            },
            "boss": {},
            "next_upgrade": {},
            "action_plan": [],
            "metrics": {"published_count": 0, "views_28d": 0, "comments_sampled": 0},
            "top_blockers": [],
        },
        "_data/media_lifecycle_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
            "deleted": [],
        },
        "_data/narrator_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
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
            "rollout_state": "disabled",
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
            "fresh_upload_watchlist": {
                "generated_at": stamp,
                "items": [],
                "counts": {"tracked": 0},
            },
            "fresh_upload_actions": {
                "generated_at": stamp,
                "source": "fresh_upload_watchlist",
                "free_only": True,
                "items": [],
                "counts": {"total": 0, "urgent": 0, "high": 0, "manual_review": 0, "automation_safe": 0},
            },
            "related_video_recommendations": [],
            "sequel_opportunities": [],
        },
        "_data/fresh_upload_watchlist.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
            "counts": {"tracked": 0},
        },
        "_data/fresh_upload_actions.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "source": "fresh_upload_watchlist",
            "free_only": True,
            "items": [],
            "counts": {"total": 0, "urgent": 0, "high": 0, "manual_review": 0, "automation_safe": 0},
        },
        "_data/queue_audit.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "pending": 0,
            "items": [],
            "mechanism_clusters": {},
        },
        "_data/queue_history_repair.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/queue_prune_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "before": 0,
            "after": 0,
            "removed": [],
        },
        "_data/related_video_recommendations.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/reject_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/render_bench.json": {
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
        "_data/security_manifest.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
            "issues": [],
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
        "_data/trend_radar.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "trends": [],
            "blocked": [],
        },
        "_data/trends/freshness_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "enabled": True,
            "pending": 0,
            "scored": 0,
            "coverage": 0,
            "average_freshness_score": 0,
            "stale": [],
            "top_fresh": [],
        },
        "_data/trends/topic_candidates.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
        "_data/underpowered_tests.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "active_axes": [],
            "underpowered_tests": [],
            "recommended_next_axes": [],
            "low_volume": True,
        },
        "_data/visual_qa_backfill.json": {"generated_at": stamp, "channel_epoch": EPOCH, "items": []},
        "_data/visual_quality_report.json": {
            "generated_at": stamp,
            "channel_epoch": EPOCH,
            "items": [],
        },
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
        "_data/analytics/api_quota_ledger.jsonl",
        "_data/channel_memory.jsonl",
        "_data/repair_queue.jsonl",
        "_data/rejected_queue.jsonl",
        "_data/source_provenance.jsonl",
        "_data/fact_sources.jsonl",
        "_data/ai_cache.jsonl",
        "_data/provider_stats.jsonl",
        "_data/quota_log.jsonl",
        "_data/trends/trend_signals.jsonl",
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
    parser.add_argument("--epoch", default="", help="Override the channel epoch label written into reset artifacts.")
    args = parser.parse_args()
    global EPOCH
    if args.epoch.strip():
        EPOCH = args.epoch.strip()
    print(json.dumps(reset_state(dry_run=args.dry_run), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
