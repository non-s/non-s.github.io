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
upload_youtube.py             -> YouTube Shorts + .done sidecar
scripts/live_stream_dynamic.py -> 24/7 YouTube Live relay (one clip
                                   looped + the whole local bgm playlist
                                   on loop, like a real lofi radio -- not
                                   several clips cut together)
```

The b-roll/bgm libraries (`_assets/video/lofi_broll`, `_assets/audio/bgm`)
are gitignored and persist across ephemeral runners via GitHub Actions
cache (`actions/cache`, key `lofi-media-*`) instead of git, so the Jamendo
library grows toward its ~150-track target over many runs instead of
resetting to empty every time. The live relay streams straight to RTMP
with `-stream_loop -1` on both the video clip and the audio playlist --
there is no bake-to-file step, so a crash/restart is back on air within
seconds regardless of playlist size. The looped clip is preprocessed once
with a short crossfade baked between its tail and head so the loop
wrap-around has no visible jump cut.

This channel was rebuilt from an earlier nature-science-facts format
(narrated Shorts, editorial scoring pipeline, trend hijacking, a story
queue). That pipeline and its supporting scripts/docs have been removed
now that the channel has fully moved to the lofi format; a handful of
shared modules (b-roll fetching, upload, media lifecycle) survived the
cleanup because the lofi pipeline still uses them.

Basic view/watch-time analytics come from manual YouTube Studio CSV
exports via `studio-reach-import.yml` and `reporting-backfill.yml`, and
are rendered on the `dashboard.yml` status page.

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
