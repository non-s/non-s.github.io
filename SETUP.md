# Amber Hours - YouTube Setup

## Required GitHub secrets

Open **Settings -> Secrets and variables -> Actions** and add:

- `YOUTUBE_TOKEN`
- `PIXABAY_API_KEY` -- real storm/rain b-roll footage for the long-form
  video, the Shorts, and the live loop (`scripts/sync_storm_broll.py`);
  falls back to the illustrated pinned scene if missing
- `YOUTUBE_STREAM_KEY` -- only needed for the 24/7 live relay
  (`live-stream.yml`)
- `YOUTUBE_STREAM_KEY_CLASSICAL` -- only needed for the classical
  pillar's own 24/7 live relay (`live-stream-classical.yml`) -- a
  second, separate persistent stream created in YouTube Studio, not the
  same key as `YOUTUBE_STREAM_KEY` above

The earlier nature-Shorts pipeline (`fetch-content.yml`,
`QUEUE_REFRESH_ENABLED`) used `PEXELS_API_KEY`/`PEXELS` and an AI text
provider key (`MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY` or
`GROQ_API_KEY`). That workflow, and the free-signal/TTS scripts that went
with it, were removed once the channel moved to lofi, and later the
lofi format itself was removed when the channel pivoted fully to the
rain & thunder ambience pillar (growth pass, 2026-07-21) -- none of
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
   ready to resume automation -- every general publishing/health-check
   workflow gates on it, so this one variable turns those on or off.
2. Set the repository variable `STORM_AMBIENCE_ENABLED=1` to turn on the
   channel's one content pillar (real rain/thunder ambience -- see
   README.md): `storm-ambience.yml` publishes a ~1-hour long-form video
   twice a day and `storm-shorts.yml` publishes vertical Shorts every 2
   hours, both gated by this variable, independent of
   `YOUTUBE_PUBLISHING_ENABLED`. Neither needs a new secret beyond
   `YOUTUBE_TOKEN` -- each format loops one fixed, hand-picked real
   Pixabay clip committed in the repo, falling back to the illustrated
   pinned scene only if that file is ever missing.
   Optionally tune `STORM_MIN_DURATION_MINUTES` / `STORM_MAX_DURATION_MINUTES`
   (default 45-75, tighten toward exactly 1 hour with e.g. 55/65).
3. `live-stream.yml` needs `YOUTUBE_STREAM_KEY` set -- once it is,
   `live-stream-watchdog.yml` keeps the relay running on its own, looping
   the pinned storm scene under the synthesized rain/thunder bed.
3b. Optionally set the repository variable `CUTE_ANIMALS_ENABLED=1` to
   turn on the second, independent "Pata Jazz" cute-animal Shorts pillar
   (see README.md) -- off by default. Needs no new secret beyond
   `YOUTUBE_TOKEN`/`PIXABAY_API_KEY` (already required above); Jamendo
   jazz sync needs no secret, same as the rain pillar's earlier Jamendo
   integration. Runs on its own conservative 8/day cadence
   (`cute-animals-shorts.yml`'s cron) -- see README.md's "Cadence" note
   for why this is deliberately not the higher frequency originally
   considered, and edit that workflow's cron directly to change it.
3c. Optionally set the repository variable `BABY_NOISE_ENABLED=1` to turn
   on the third, independent white/pink/brown-noise pillar (see README.md)
   -- off by default. Needs no new secret beyond `YOUTUBE_TOKEN`/
   `PIXABAY_API_KEY` (already required above); the noise audio itself is
   procedurally synthesized, no external dependency at all. Runs on its
   own conservative cadence (long-form once/day, Shorts every 4 hours --
   `baby-noise-ambience.yml`/`baby-noise-shorts.yml`'s crons). Optionally
   tune `BABY_NOISE_MIN_DURATION_MINUTES`/`BABY_NOISE_MAX_DURATION_MINUTES`
   (default 180-300, i.e. 3-5 hours). **Read README.md's "Which pillars
   can run together?" note before enabling this alongside the other two
   pillars** -- all three share one account-level YouTube upload cap, and
   running everything's full designed cadence at once will very likely
   exceed it.
3d. Optionally set the repository variable `CLASSICAL_AMBIENCE_ENABLED=1`
   to turn on the fourth, independent classical/orchestral/piano pillar
   (see README.md) -- off by default, published in English as "Amber
   Hours Classical". Needs no new secret beyond `YOUTUBE_TOKEN` (Jamendo
   needs no secret, same as every other pillar's Jamendo integration).
   Runs hourly (~24/day, `classical-ambience.yml`'s cron) -- see
   README.md's cadence note for why this pillar's cadence was chosen
   assuming the other three are disabled, not as something to layer on
   top of them. Separately, set `CLASSICAL_LIVE_ENABLED=1` to turn on
   this pillar's own 24/7 live relay (`live-stream-classical.yml`) -- it
   needs its own **new** secret, `YOUTUBE_STREAM_KEY_CLASSICAL`: create a
   second persistent live stream in YouTube Studio (Go Live -> Stream,
   not the same stream used for the rain pillar's live) and paste that
   stream key in. **Read README.md's "Which pillars can run together?"
   note before enabling this alongside any other pillar.**
4. Optionally create the repository variable `YOUTUBE_PRIVACY`: `public`,
   `unlisted`, or `private`. Default: `public`.
5. Optionally set the repository variable `COMMUNITY_ENGAGEMENT_ENABLED=1`
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
6. Optionally set `GEMINI_API_KEY` (or `CEREBRAS_API_KEY`/`GROQ_API_KEY`/
   `MISTRAL_API_KEY`) to let `utils/ai_titling.py` write each video's
   title, description and hashtags with AI instead of the template text --
   Gemini is tried first when its key is set. With no key configured the
   pipeline still works, just with template copy.

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
