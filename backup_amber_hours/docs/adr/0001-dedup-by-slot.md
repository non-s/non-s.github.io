# ADR 0001: Publish Slot-Based Deduplication

## Status
Accepted

## Context
YouTube's API limits uploads per account. Without deduplication, a workflow retry or delayed execution could cause the same video to publish twice to the same slot, wasting quota and creating duplicate channel content.

## Decision
Implement **idempotent upload ledger keyed by canonical publish slot** (`YYYY-MM-DDTHH:MMZ`).

Each upload records:
- `publish_slot_key` (immutable timestamp)
- `upload_intent_key` (unique hash of metadata)
- `video_id` (YouTube video ID after successful upload)
- `status` (pending → uploaded → completed)

## Rationale
1. **Slot-level dedup is atomic:** A workflow retry within the same UTC minute sees the same slot key and can safely skip if already uploaded.
2. **Works across retries:** GitHub Actions retry, manual dispatch, or watchdog recovery all see the same ledger.
3. **Survives transient failures:** If upload succeeds but metadata write fails, re-run finds `video_id` and marks it completed without uploading again.
4. **Enables rate limiting:** Can safely publish N times per slot without risk of duplication.

## Consequences
- ✅ Quota-safe: impossible to waste quota on duplicate uploads
- ✅ Observability: ledger is audit trail of what published and when
- ⚠️ Requires careful clock management: slot key must be UTC, never local time
- ⚠️ Ledger corruption = loss of dedup guarantee (mitigated by read-only checks)

## Alternatives Considered
1. **Video ID-based dedup:** Search YouTube for recent videos by title hash → too slow, quota-intensive
2. **Workflow run ID-based dedup:** Only works within GitHub Actions → brittle for manual dispatch
3. **No dedup:** Accept duplicate uploads → unacceptable quota waste

## See Also
- `utils/publish_schedule.py` — slot calculation
- `scripts/upload_intent.py` — ledger recording
- `ENVIRONMENT.md` — `UPLOAD_SLOT_IDEMPOTENCY_MODE` flag
