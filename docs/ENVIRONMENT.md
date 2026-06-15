# Wild Brief Environment

## Required Secrets

| Name | Required | Use |
| --- | --- | --- |
| `YOUTUBE_TOKEN` | yes | OAuth token JSON for official YouTube Data API upload and optional Analytics API reads. |
| `PEXELS_API_KEY` or `PEXELS` | yes | Free Pexels API key used for the production visual source. |
| One AI text provider key | yes | Queue/story rewriting and packaging assistance. Supported names include `MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY` and `GROQ_API_KEY`. |

## Optional Secrets and Settings

| Name | Required | Use |
| --- | --- | --- |
| `BROLL_SOURCE_MODE` | no | Video source mode. Defaults to `pexels`; set to `archive` only for explicit research runs. |
| `ARCHIVE_VIDEO_MAX_BYTES` | no | Maximum Internet Archive source video file size admitted by opt-in Archive discovery. Defaults to `94371840` (90 MB). |
| `BROLL_DOWNLOAD_MAX_BYTES` | no | Maximum b-roll download size during render. Defaults to `94371840` (90 MB). |
| `GEMINI_API_KEY` or `GEMINI` | no | Visual QA when configured. |
| `WILD_BRIEF_RSS_URLS` | no | Comma-separated RSS URLs for `scripts/free_signal_harvester.py`. |
| `WILD_BRIEF_GMAIL_ALERTS` | no | Set to `1` only when alert payload generation should be enabled. |
| `WILD_BRIEF_ALERT_TO` | no | Alert recipient used only when alerts are explicitly enabled. |
| `COQUI_TTS_COMMAND` | no | Optional local Coqui-compatible TTS command. Edge TTS remains primary. |
| `COQUI_TTS_MODEL` | no | Optional local Coqui model name. |
| `ARCHIVE_AUDIO_ENABLED` | no | Enables opt-in Internet Archive public-domain/CC0 audio discovery as the autonomous music-bed source. Defaults to `0`. |
| `ARCHIVE_AUDIO_ROWS` | no | Maximum Internet Archive search rows per mood query. Defaults to `12`. |
| `ARCHIVE_AUDIO_CACHE_DIR` | no | Cache folder for downloaded Internet Archive audio. Defaults to `_data/archive_audio_cache`. |
| `ARCHIVE_AUDIO_MAX_BYTES` | no | Maximum downloaded Archive audio file size. Defaults to `20971520`. |
| `EXPERIMENTS_FILE` | no | Optional override for the experiment assignment cache. |
| `VARIANT_ASSIGNMENTS_FILE` | no | Optional override for the durable variant-assignment JSONL log. |
| `ADAPTIVE_CADENCE_ENABLED` | no | Enables publish vs safe-skip decisions from the canonical 24/day UTC grid: `00:00`, `01:00`, `02:00`, `03:00`, `04:00`, `05:00`, `06:00`, `07:00`, `08:00`, `09:00`, `10:00`, `11:00`, `12:00`, `13:00`, `14:00`, `15:00`, `16:00`, `17:00`, `18:00`, `19:00`, `20:00`, `21:00`, `22:00` and `23:00`. Defaults to enabled in the YouTube workflow. |
| `ALLOW_FLEX_SLOT` | no | Allows one operator-defined `FLEX_SLOT_UTC` in addition to the canonical slots. |
| `FLEX_SLOT_UTC` | no | Optional `HH:MM` UTC flex slot used only when `ALLOW_FLEX_SLOT=1`. |
| `MIN_SLOT_PUBLISH_SCORE` | no | Minimum top-candidate publish score required for an adaptive slot to publish. |
| `MIN_QUEUE_OPPORTUNITY_SCORE` | no | Minimum top-candidate opportunity score required for an adaptive slot to publish. |
| `QUEUE_TARGET_PENDING` | no | Target number of unconsumed queue stories to keep ready. Defaults to `24` for a one-day free inventory buffer. |
| `PUBLISH_BACKFILL_QUEUE_TARGET` | no | Publish-workflow emergency backfill target. Defaults to `24` so the upload job keeps a one-day hourly queue buffer when free discovery quota allows it. |
| `PUBLISH_BACKFILL_READY_TARGET` | no | Minimum editor-approved `publish_ready` candidates the publish workflow tries to keep before attempting upload. Defaults to `6`. |
| `PUBLISH_BACKFILL_PENDING_BATCH` | no | Extra raw pending-story target added on each emergency backfill attempt while approved supply is still low. Defaults to `12`. |
| `YOUTUBE_DESCRIPTION_MODE` | no | YouTube description mode: `empty` or `full`. Defaults to `empty` in the publishing workflow. |
| `PUBLISH_RECOVERY_DELAY_MINUTES` | no | Minutes after an hourly slot when the recovery cron maps back to the intended slot. Defaults to `40`. |
| `YOUTUBE_SCHEDULE_UPLOADS` | no | When enabled, uploads are private scheduled videos using `publishAt` instead of immediate public uploads. Defaults to `0`. |
| `YOUTUBE_SCHEDULE_START_UTC` | no | Optional RFC3339 start time for scheduled upload batches. Defaults to one hour from upload time. |
| `YOUTUBE_SCHEDULE_SLOTS_UTC` | no | Optional comma-separated `HH:MM` UTC slots for scheduled upload batches. Defaults to the canonical publish grid. |
| `YOUTUBE_SCHEDULE_OFFSET` | no | Optional starting index into the rolling schedule when adding another scheduled batch. Defaults to `0`. |
| `STUDIO_REACH_IMPORT_ENABLED` | no | Enables manual YouTube Studio Shorts Reach CSV import. |
| `STUDIO_REACH_IMPORT_PATH` | no | Folder or file path for Studio/Sheets reach CSV exports. |
| `TOPIC_FRESHNESS_ENABLED` | no | Adds free signal freshness scoring to the queue. |
| `OPENING_AUDIT_ENABLED` | no | Enables first-second motion/text/safe-zone audit metadata. |
| `OPENING_AUDIT_STRICT` | no | Rejects opening packages below `OPENING_MIN_SCORE` when enabled. |
| `OPENING_MIN_SCORE` | no | Minimum opening audit score. |
| `OPENING_GATE_MODE` | no | Opening gate v2 mode: `off`, `warn` or `block`. |
| `OPENING_GATE_MIN_SCORE` | no | Minimum opening gate v2 score. |
| `FACT_GUARD_MODE` | no | Claim risk mode: `warn` or `block`. |
| `RIGHTS_GUARD_MODE` | no | Rights guard mode: `warn` or `block`. |
| `ORIGINALITY_PACK_MODE` | no | Originality pack completeness mode: `warn` or `block`. |
| `OPS_GUARDIAN_ENFORCE` | no | Applies paused-topic guidance during candidate selection. Defaults to `1`. |
| `SESSION_GRAPH_ENABLED` | no | Enables post-upload handoff, sequel and next-session artifacts. |
| `COMMENT_TO_SHORT_ENABLED` | no | Allows strong viewer questions to become queue ideas. |
| `COMMENT_TO_SHORT_MIN_SCORE` | no | Minimum comment idea score before it can enter the queue. |
| `COMMENT_TO_SHORT_MAX_ITEMS` | no | Maximum comment ideas queued per run. |
| `QUOTA_GUARD_ENABLED` | no | Enables quota ledger/guard decisions. |
| `QUOTA_GUARD_MODE` | no | `warn` logs only; `block` can mark `PUBLISH_QUOTA_BLOCKED=1`. |
| `UPLOAD_IDEMPOTENCY_MODE` | no | `warn` records duplicates; `block` skips an already uploaded intent key. |
| `UPLOAD_SLOT_IDEMPOTENCY_MODE` | no | `warn` records duplicate slots; `block` skips a second successful upload for the same slot. |
| `MEDIA_LIFECYCLE_CLEANUP` | no | Deletes generated video/audio/image artifacts after upload while preserving `.done` markers and analytics. Defaults to `1`. |
| `QUOTA_GUARD_MAX_DAILY_RATIO` | no | Daily budget ratio used by quota guard. |
| `QUOTA_LEDGER_ENABLED` | no | Writes `_data/analytics/api_quota_ledger.jsonl` and latest summary. |
| `YOUTUBE_DAILY_QUOTA_BUDGET` | no | Conservative daily API unit budget, default `10000`. |
| `YOUTUBE_DAILY_UPLOAD_BUDGET` | no | Conservative daily `videos.insert` call budget, default `100`. |
| `YOUTUBE_REPORTING_ENABLED` | no | Enables optional Reporting API CSV backfill folders. |
| `WAREHOUSE_COMPACTION_ENABLED` | no | Writes monthly analytics JSONL partitions. |
| `MUSIC_BED_ENABLED` | no | Enables optional music beds. Defaults to `0` for the Pexels-only restart. |
| `MUSIC_BED_CANARY_PERCENT` | no | Percent of safe Shorts allowed into music-bed canary. Defaults to `5`. |
| `SEO_METADATA_LINT_ENABLED` | no | Adds deterministic SEO/search lint to metadata and repo checks. |
| `SEO_METADATA_LINT_STRICT` | no | Rejects generated metadata with SEO lint errors when set to `1`. |

YouTube `videos.insert` calls use their own daily upload bucket. Keep
`YOUTUBE_DAILY_UPLOAD_BUDGET=100` unless Google Cloud shows a different
project-specific value. The 10000-unit `YOUTUBE_DAILY_QUOTA_BUDGET` still
protects non-upload calls such as thumbnails, playlists, comments and analytics.

## Feature Flag Registry

| Flag | Default | Owner | Purpose | Rollback |
|---|---:|---|---|---|
| `ADAPTIVE_CADENCE_ENABLED` | `1` | publishing | Enable adaptive publish/skip decisions. | Set to 0 for legacy slot behavior. |
| `ALLOW_FLEX_SLOT` | `0` | publishing | Allow one extra operator-defined UTC slot. | Set to 0. |
| `FLEX_SLOT_UTC` | `` | publishing | Optional HH:MM UTC flex slot. | Unset it. |
| `MIN_SLOT_PUBLISH_SCORE` | `72` | publishing | Minimum publish score for adaptive cadence. | Lower or disable adaptive cadence. |
| `MIN_QUEUE_OPPORTUNITY_SCORE` | `50` | publishing | Minimum queue opportunity score for a slot. | Lower or disable adaptive cadence. |
| `QUEUE_TARGET_PENDING` | `24` | publishing | Pending story target for hourly queue refresh. | Lower if free discovery/AI quotas become tight. |
| `PUBLISH_BACKFILL_QUEUE_TARGET` | `24` | publishing | Emergency pending story target checked inside the publish workflow. | Lower if the publish workflow approaches its timeout. |
| `PUBLISH_BACKFILL_READY_TARGET` | `6` | publishing | Minimum editor-approved publish-ready candidates before a publish attempt. | Lower only during provider outages. |
| `PUBLISH_BACKFILL_PENDING_BATCH` | `12` | publishing | Extra raw pending target added on each emergency backfill attempt. | Lower if the publish workflow approaches timeout. |
| `BROLL_SOURCE_MODE` | `pexels` | discovery | Use Pexels as the only active production visual source. | Set back to `pexels`; use `archive` only for explicit research runs. |
| `ARCHIVE_VIDEO_MAX_BYTES` | `94371840` | discovery | Reject overly large opt-in Archive source files before rendering. | Leave unchanged unless Archive research is intentionally enabled. |
| `BROLL_DOWNLOAD_MAX_BYTES` | `94371840` | production | Cap video-source downloads during rendering. | Lower during CI timeouts. |
| `YOUTUBE_DESCRIPTION_MODE` | `empty` | publishing | YouTube description mode: empty or full. | Set to full. |
| `PUBLISH_RECOVERY_DELAY_MINUTES` | `40` | publishing | Minutes after an hourly slot when recovery cron maps back to the intended slot. | Set to 40. |
| `YOUTUBE_SCHEDULE_UPLOADS` | `0` | publishing | Upload as private scheduled videos with publishAt. | Set to 0 for normal slot-time public uploads. |
| `YOUTUBE_SCHEDULE_START_UTC` | `` | publishing | Optional start time for scheduled upload batches. | Unset it. |
| `YOUTUBE_SCHEDULE_SLOTS_UTC` | `` | publishing | Optional scheduled batch slot list. | Unset to use canonical slots. |
| `YOUTUBE_SCHEDULE_OFFSET` | `0` | publishing | Offset for adding another scheduled batch after existing scheduled items. | Reset to 0 after batch upload. |
| `STUDIO_REACH_IMPORT_ENABLED` | `1` | analytics | Import manually exported Shorts Reach CSV data. | Set to 0. |
| `STUDIO_REACH_IMPORT_PATH` | `_data/studio_reach_exports` | analytics | Path to Studio/Sheets reach CSV exports. | Leave empty or remove files. |
| `TOPIC_FRESHNESS_ENABLED` | `1` | discovery | Annotate queue entries with free freshness signals. | Set to 0. |
| `OPENING_AUDIT_ENABLED` | `1` | production | Score the first second opening package. | Set to 0. |
| `OPENING_AUDIT_STRICT` | `1` | production | Reject openings below the configured score. | Set to 0 for informational mode. |
| `OPENING_MIN_SCORE` | `72` | production | Minimum opening audit score. | Lower threshold or disable strict mode. |
| `OPENING_GATE_MODE` | `warn` | production | Opening gate v2 mode: off, warn or block. | Use warn. |
| `OPENING_GATE_MIN_SCORE` | `78` | production | Minimum opening gate v2 score. | Lower threshold or set OPENING_GATE_MODE=off. |
| `FACT_GUARD_MODE` | `block` | production | Claim risk mode: warn or block. | Use warn. |
| `RIGHTS_GUARD_MODE` | `block` | production | Rights guard mode: warn or block. | Use warn. |
| `ORIGINALITY_PACK_MODE` | `warn` | production | Originality pack completeness mode: warn or block. | Use warn. |
| `SESSION_GRAPH_ENABLED` | `1` | growth | Build post-upload handoff and sequel graph artifacts. | Set to 0. |
| `COMMENT_TO_SHORT_ENABLED` | `1` | growth | Promote strong viewer questions into Short ideas. | Set to 0. |
| `COMMENT_TO_SHORT_MIN_SCORE` | `64` | growth | Minimum score to add a comment idea to the queue. | Raise threshold or disable. |
| `COMMENT_TO_SHORT_MAX_ITEMS` | `6` | growth | Maximum comment ideas added per run. | Lower limit. |
| `QUOTA_GUARD_ENABLED` | `1` | operations | Block runs projected to exceed quota budget. | Set to 0 for passive logging. |
| `QUOTA_GUARD_MODE` | `block` | operations | Quota guard mode: warn or block. | Use warn. |
| `UPLOAD_IDEMPOTENCY_MODE` | `block` | operations | Upload idempotency mode: warn or block duplicate completed intents. | Use warn. |
| `UPLOAD_SLOT_IDEMPOTENCY_MODE` | `block` | operations | Block a second successful upload for the same publish slot. | Use warn. |
| `MEDIA_LIFECYCLE_CLEANUP` | `1` | operations | Delete generated media after successful upload while keeping metadata markers. | Set to 0 temporarily while debugging renders. |
| `OPS_GUARDIAN_ENFORCE` | `1` | operations | Apply ops guardian paused-topic guidance during candidate selection. | Set to 0. |
| `QUOTA_GUARD_MAX_DAILY_RATIO` | `0.95` | operations | Daily budget ratio before guard trips. | Raise ratio or disable. |
| `QUOTA_LEDGER_ENABLED` | `1` | operations | Write API quota ledger artifacts. | Set to 0. |
| `YOUTUBE_DAILY_QUOTA_BUDGET` | `10000` | operations | Conservative daily YouTube quota unit budget. | Raise only after checking API quota. |
| `YOUTUBE_DAILY_UPLOAD_BUDGET` | `100` | operations | Conservative daily YouTube upload-call budget. | Match the Google Cloud upload quota. |
| `YOUTUBE_REPORTING_ENABLED` | `0` | analytics | Enable optional Reporting API CSV backfill folders. | Set to 0. |
| `WAREHOUSE_COMPACTION_ENABLED` | `1` | analytics | Write monthly JSONL analytics partitions. | Set to 0. |
| `MUSIC_BED_ENABLED` | `0` | production | Allow optional music beds. | Set to 0. |
| `ARCHIVE_AUDIO_ENABLED` | `0` | production | Allow opt-in Internet Archive public-domain/CC0 audio candidates after license metadata checks. | Set to 0. |
| `ARCHIVE_AUDIO_ROWS` | `12` | production | Limit Archive API search breadth per mood. | Lower rows or set ARCHIVE_AUDIO_ENABLED=0. |
| `ARCHIVE_AUDIO_CACHE_DIR` | `_data/archive_audio_cache` | production | Cache downloaded Archive audio. | Remove cache and disable Archive audio. |
| `MUSIC_BED_CANARY_PERCENT` | `5` | production | Percent of Shorts allowed into safe music-bed canary. | Set to 0. |
| `SEO_METADATA_LINT_ENABLED` | `1` | production | Attach deterministic SEO/metadata lint to every Short. | Set to 0. |
| `SEO_METADATA_LINT_STRICT` | `0` | production | Reject metadata with SEO lint errors. | Set to 0. |
| `COQUI_TTS_COMMAND` | `` | resilience | Optional local Coqui-compatible TTS command. | Unset it. |
| `COQUI_TTS_MODEL` | `` | resilience | Optional Coqui model name. | Unset it. |
| `COQUI_TTS_LOCALE_ARG` | `0` | resilience | Pass language_idx to Coqui CLI. | Set to 0. |

## Local-Only Files

Do not commit:

- OAuth client secrets.
- YouTube token JSON files.
- temporary rendered videos/audio/images.
- local TTS caches.
- manual credentials or debug dumps.

Operator-dropped Google Trends snapshots belong under `_data/trends/manual_import/`.
Those files should contain public trend data only.

Pexels is the active production video source. `BROLL_SOURCE_MODE=pexels`
keeps both queue discovery and render-time b-roll on Pexels only. Internet
Archive video is kept as an explicit opt-in research path for future review;
it is not used by the production queue or publisher unless `BROLL_SOURCE_MODE`
is deliberately changed. `ARCHIVE_AUDIO_ENABLED=0` keeps Archive audio off by
default; when it is deliberately enabled, metadata checks apply to optional
music/audio candidates. Use `python scripts/archive_video_report.py
--json` only when reviewing Archive video candidates and
`python scripts/archive_audio_report.py --json` to review audio candidate
sources and license evidence.

Publish slot decisions are appended to `_data/publish_slot_decisions.jsonl`.
When adaptive cadence is enabled, a slot can safely return `skip_outside_slot`,
`skip_no_eligible_story`, `skip_low_queue_quality` or `skip_quota_guard`
without failing the workflow.

Generated and uploaded metadata carries the shared temporal contract:
`publish_ts_utc`, `publish_day_pt`, `quota_day_pt` and `views_regime`.
Operational schedules stay in UTC, while YouTube quota and Analytics day
alignment use Pacific Time.

## Logging Rules

- Never print OAuth token payloads.
- Never print API keys.
- Keep alert bodies short and secret-free.
- Use `utils.observability.emit_event` for structured script events.
- Redact fields whose names include `token`, `secret`, `password`,
  `credential`, `authorization` or `api_key`.
