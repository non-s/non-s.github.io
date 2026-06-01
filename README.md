# Wild Brief - Animal Shorts Bot (YouTube)

[![Refresh animal queue](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml)
[![YouTube Bot - Shorts only](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml)

Automated pipeline that turns Pexels animal footage into vertical YouTube Shorts with original voice-over narration and publishes through the official YouTube Data API.

- Cadence: **5 Shorts/day**, posted at 01, 14, 17, 22 and 23 UTC.
- Duration target: **25-35 seconds**.
- Category: YouTube **Pets & Animals** (`categoryId=15`).

## Pipeline

```text
Pexels clips -> fetch_animals.py -> _data/stories_queue.json
             -> generate_shorts.py -> _videos/*.mp4 + metadata
             -> upload_youtube.py -> YouTube Shorts + .done sidecar
```

## Required secrets

- `MISTRAL_API_KEY`
- `PEXELS_API_KEY` or `PEXELS`
- `YOUTUBE_TOKEN`

`YOUTUBE_TOKEN` is an OAuth JSON token, not an API key. Generate it once with `auth_youtube.py` or the `Build auth_youtube.exe (Windows)` workflow. See [SETUP.md](SETUP.md).
