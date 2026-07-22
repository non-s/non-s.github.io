# Amber Hours Incidents

## Safe Rollback Flags

- Quota guard false positive: `QUOTA_GUARD_MODE=off`
- Media lifecycle cleanup concern: `MEDIA_LIFECYCLE_CLEANUP=0`
- Publishing needs to pause entirely: `YOUTUBE_PUBLISHING_ENABLED=0`

## Evidence to Capture

- The failed workflow run URL.
- `_data/analytics/api_quota_latest.json` for quota state.
- `_data/upload_intents.jsonl` for the slot-level proof of upload.
- `_data/media_lifecycle_report.json` for b-roll/bgm cleanup state.
- The open `Amber Hours automation alert` issue if the alert workflow created one.

## Recovery Rule

Prefer disabling the smallest feature flag first, then rerun the smallest
workflow that regenerates the affected artifact.

## Resolution Rule

An incident is resolved only when the missed slot has either an `uploaded`
ledger row or a documented intentional skip, and the next scheduled
content workflow run completes clean.
