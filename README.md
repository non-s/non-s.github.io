# Wild Brief - Animal Shorts Bot (YouTube)

[![Production quality gate](https://github.com/non-s/non-s.github.io/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/quality-gate.yml)
[![Refresh animal queue](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml)
[![YouTube Bot - Shorts only](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml)

Automated pipeline that turns Pexels animal footage into vertical YouTube Shorts with original voice-over narration and publishes through the official YouTube Data API.

- Cadence: **3 Shorts/day**, posted at 14:23, 19:23 and 23:23 UTC.
- Duration target: **25-35 seconds**.
- Category: YouTube **Pets & Animals** (`categoryId=15`).

## Pipeline

```text
Pexels clips -> fetch_animals.py -> _data/stories_queue.json
             -> generate_shorts.py -> _videos/*.mp4 + metadata
             -> upload_youtube.py -> YouTube Shorts + .done sidecar
             -> analyze_channel.py -> free public performance feedback
```

## Editorial system

Every candidate passes through an automated editor-in-chief before rendering:

- ranks specific animal stories by editorial quality;
- blocks weak scripts and subjects repeated inside a three-day cooldown;
- organizes videos into recurring series such as **Pet Secrets** and **Ocean Mysteries**;
- renders a readable 2-4 word cover inside the opening frame and an end-screen CTA for channel subscriptions;
- records public YouTube engagement after uploads and feeds winning categories, series and experiments back into the dashboard.

## Required secrets

- `MISTRAL_API_KEY`
- `PEXELS_API_KEY` or `PEXELS`
- `YOUTUBE_TOKEN`

`YOUTUBE_TOKEN` is an OAuth JSON token, not an API key. Generate it once with `auth_youtube.py` or the `Build auth_youtube.exe (Windows)` workflow. See [SETUP.md](SETUP.md).
