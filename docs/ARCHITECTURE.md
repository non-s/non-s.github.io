# Amber Hours Architecture

Amber Hours is a zero-cost rain & thunder ambience production loop: one
fixed, real Pixabay clip per format (falling back to an original
animated storm scene if ever missing) + procedurally-synthesized
rain/thunder audio (no music layer) become a long-form ambience video,
looping vertical YouTube Shorts, and a 24/7 YouTube Live relay, with no
narration and no editorial/story queue.

## Core Loops

- Production: `generate_storm_ambience.py` renders one ~1-hour ambience
  video per run; `generate_storm_short.py` renders one vertical Short.
- Upload: `upload_youtube.py` publishes through the official YouTube Data
  API and writes `.done` sidecars.
- Live: `scripts/live_stream_dynamic.py` runs the 24/7 RTMP relay (one
  looped storm clip + the synthesized rain/thunder bed).
- Learning: optional manual imports via
  `scripts/import_studio_reach_export.py` and `scripts/reporting_pull.py`
  feed the GitHub Pages dashboard (`scripts/build_dashboard.py`).
- Operations: `scripts/quota_preflight.py`, `scripts/media_lifecycle.py`,
  `scripts/check_repo_contracts.py`, `scripts/check_workflow_contracts.py`.

## Durable Artifacts

`_data/analytics/latest.json` and `_data/analytics/studio_reach_latest.json`
hold the last known channel snapshot; both are optional and degrade safely
to zero/empty when no manual export has been run yet. `_videos/*.done`
markers are the source of truth for what has actually been published.

Each `.done`/upload-intent record carries `publish_ts_utc` (the UTC
timestamp of the actual upload), `quota_day_pt` (the Pacific-time quota day
the upload counted against, since `YOUTUBE_DAILY_UPLOAD_BUDGET` resets on
YouTube's own daily cycle) and `views_regime` (a coarse bucket the
dashboard/analytics scripts use to compare a Short's views against others
in the same age range) — see `utils/time_semantics.py`,
`utils/api_quota_budget.py` and `utils/analytics_schema.py`.
