# GlobalBR News — Setup Guide

Everything required to run the pipeline + everything optional you can
turn on later. All steps are **free**, none require a credit card
unless explicitly noted (only Turso's most generous tier asks for one,
and the alternative is also free).

---

## 1. Required — without these, nothing publishes

### 1.1 Mistral La Plateforme API key

1. Create a free account at <https://console.mistral.ai>
2. Settings → API keys → Create new key
3. Copy the key
4. In this repo: **Settings → Secrets and variables → Actions** →
   New repository secret → name `MISTRAL_API_KEY`, paste the key

Free tier: ~500k tokens/month, 1 request/second. The pipeline throttles
to one call per 8 s to stay well under the limit.

### 1.2 YouTube OAuth token

1. Locally, clone the repo and install deps:
   ```bash
   pip install -r requirements.txt
   ```
2. Create an OAuth client in Google Cloud Console:
   - <https://console.cloud.google.com/apis/credentials>
   - Create project → Enable YouTube Data API v3 + YouTube Analytics API
   - OAuth consent screen → External → fill the required fields →
     add scopes:
     - `https://www.googleapis.com/auth/youtube.upload`
     - `https://www.googleapis.com/auth/youtube`            (playlists+comments)
     - `https://www.googleapis.com/auth/youtube.readonly`   (analytics workflow)
     - `https://www.googleapis.com/auth/yt-analytics.readonly`
   - Credentials → Create credentials → OAuth client ID → Desktop app
   - Download the JSON → save it as `client_secret.json` in the repo root
3. Run the local helper:
   ```bash
   python auth_youtube.py
   ```
   This opens a browser, asks you to sign in with the channel's Google
   account, and writes `token.json` next to `client_secret.json`.
4. Copy the **entire contents** of `token.json` (it's small, one line of JSON).
5. In this repo: **Settings → Secrets and variables → Actions** →
   New repository secret → name `YOUTUBE_TOKEN`, paste the JSON.

The refresh token inside doesn't normally expire — one-time setup. If
YouTube ever invalidates it, just re-run `auth_youtube.py` and update
the secret.

---

## 2. Recommended — free, opt-in upgrades

### 2.1 Cerebras AI fallback (1M tokens/day free)

When Mistral rate-limits you ([happens on bursty hours](https://docs.mistral.ai/deployment/laplateforme/rate_limits/)), the pipeline currently drops those stories silently. Cerebras adds a 1M tokens/DAY parachute that fires automatically.

1. Sign up at <https://cloud.cerebras.ai> (Google or GitHub login,
   no credit card)
2. Generate an API key in the dashboard
3. In this repo: add secret `CEREBRAS_API_KEY` with the value

Verify it's working: in `fetch-news.log` after a Mistral 429,
you should see `"Falling back to Cerebras after Mistral 429"`.
Without the key, the pipeline simply skips the failover (same
behaviour as before Phase 3 of the audit).

---

## 3. Future — needs external infra setup

These give the project room to grow but require accounts/services
outside GitHub. None of them is required for the channel to publish
its 3 Shorts/day.

### 3.1 Turso for queue state (replaces git-as-DB)

Today `_data/stories_queue.json` is committed back to the repo on every
fetch-news run. Works, but pollutes `git log` and grows the repo over
time. Turso is a free SQLite-over-HTTP service (500M reads/mo, 25M
writes/mo, 5 GB) that lets us keep state out of git.

1. Sign up at <https://app.turso.tech> with GitHub (no credit card)
2. `brew install tursodatabase/tap/turso` or [other installs](https://docs.turso.tech/cli/installation)
3. ```bash
   turso db create globalbr
   turso db tokens create globalbr
   ```
4. Add two repo secrets:
   - `TURSO_DATABASE_URL` (output of `turso db show --url globalbr`)
   - `TURSO_AUTH_TOKEN` (the token from step 3)

The code to actually use Turso isn't wired in yet — when you decide
to migrate, the adapter slot is in `fetch_news.py::_load_queue` /
`_save_queue` and `generate_shorts.py` mirror functions.

### 3.2 Oracle Cloud Always Free — VM for 24/7 use

If you ever want a live stream (FFmpeg pushing RTMP to YouTube 24/7),
GitHub Actions is **not** an option — jobs cap at 6 hours. Oracle's
"Always Free" tier gives a parrudo VM (4 vCPU ARM Ampere + 24 GB RAM,
10 TB outbound/month) **for life, no time limit**.

1. Sign up at <https://www.oracle.com/cloud/free/> with a card
   (Oracle uses it for ID verification, **never charges**)
2. Wait 1-3 business days for the account to be approved
3. Create Compute → Instance → shape `VM.Standard.A1.Flex`
   (4 OCPU / 24 GB), Ubuntu 22.04
4. Open ports 1935 (RTMP) and 443 (HTTPS) on the security list
5. SSH in, install ffmpeg + nginx-rtmp (or just ffmpeg push to YouTube
   directly)

This unlocks future Phase: 24/7 news loop live stream.

### 3.3 Meta Graph API — cross-post Reels to IG + FB

Same MP4 we upload to YouTube can go to Instagram Reels and Facebook
Reels via the Meta Graph API. Free. Requires a Facebook Business
account.

1. <https://developers.facebook.com> → Create App → Business type
2. Add Instagram Graph API + Facebook Graph API products
3. Connect a Facebook Page to your Instagram account (must be
   Business or Creator type — personal IG accounts can't post via API)
4. Generate a Page access token with `instagram_basic`,
   `instagram_content_publish`, `pages_show_list` scopes
5. Add repo secrets:
   - `META_PAGE_ID`
   - `META_IG_USER_ID`
   - `META_PAGE_TOKEN` (long-lived, 60-day; refresh script needed
     before expiry)

Hard limits to know:
- IG Reels via API: **100 posts / 24 h** per account (Phyllo, 2026)
- Only Business / Creator IG accounts (personal blocked)
- MP4 must already be embedded with its audio — IG API doesn't
  apply music

When you're ready to wire this, the workflow stub goes in
`.github/workflows/crosspost.yml`; it triggers off
`workflow_run: youtube-bot success`.

### 3.4 TikTok — needs manual audit

The TikTok Content Posting API works, but **unaudited apps can only
post `SELF_ONLY` (private)** — useless for a public channel. The
audit is a manual process, takes weeks, and isn't worth chasing until
the IG/FB cross-post is proven. Skip until then.

---

## 4. What runs when

| Workflow | Cron (UTC) | Cost (YouTube units) | Cost (Actions min) |
|--|--|--|--|
| `fetch-news` | every 3h | 0 | ~5 min/run × 8 = 40 min/day |
| `youtube-bot` | 08, 14, 20 | 3 × 1,650 = **4,950**/day | ~5 min/run × 3 = 15 min/day |
| `analytics` | 03 | 0 (separate Analytics quota) | ~2 min |
| `cleanup-branches` | Sun 04 | 0 | ~1 min/week |

Public repo = unlimited Actions minutes, so the only hard ceiling
is the YouTube Data API daily quota (**10,000**). We use roughly
half. Bumping to 5 Shorts/day would put us at 8,250/day — safe.
Above that, you'd need a Google quota increase request.

---

## 5. Troubleshooting

**`fetch_news` runs but `_data/stories_queue.json` stays empty.**
- Check the run log for `Mistral rate limited` → set `CEREBRAS_API_KEY`
- Check for `quality_check rejected` patterns → tune
  `FETCH_QUALITY_THRESHOLD` (default 6) lower

**`youtube-bot` reports `0 Shorts uploaded today`.**
- Workflow exits non-zero now (Phase 1 fix) so it shows red in Actions.
- Check `generate_shorts.log` artifact: if TTS / Pollinations
  failed for every story, that's an upstream outage. The job will
  retry naturally on the next scheduled run.

**`analytics.yml` fails with `403`.**
- Token doesn't have `yt-analytics.readonly`. Re-run
  `auth_youtube.py` after adding the scope in Google Cloud Console.

**First comment doesn't appear under uploads.**
- The channel-owner account must have **community-tab eligibility**
  for the comment API to work without 403. Below 500 subscribers,
  comments still post but you can't pin them programmatically.
