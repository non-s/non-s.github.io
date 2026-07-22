# Amber Hours Environment

## Required Secrets

| Name | Required | Use |
| --- | --- | --- |
| `YOUTUBE_TOKEN` | yes | OAuth token JSON for official YouTube Data API upload and optional Analytics API reads. |
| `PIXABAY_API_KEY` | only for the admin b-roll resync/search tools (`admin-resync-broll.yml`, `admin-search-broll-candidates.yml`) | The scheduled pipeline no longer fetches footage live -- each format loops one fixed, hand-picked real Pixabay clip committed in the repo. |
| `YOUTUBE_STREAM_KEY` | only for the 24/7 live relay (`live-stream.yml`) | RTMP stream key the live relay pushes to. |

No AI text provider key is required — title/description text is
template-based by default; an optional translation feature in
`upload_youtube.py` degrades gracefully to English-only when no
`MISTRAL_API_KEY`/`CEREBRAS_API_KEY`/`GEMINI_API_KEY`/`GROQ_API_KEY` is
configured.

`utils/ai_titling.py` calls `utils/ai_helper.py`'s
`ai_text(..., json_mode=True)` to write each storm video's title,
description and hashtags. That routes to Gemini first when
`GEMINI_API_KEY` is set (falling back through Cerebras/Groq/Mistral,
whichever keys are configured); with no key configured at all, it falls
back to the template title/description. `GEMINI_API_KEY` is optional
either way, never required.

## Feature Flag Registry

| Flag | Default | Owner | Purpose | Rollback |
|---|---:|---|---|---|
| `YOUTUBE_PUBLISHING_ENABLED` | `0` | publishing | Master switch for general publishing/health-check automation. | Set to 0 to pause publishing entirely. |
| `ADAPTIVE_CADENCE_ENABLED` | `1` | publishing | Enables publish vs safe-skip decisions from the canonical 12/day UTC grid (every 2 hours -- see the full list below the table). | Set to 0 for legacy slot behavior. |
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
| `COMMUNITY_ENGAGEMENT_ENABLED` | `0` | community | Master switch for comment replies and the weekly Community post draft, independent of `YOUTUBE_PUBLISHING_ENABLED`. | Set to 0 to pause both. |
| `COMMENT_REPLY_MAX_PER_RUN` | `15` | community | Cap on comment replies posted per `community-comment-replies.yml` run. | Lower it, or set `COMMUNITY_ENGAGEMENT_ENABLED` to 0. |
| `STORM_AMBIENCE_ENABLED` | `0` | publishing | Master switch for the `storm-ambience.yml` pillar (real rain/thunder ambience), independent of `YOUTUBE_PUBLISHING_ENABLED`. | Set to 0 to pause this pillar. |
| `STORM_MIN_DURATION_MINUTES` | `45` | publishing | Minimum runtime (minutes) for a generated storm-ambience video. | Lower it for faster/smaller uploads. |
| `STORM_MAX_DURATION_MINUTES` | `75` | publishing | Maximum runtime (minutes) for a generated storm-ambience video. | Lower it for faster/smaller uploads. |
| `CUTE_ANIMALS_ENABLED` | `0` | publishing | Master switch for the cute-animals-shorts.yml pillar (real cute-animal clips + real Jamendo jazz, published as "Pata Jazz"), independent of YOUTUBE_PUBLISHING_ENABLED and STORM_AMBIENCE_ENABLED. | Set to 0 to pause this pillar. |
| `BABY_NOISE_ENABLED` | `0` | publishing | Master switch for the baby-noise-ambience.yml/baby-noise-shorts.yml pillar (procedurally-synthesized white/pink/brown noise, published as Amber Hours), independent of YOUTUBE_PUBLISHING_ENABLED/STORM_AMBIENCE_ENABLED/CUTE_ANIMALS_ENABLED. | Set to 0 to pause this pillar. |
| `BABY_NOISE_MIN_DURATION_MINUTES` | `180` | publishing | Minimum runtime (minutes) for a generated baby-noise ambience video. | Lower it for faster/smaller uploads. |
| `BABY_NOISE_MAX_DURATION_MINUTES` | `300` | publishing | Maximum runtime (minutes) for a generated baby-noise ambience video. | Lower it for faster/smaller uploads. |
| `CLASSICAL_AMBIENCE_ENABLED` | `0` | publishing | Master switch for classical-ambience.yml (real, licensed classical/orchestral/piano tracks, one per video, published as Amber Hours Classical), independent of every other pillar's switch. | Set to 0 to pause this pillar. |
| `CLASSICAL_LIVE_ENABLED` | `0` | publishing | Master switch for live-stream-classical.yml (the classical pillar's own 24/7 live relay, independent stream key from the rain pillar's live), independent of CLASSICAL_AMBIENCE_ENABLED and every other pillar's live/upload switches. | Set to 0 to pause this live relay. |

YouTube `videos.insert` calls use their own daily upload bucket. Keep
`YOUTUBE_DAILY_UPLOAD_BUDGET=100` unless Google Cloud shows a different
project-specific value. The 10000-unit `YOUTUBE_DAILY_QUOTA_BUDGET` still
protects non-upload calls such as thumbnails, playlists, comments and analytics.

## Canonical Publish Grid

`GLOBAL_PUBLISH_WINDOWS` (`utils/audience_expansion.py`) defines one slot
every 2 hours, even hours only (12 slots/day):

```
00:00, 02:00, 04:00, 06:00, 08:00, 10:00,
12:00, 14:00, 16:00, 18:00, 20:00, 22:00
```

This was the lofi Shorts pipeline's publish cadence; that pipeline was
removed when the channel pivoted fully to the storm/rain ambience pillar
(growth pass, 2026-07-21), which publishes on its own, separate cadence
(`storm-ambience.yml` twice daily, `storm-shorts.yml` every 2 hours,
neither keyed off this grid). `CANONICAL_SLOTS_UTC`
(`utils/publish_schedule.py`) and this grid stay documented because
`upload_youtube.py`'s dedup/adaptive-schedule math still references them
-- see `scripts/check_schedule_sync.py`'s docstring for the full
retirement note on why no workflow-cron-coverage check runs against this
grid anymore.

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
