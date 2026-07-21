# Amber Hours - YouTube Setup

## Required GitHub secrets

Open **Settings -> Secrets and variables -> Actions** and add:

- `YOUTUBE_TOKEN`
- `PIXABAY_API_KEY` -- active lofi pipeline's visual source (anime/
  illustrated b-roll for Shorts, the mix, and the live loop)
- `YOUTUBE_STREAM_KEY` -- only needed for the 24/7 live relay
  (`live-stream.yml`)

The earlier nature-Shorts pipeline (`fetch-content.yml`,
`QUEUE_REFRESH_ENABLED`) used `PEXELS_API_KEY`/`PEXELS` and an AI text
provider key (`MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY` or
`GROQ_API_KEY`). That workflow, and the free-signal/TTS scripts that went
with it, were removed once the channel fully moved to lofi -- none of
those secrets or scripts are needed anymore.

## Create YouTube OAuth credentials

1. Open <https://console.cloud.google.com/>.
2. Create or select a Google Cloud project.
3. Enable **YouTube Data API v3** and **YouTube Analytics API**.
4. Configure the OAuth consent screen.
5. Create an OAuth client ID of type **Desktop app**.
6. Copy the client ID and client secret.

## Generate `YOUTUBE_TOKEN`

A plain API key cannot upload videos. Run:

```bash
pip install -r requirements.txt
python auth_youtube.py
```

Approve upload, YouTube read-only and read-only Analytics access in the browser, then paste the printed JSON into the `YOUTUBE_TOKEN` repository secret. Regenerate an older token once to add Analytics retention metrics and the full YouTube API intelligence layer.

If you downloaded the OAuth desktop-client JSON from Google Cloud and have `gh` authenticated, use the safer direct secret update:

```bash
python auth_youtube.py --client-secrets-file client_secret.json --set-github-secret
```

This writes `youtube_token.json` locally and updates the repository secret without printing the token JSON in the terminal.

Expected free scopes:

- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/youtube.readonly`
- `https://www.googleapis.com/auth/youtube.force-ssl`
- `https://www.googleapis.com/auth/yt-analytics.readonly`

The dashboard writes `_data/youtube_intelligence.json`. If it shows `youtube_readonly_scope_missing` or `youtube_analytics_scope_missing`, rerun `auth_youtube.py` and replace the `YOUTUBE_TOKEN` secret.

On Windows, you can instead run the **Build auth_youtube.exe (Windows)** workflow, download the artifact and execute `auth_youtube.exe`.

## Start publishing

1. Set the repository variable `YOUTUBE_PUBLISHING_ENABLED=1` when you are
   ready to resume automation -- every publishing/watchdog/health-check
   workflow gates on it, so this one variable turns the whole pipeline on
   or off.
2. Run `youtube-bot.yml` manually once (Shorts) to confirm auth/quota are
   working, then let its own schedule (`:02`, `:22`, `:42` hourly) take
   over.
3. Run `lofi-mix-daily.yml` manually once (the 1-hour horizontal mix),
   then let its daily schedule take over.
4. `live-stream.yml` needs `YOUTUBE_STREAM_KEY` set -- once it is,
   `live-stream-watchdog.yml` keeps the relay running on its own.
5. Optionally create the repository variable `YOUTUBE_PRIVACY`: `public`,
   `unlisted`, or `private`. Default: `public`.
6. Optionally set the repository variable `COMMUNITY_ENGAGEMENT_ENABLED=1`
   to turn on community engagement: `community-comment-replies.yml` replies
   to fresh top-level comments across the channel (official
   `commentThreads`/`comments` API, see `scripts/reply_to_comments.py`'s
   docstring for its dedup/spam/rate-limit guardrails), and
   `community-post-draft.yml` commits one ready-to-paste Community-tab post
   suggestion a week to `_data/community/suggested_post.json` -- the
   Community tab has no public API, so that one is paste-it-yourself, not
   automated. Independent of `YOUTUBE_PUBLISHING_ENABLED`: posting under the
   channel's identity is its own trust boundary. Optionally tune
   `COMMENT_REPLY_MAX_PER_RUN` (default 15).
7. Optionally set the repository variable `STORM_AMBIENCE_ENABLED=1` to turn
   on the second content pillar (real rain/thunder ambience -- see
   README.md's "Second pillar" section): `storm-ambience.yml` publishes
   long-form videos on its own twice-daily schedule and `storm-shorts.yml`
   publishes vertical Shorts every 2 hours, both gated by the same
   variable. Neither needs a new secret (both reuse `YOUTUBE_TOKEN`), and
   both can run whether or not `YOUTUBE_PUBLISHING_ENABLED` is on.
   Optionally tune `STORM_MIN_DURATION_MINUTES` /
   `STORM_MAX_DURATION_MINUTES` (default 45-75) and
   `STORM_MUSIC_LAYER_PROBABILITY` (default 0.35).
8. Optionally set `GEMINI_API_KEY` (or `CEREBRAS_API_KEY`/`GROQ_API_KEY`/
   `MISTRAL_API_KEY`) to let `utils/ai_titling.py` write each storm-pillar
   video's title, description and hashtags with AI instead of the template
   text -- Gemini is tried first when its key is set. With no key
   configured the storm pillar still works, just with template copy.
9. To switch the 24/7 live relay from the original lofi loop to the rain
   & thunder pillar, set the repository variable
   `LIVE_CONTENT_PILLAR=storm` (`live-stream.yml` reads it and passes it
   to `scripts/live_stream_dynamic.py`; the watchdog just relaunches
   `live-stream.yml`, so no separate change is needed there). Leave it
   unset (or `lofi`) to keep the original anime desk loop live.

See [RUNBOOK.md](RUNBOOK.md) for what each reliability workflow does and
what to do when one of them alerts.

## Optional zero-cost imports

- Shorts Reach: export the YouTube Studio reach table or a Google Sheets CSV
  containing viewed/stayed-to-watch and swiped-away columns, place it under
  `_data/studio_reach_exports/`, then run `python scripts/import_studio_reach_export.py`
  (or run `studio-reach-import.yml`).
- Reporting CSV backfill: place official Reporting API CSV exports under
  `_data/reporting_import/`, run `python scripts/reporting_bootstrap.py`, then
  `python scripts/reporting_pull.py`. This is also what feeds
  `utils/broll_performance.py`'s real-performance b-roll weighting once
  there's enough data.

All optional imports degrade safely when their source files are missing.
