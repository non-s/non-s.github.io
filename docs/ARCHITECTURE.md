# Amber Hours Architecture

Amber Hours is a zero-cost lofi radio production loop: free-licensed
Pixabay anime b-roll + Creative Commons (CC BY) Jamendo music become
looping lofi YouTube Shorts and a 24/7 YouTube Live relay, with no
narration and no editorial/story queue.

## Core Loops

- Media sync: `scripts/sync_lofi_broll.py` (Pixabay b-roll cache),
  `scripts/sync_jamendo_music.py` (Jamendo bgm cache).
- Production: `generate_lofi_short.py` renders one Short per run from the
  synced libraries.
- Upload: `upload_youtube.py` publishes through the official YouTube Data
  API and writes `.done` sidecars.
- Live: `scripts/live_stream_dynamic.py` runs the 24/7 RTMP relay (one
  looped clip + the full local bgm playlist).
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
