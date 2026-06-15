# Wild Brief - Nature Science Shorts Bot (YouTube)

[![Production quality gate](https://github.com/non-s/non-s.github.io/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/quality-gate.yml)
[![Refresh Pexels queue](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml)
[![YouTube Bot - Shorts only](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml)

Automated pipeline that turns curated Pexels nature and science footage into vertical YouTube Shorts with original voice-over narration and publishes through the official YouTube Data API.

- Cadence: the workflow evaluates **one slot per hour, 00:00 through
  23:00 UTC**, for a 24/day publishing grid when quality and quota allow it.
  Canonical slots: `00:00`, `01:00`, `02:00`, `03:00`, `04:00`, `05:00`,
  `06:00`, `07:00`, `08:00`, `09:00`, `10:00`, `11:00`, `12:00`, `13:00`,
  `14:00`, `15:00`, `16:00`, `17:00`, `18:00`, `19:00`, `20:00`, `21:00`,
  `22:00` and `23:00`.
  `utils/publish_schedule.py` is the source of truth for adaptive publish vs
  safe skip, and every slot writes `_data/publish_slot_decisions.jsonl`.
  Metadata also carries `publish_ts_utc`, `publish_day_pt`, `quota_day_pt`
  and `views_regime` so UTC operations and Pacific-time YouTube quota/analytics
  semantics stay aligned.
- Duration target: **12-18 seconds**, biased toward high completion rate.
- Category: YouTube **Science & Technology** (`categoryId=28`).
- Programming: animals, plants, trees, fungi, oceans, rivers, mountains, forests, volcanoes, weather, rare natural phenomena, geology, ecosystems, Earth from space, astronomy, physics, chemistry, microscopy, conservation and discoveries.

## Pipeline

```text
Pexels clips -> nature taxonomy + enrichment -> fetch_animals.py
             -> _data/stories_queue.json
             -> generate_shorts.py -> _videos/*.mp4 + metadata
             -> upload_youtube.py -> YouTube Shorts + .done sidecar
             -> analyze_channel.py -> free public performance feedback
```

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

- `YOUTUBE_TOKEN`
- `PEXELS_API_KEY` or legacy secret name `PEXELS`
- At least one AI text provider:
  `MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY` or `GROQ_API_KEY`

Recommended free quality extensions:

- `GEMINI_API_KEY` or `GEMINI`
- `AUDIO_LIBRARY_MANIFEST` for operator-curated YouTube Audio Library files
- `COQUI_TTS_COMMAND` for a local TTS fallback if Edge TTS fails

GBIF and Wikimedia Commons enrichment do not require secrets. Pexels is the
default and only active visual source through `BROLL_SOURCE_MODE=pexels`.
Internet Archive video remains an explicit opt-in research path only; it is not
used by the production queue or publisher.
See [WILD_BRIEF_GROWTH_PLAN.md](WILD_BRIEF_GROWTH_PLAN.md) for the current channel transformation plan.

AI image generation is intentionally disabled because current free-tier
availability is not reliable enough for the zero-cost goal.

`YOUTUBE_TOKEN` is an OAuth JSON token, not an API key. Generate it once with `auth_youtube.py` or the `Build auth_youtube.exe (Windows)` workflow. See [SETUP.md](SETUP.md).
