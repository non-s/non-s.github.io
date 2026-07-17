# Lofi Beats Bot (YouTube)

[![Production quality gate](https://github.com/non-s/non-s.github.io/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/quality-gate.yml)
[![YouTube Bot - Shorts only](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml)

Automated pipeline that turns free-licensed Pixabay anime/illustrated
b-roll (the "Lofi Girl" studying-loop look) and Creative Commons (CC BY,
commercial-safe) music into looping lofi YouTube Shorts and a 24/7 lofi
live stream, with no narration -- clip + music only -- and publishes
through the official YouTube Data API.

- Cadence: `youtube-bot.yml` fires up to 3x/hour (`:02`, `:22`, `:42`, the
  extra two as a recovery net for delayed/dropped GitHub schedule events);
  `upload_youtube.py`'s own per-canonical-slot dedup keeps a slot from
  publishing twice.
- Duration: **30-58 seconds** per Short, randomized.
- Category: YouTube **Science & Technology** (`categoryId=28`).
- Content: a random Pixabay anime-style lofi clip (`video_type=animation`
  -- girl studying, rain windows, cozy rooms, night cities, ...) looped
  under a random CC BY-licensed Jamendo track, with a lofi-genre title/
  description and a custom thumbnail frame. Pexels was tried first but has
  no genuine illustrated content -- checked live, its "anime" search
  results are cosplay footage and mistagged live-action.

## Pipeline

```text
scripts/sync_lofi_broll.py   -> _assets/video/lofi_broll (Pixabay anime clips)
scripts/sync_jamendo_music.py -> _assets/audio/bgm (Jamendo CC BY tracks)
generate_lofi_short.py        -> _videos/*.mp4 + metadata (Shorts)
generate_lofi_long_video.py   -> _videos/long_video_*.mp4 (24/7 live loop)
upload_youtube.py             -> YouTube Shorts + .done sidecar
scripts/live_stream_dynamic.py -> 24/7 YouTube Live relay
```

This channel was rebuilt from an earlier nature-science-facts format
(narrated Shorts, editorial scoring pipeline, trend hijacking, a story
queue). Everything below "Editorial system" describes that earlier
pipeline: the code is still in the repo but nothing in
`.github/workflows/` invokes `generate_shorts.py`, `fetch_animals.py` or
`publish_window.py` anymore. Kept for reference rather than deleted, since
several of its modules (b-roll fetching, upload, media lifecycle) are still
the ones the lofi pipeline reuses.

## Editorial system

Every candidate passes through an automated editor-in-chief before rendering:

- scores topic opportunity across viral, visual, replay, comment, education, emotion and novelty signals;
- blocks low-opportunity topics before rendering or upload;
- blocks weak content patterns such as generic thumbnails, generic hooks, repetitive scripts and recycled topics;
- predicts retention with hook, curiosity, visual, replay and completion scores;
- predicts subscriber conversion from hook, CTA, pinned comment, final prompt and series continuity;
- generates 10 titles, 10 thumbnail texts and 5 alternate hooks, then ships the best-scored package;
- caches packaging selection per story to avoid repeated scoring work;
- learns from `_videos/*.done` markers into `_data/format_memory.json`, including real views, likes, comments, retention and subscriber gains when available;
- records lightweight explore/exploit experiments for formats, hooks, thumbnails, loop styles, end cards and CTAs;
- writes `_data/fan_growth.json` to rank videos, categories and formats by subscribers per 1,000 views and comments per 1,000 views;
- writes `_data/audience_memory.json` to learn category, format and series strength from real retention, watch time, subscribers and comments;
- joins `.done` markers with `_data/analytics/latest.json` and `_data/youtube_intelligence.json` so learning uses real channel outcomes instead of empty sidecar fields;
- writes `_data/early_performance.json`, `_data/early_warning.json` and `_data/winner_patterns.json` to learn distribution velocity, acceleration and breakout patterns;
- blocks robotic title shapes such as repeated "one trick / one reason" templates;
- ranks specific nature stories by editorial quality;
- blocks weak scripts and subjects repeated inside a three-day cooldown;
- organizes videos into recurring series such as **Earth Engine**, **Hidden Network** and **Rare Earth**;
- renders a readable 2-4 word cover inside the opening frame and an experiment-aware end-screen CTA;
- burns yellow CapCut-style captions with highlighted keywords;
- uses faster b-roll beats, subtle zoom, micro-fades and contrast/saturation lift;
- creates/maintains YouTube playlists for series and categories;
- replies automatically to eligible viewer comments with varied, short, classified responses and records a reply ledger;
- records public YouTube engagement after uploads and feeds winning categories, series and experiments back into the dashboard.
- uses Gemini visual QA to reject unrelated thumbnails when `GEMINI_API_KEY` is configured;
- reads retention, traffic-source, segment and subscriber conversion signals when the OAuth token includes YouTube Analytics access.
- skips production candidates without real motion b-roll or burned captions instead of uploading low-retention fallbacks.
- writes variant assignments during generation into `_data/analytics/variant_assignments.jsonl` so experiments are auditable before upload.
- applies loop-plan final lines to the rendered narration and captions, not only to metadata.
- can recover from Edge TTS outages through an optional local Coqui-compatible command.
- imports optional YouTube Studio Shorts Reach CSV exports into `_data/analytics/studio_reach_daily.jsonl` so stayed-to-watch and swipe signals are visible in weekly review and the dashboard.
- defines the finished v1.0 operating contract in [`docs/V1_CLOSURE.md`](docs/V1_CLOSURE.md).
- annotates the queue with `_data/trends/freshness_report.json` from free CSV/RSS/manual trend signals.
- audits the first second of each Short through `opening_audit` metadata and `_data/opening_audit_report.json`.
- applies `opening_gate_v2` scoring over the first 0.7s and 1.5s with motion,
  contrast, legibility, curiosity and first-word timing subscores.
- records hook-library, story-pattern, payoff, loop-semantics, claim-risk,
  rights-provenance and originality-pack metadata before upload.
- writes `_data/upload_intents.jsonl` so uploads are idempotent by story,
  slot, variant and script hash.
- governs experiments through `_data/experiment_registry.json` and
  `_data/underpowered_tests.json` so low-volume runs test one creative axis at a time.
- builds `_data/session_graph.json`, `_data/next_session_actions.json` and `_data/sequel_candidates.json` after upload for playlist, pinned-comment and sequel continuity.
- writes `_data/analytics/api_quota_ledger.jsonl` and `_data/analytics/api_quota_latest.json` before expensive jobs.
- promotes high-signal viewer questions into `_data/comment_to_short_candidates.json` and optionally into the queue.
- compacts analytics into monthly `_data/analytics/partitions/` JSONL files while keeping flat files backward-compatible.
- writes `_data/scale_blueprint.json` to turn Studio metrics into a million-view operating plan with bottlenecks, series lanes, winner/remake actions and milestone targets.

## World-class upgrade track

The operating model is now documented in
[docs/WILD_BRIEF_WORLD_CLASS_UPGRADE.md](docs/WILD_BRIEF_WORLD_CLASS_UPGRADE.md).
The channel-scale plan is documented in
[docs/MILLION_VIEW_SCALE_SYSTEM.md](docs/MILLION_VIEW_SCALE_SYSTEM.md).
The master-prompt implementation is complete across the production path:
rulebook preflight, curiosity and swipe scoring, rendered loop callbacks,
expanded A/B axes, live variant logging, extended analytics warehouse files,
weekly decisions, free signal harvesting, Studio Reach import, opening audit,
quota guard, comment-to-Short triage, Reporting CSV backfill, warehouse
compaction, post-upload session ops, dashboard sections, CI smoke checks and
optional zero-cost fallbacks are all wired without
replacing the current queue, render, upload or official YouTube APIs.

## Required secrets

- `YOUTUBE_TOKEN` -- Shorts upload + playlist/comment operations.
- `PIXABAY_API_KEY` -- anime/illustrated b-roll for Shorts and the live loop.
- `YOUTUBE_STREAM_KEY` -- only needed for the 24/7 live relay
  (`live-stream.yml`).

Jamendo music sync (`scripts/sync_jamendo_music.py`) uses a registered
Jamendo client id (`CLIENT_ID` in that script) and needs no separate
GitHub secret. No AI text provider key is required by the active lofi
pipeline -- title/description text is template-based, not AI-generated.

`YOUTUBE_TOKEN` is an OAuth JSON token, not an API key. Generate it once with `auth_youtube.py` or the `Build auth_youtube.exe (Windows)` workflow. See [SETUP.md](SETUP.md).

## Subdirectory: YouTube Auto Publisher

The general-purpose video generation pipeline `youtube-auto-publisher` has been merged into the [youtube-auto-publisher/](youtube-auto-publisher/) directory of this repository.

To use it:
1. Navigate to the subdirectory: `cd youtube-auto-publisher`
2. Follow the setup and environment configuration instructions in its local [README.md](youtube-auto-publisher/README.md).
3. The workflows [.github/workflows/youtube-bot.yml](.github/workflows/youtube-bot.yml) and [.github/workflows/quality-gate.yml](.github/workflows/quality-gate.yml) run within this context on GitHub Actions.
