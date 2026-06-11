# Wild Brief - Nature Science Shorts Bot (YouTube)

[![Production quality gate](https://github.com/non-s/non-s.github.io/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/quality-gate.yml)
[![Refresh animal queue](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml)
[![YouTube Bot - Shorts only](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml)

Automated pipeline that turns vetted nature footage into vertical YouTube Shorts with original voice-over narration and publishes through the official YouTube Data API.

- Cadence: the workflow evaluates **05:23, 14:23, 19:23 and 23:23 UTC**.
  `utils/publish_schedule.py` is the source of truth for adaptive publish vs
  safe skip, and every slot writes `_data/publish_slot_decisions.jsonl`.
- Duration target: **12-18 seconds**, biased toward high completion rate.
- Category: YouTube **Science & Technology** (`categoryId=28`).
- Programming: animals, plants, trees, fungi, oceans, rivers, mountains, forests, volcanoes, weather, rare natural phenomena, geology, ecosystems, Earth from space, conservation and discoveries.

## Pipeline

```text
Pexels + Pixabay clips -> nature taxonomy + enrichment -> fetch_animals.py
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

## World-class upgrade track

The operating model is now documented in
[docs/WILD_BRIEF_WORLD_CLASS_UPGRADE.md](docs/WILD_BRIEF_WORLD_CLASS_UPGRADE.md).
The master-prompt implementation is complete across the production path:
rulebook preflight, curiosity and swipe scoring, rendered loop callbacks,
expanded A/B axes, live variant logging, extended analytics warehouse files,
weekly decisions, free signal harvesting, post-upload session ops, dashboard
sections, CI smoke checks and optional zero-cost fallbacks are all wired without
replacing the current queue, render, upload or official YouTube APIs.

## Required secrets

- `PEXELS_API_KEY` or `PEXELS`
- `YOUTUBE_TOKEN`
- At least one AI text provider:
  `MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY` or `GROQ_API_KEY`

Recommended free quality extensions:

- `PIXABAY_API_KEY` or `PIXABAY`
- `GEMINI_API_KEY` or `GEMINI`
- `AUDIO_LIBRARY_MANIFEST` for operator-curated YouTube Audio Library files
- `COQUI_TTS_COMMAND` for a local TTS fallback if Edge TTS fails

GBIF and Wikimedia Commons enrichment do not require secrets.
See [WILD_BRIEF_GROWTH_PLAN.md](WILD_BRIEF_GROWTH_PLAN.md) for the current channel transformation plan.

AI image generation is intentionally disabled because current free-tier
availability is not reliable enough for the zero-cost goal.

`YOUTUBE_TOKEN` is an OAuth JSON token, not an API key. Generate it once with `auth_youtube.py` or the `Build auth_youtube.exe (Windows)` workflow. See [SETUP.md](SETUP.md).
