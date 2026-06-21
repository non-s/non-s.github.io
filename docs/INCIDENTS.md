# Wild Brief Incidents

## Safe Rollback Flags

- Publishing drift: `ADAPTIVE_CADENCE_ENABLED=0`
- Weak freshness data: `TOPIC_FRESHNESS_ENABLED=0`
- Opening audit false positives: `OPENING_AUDIT_STRICT=0`
- Session/comment automation concern: `SESSION_GRAPH_ENABLED=0` or `COMMENT_TO_SHORT_ENABLED=0`
- Quota guard false positive: `QUOTA_GUARD_ENABLED=0`
- Reporting import issue: `YOUTUBE_REPORTING_ENABLED=0`
- Music concern: `MUSIC_BED_ENABLED=0`
- SEO lint false positive: `SEO_METADATA_LINT_STRICT=0`

## Evidence to Capture

- The failed workflow run URL.
- `_data/publish_slot_decisions.jsonl` for publish/skip decisions.
- `_data/analytics/api_quota_latest.json` for quota state.
- `_data/rejected_queue.jsonl` for generation rejects.
- `_data/seo_metadata_lint.json` for metadata drift.
- `_data/upload_intents.jsonl` for the slot-level proof of upload.
- The open `Wild Brief automation alert` issue if the alert workflow created one.

## Recovery Rule

Prefer disabling the smallest feature flag first, then rerun the smallest
workflow that regenerates the affected artifact.

## Resolution Rule

An incident is resolved only when the failed slot has either an `uploaded`
ledger row or a documented intentional skip, the queue has clean publish-ready
supply, the dashboard renders, and the v1.0 closure checks in
[V1_CLOSURE.md](V1_CLOSURE.md) pass.
