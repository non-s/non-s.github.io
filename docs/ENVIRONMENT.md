# Amber Hours Environment

## Required Secrets

| Name | Required | Use |
| --- | --- | --- |
| `YOUTUBE_TOKEN` | yes | OAuth token JSON for official YouTube Data API upload and optional Analytics API reads. |
| `PIXABAY_API_KEY` | yes | Free Pixabay API key used for the lofi pipeline's anime/illustrated b-roll (`video_type=animation`). |
| `YOUTUBE_STREAM_KEY` | only for the 24/7 live relay (`live-stream.yml`) | RTMP stream key the live relay pushes to. |

Jamendo music sync (`scripts/sync_jamendo_music.py`) uses a registered
Jamendo client id hardcoded in that script and needs no separate secret.
No AI text provider key is required by the lofi pipeline — title/
description text is template-based, not AI-generated; an optional
translation feature in `upload_youtube.py` degrades gracefully to
English-only when no `MISTRAL_API_KEY`/`CEREBRAS_API_KEY`/
`GEMINI_API_KEY`/`GROQ_API_KEY` is configured.

## Feature Flag Registry

| Flag | Default | Owner | Purpose | Rollback |
|---|---:|---|---|---|
| `YOUTUBE_PUBLISHING_ENABLED` | `0` | publishing | Master switch for the hourly lofi Shorts publisher. | Set to 0 to pause publishing entirely. |
| `ADAPTIVE_CADENCE_ENABLED` | `1` | publishing | Enables publish vs safe-skip decisions from the canonical 24/day UTC grid: `00:00`, `01:00`, `02:00`, `03:00`, `04:00`, `05:00`, `06:00`, `07:00`, `08:00`, `09:00`, `10:00`, `11:00`, `12:00`, `13:00`, `14:00`, `15:00`, `16:00`, `17:00`, `18:00`, `19:00`, `20:00`, `21:00`, `22:00` and `23:00`. | Set to 0 for legacy slot behavior. |
| `ALLOW_FLEX_SLOT` | `0` | publishing | Allows one operator-defined `FLEX_SLOT_UTC` in addition to the canonical slots. | Set to 0. |
| `FLEX_SLOT_UTC` | (empty) | publishing | Optional `HH:MM` UTC flex slot used only when `ALLOW_FLEX_SLOT=1`. | Unset it. |
| `MIN_SLOT_PUBLISH_SCORE` | `72` | publishing | Minimum top-candidate publish score required for an adaptive slot to publish. | Lower or disable adaptive cadence. |
| `MIN_QUEUE_OPPORTUNITY_SCORE` | `50` | publishing | Minimum top-candidate opportunity score required for an adaptive slot to publish. | Lower or disable adaptive cadence. |
| `YOUTUBE_DESCRIPTION_MODE` | `full` | publishing | YouTube description mode: empty or full. | Set to empty for a minimal-description rollback. |
| `CHANNEL_PLAYLIST_PREFIX` | (empty) | publishing | Text prepended to every auto-created playlist title. | Unset it to use bare playlist titles. |
| `CHANNEL_DEFAULT_HASHTAGS` | `#Shorts` | publishing | Comma-separated hashtags appended to the description when not already present. | Set to #Shorts to drop channel-specific tags. |
| `CHANNEL_PLAYLIST_DESCRIPTION` | `Shorts grouped for easier binge watching.` | publishing | Description text used for every auto-created playlist. | Unset it to use the generic default. |
| `PUBLISH_RECOVERY_DELAY_MINUTES` | `40` | publishing | Minutes after an hourly slot when recovery cron maps back to the intended slot. | Set to 40. |
| `PUBLISH_HEARTBEAT_RECENT_RUN_TOLERANCE_MINUTES` | `10` | publishing | Lookback before a slot used by the heartbeat to avoid duplicate publisher dispatches. | Raise if GitHub frequently delays publisher runs. |
| `YOUTUBE_SCHEDULE_UPLOADS` | `0` | publishing | Upload as private scheduled videos using `publishAt` instead of immediate public uploads. | Set to 0 for normal slot-time public uploads. |
| `YOUTUBE_SCHEDULE_START_UTC` | (empty) | publishing | Optional RFC3339 start time for scheduled upload batches. | Unset it. |
| `YOUTUBE_SCHEDULE_SLOTS_UTC` | (empty) | publishing | Optional comma-separated `HH:MM` UTC slots for scheduled upload batches. | Unset to use the canonical publish grid. |
| `YOUTUBE_SCHEDULE_OFFSET` | `0` | publishing | Starting index into the rolling schedule when adding another scheduled batch. | Reset to 0 after batch upload. |
| `STUDIO_REACH_IMPORT_ENABLED` | `1` | analytics | Import manually exported Shorts Reach CSV data. | Set to 0. |
| `YOUTUBE_REPORTING_ENABLED` | `0` | analytics | Enable optional Reporting API CSV backfill folders. | Set to 0. |
| `QUOTA_GUARD_ENABLED` | `1` | operations | Block runs projected to exceed quota budget. | Set to 0 for passive logging. |
| `QUOTA_GUARD_MODE` | `block` | operations | Quota guard mode: anything other than `block` just warns. | Use `off`. |
| `UPLOAD_IDEMPOTENCY_MODE` | `block` | operations | Upload idempotency mode: warn or block duplicate completed intents. | Use warn. |
| `UPLOAD_SLOT_IDEMPOTENCY_MODE` | `block` | operations | Block a second successful upload for the same publish slot. | Use warn. |
| `MEDIA_LIFECYCLE_CLEANUP` | `1` | operations | Delete generated media after successful upload while keeping metadata markers. | Set to 0 temporarily while debugging renders. |
| `OPS_ALERTS_ENABLED` | `1` | operations | Create a GitHub Issue when a critical automation workflow fails. | Set to 0 to silence issue alerts. |
| `QUOTA_GUARD_MAX_DAILY_RATIO` | `0.95` | operations | Daily budget ratio before guard trips. | Raise ratio or disable. |
| `QUOTA_LEDGER_ENABLED` | `1` | operations | Write API quota ledger artifacts. | Set to 0. |
| `YOUTUBE_DAILY_QUOTA_BUDGET` | `10000` | operations | Conservative daily YouTube quota unit budget. | Raise only after checking API quota. |
| `YOUTUBE_DAILY_UPLOAD_BUDGET` | `100` | operations | Conservative daily YouTube upload-call budget. | Match the Google Cloud upload quota. |

YouTube `videos.insert` calls use their own daily upload bucket. Keep
`YOUTUBE_DAILY_UPLOAD_BUDGET=100` unless Google Cloud shows a different
project-specific value. The 10000-unit `YOUTUBE_DAILY_QUOTA_BUDGET` still
protects non-upload calls such as thumbnails, playlists, comments and analytics.

## Local-Only Files

Do not commit:

- OAuth client secrets.
- YouTube token JSON files.
- temporary rendered videos/audio/images.
- manual credentials or debug dumps.

## Logging Rules

- Never print OAuth token payloads.
- Never print API keys.
- Keep alert bodies short and secret-free.
- Redact fields whose names include `token`, `secret`, `password`,
  `credential`, `authorization` or `api_key`.
