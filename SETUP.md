# Wild Brief - YouTube Setup

## Required GitHub secrets

Open **Settings -> Secrets and variables -> Actions** and add:

- `YOUTUBE_TOKEN`
- `PEXELS_API_KEY` or legacy secret name `PEXELS`
- At least one AI text provider:
  `MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY` or `GROQ_API_KEY`

Recommended free quality extensions:

- `GEMINI_API_KEY` or `GEMINI`

Pexels is the production visual source. Set `BROLL_SOURCE_MODE=pexels` and add
the free `PEXELS_API_KEY` secret. The workflows also accept the existing
legacy name `PEXELS`. GBIF and Wikimedia Commons need no key. AI image
generation is not enabled because the project is optimized for zero-cost
operation.

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

1. Set repository variables `QUEUE_REFRESH_ENABLED=1` and `YOUTUBE_PUBLISHING_ENABLED=1` when you are ready to resume automation.
2. Run `fetch-content.yml` manually.
3. Run `youtube-bot.yml` manually.
4. Optionally create the repository variable `YOUTUBE_PRIVACY`: `public`, `unlisted`, or `private`. Default: `public`.

## Optional zero-cost imports

- Shorts Reach: export the YouTube Studio reach table or a Google Sheets CSV
  containing viewed/stayed-to-watch and swiped-away columns, place it under
  `_data/studio_reach_exports/`, then run `python scripts/import_studio_reach_export.py`.
- Reporting CSV backfill: place official Reporting API CSV exports under
  `_data/reporting_import/`, run `python scripts/reporting_bootstrap.py`, then
  `python scripts/reporting_pull.py`.
- Free freshness signals: place public Google Trends CSV/JSON snapshots under
  `_data/trends/manual_import/` or set `WILD_BRIEF_RSS_URLS`, then run
  `python scripts/free_signal_harvester.py` and `python scripts/apply_topic_freshness.py`.
- Local TTS fallback: set `COQUI_TTS_COMMAND` and check it with
  `python scripts/tts_healthcheck.py --no-synth --json`.

All optional imports degrade safely when their source files are missing.
