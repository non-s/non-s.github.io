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

### 2.1 AI fallback chain (zero-cost reliability)

When Mistral rate-limits you ([happens on bursty hours](https://docs.mistral.ai/deployment/laplateforme/rate_limits/)), every Mistral-only pipeline drops the affected story silently. We avoid that with a chain of free-tier providers — configure **any** of them (or all) and the pipeline tries them in order before giving up:

| Provider | Free tier | Sign up | Secret |
|----------|-----------|---------|--------|
| **Cerebras** | 1M tokens/DAY, OpenAI-compatible | <https://cloud.cerebras.ai> | `CEREBRAS_API_KEY` |
| **Google Gemini** | 15 RPM, 1,500 req/DAY (flash-lite) | <https://aistudio.google.com/apikey> | `GEMINI_API_KEY` |
| **Groq** | ~14k req/DAY, very fast inference | <https://console.groq.com> | `GROQ_API_KEY` |

None require a credit card. After Mistral exhausts its retries on a
429 / 5xx / network error, the chain tries Cerebras → Gemini → Groq
in order. First successful response wins. Verify a fallback fired:
`fetch-news.log` will show `"Falling back to Cerebras|Gemini|Groq
after Mistral …"`.

Configuring at least one fallback is highly recommended — without it,
a single Mistral hiccup drops the affected stories for the day.

### 2.2 Public-source discovery (already on, free, no key)

The pipeline pulls additional candidate stories from Reddit (curated
news subs), Hacker News, Wikipedia Current Events, Google Trends
(daily search) and GDELT (global news index) on every fetch-news run.
All free, no auth, no extra secrets. Disable with `FETCH_INCLUDE_PUBLIC=0`
or `FETCH_INCLUDE_TRENDS=0` if you ever need to.

Google Trends doubles as a search-bias signal: any RSS story whose
title mentions a currently-trending keyword gets a +1 or +2 boost on
the AI ranker score, which lifts timely stories over evergreen ones.

### 2.3 Free image fallback chain

When a story has no embedded image and Pollinations rate-limits the
AI background generator, the Shorts renderer now tries (free, no key):

  1. Open Graph image scraped from the source article URL
  2. Wikipedia REST API thumbnail for any named entity in the title
  3. Openverse Creative-Commons image search

This makes "no background available → drop the Short" much rarer.

### 2.4 Token-saving defaults (already on)

Three knobs cut AI quota use without changing output quality:

  - **Disk cache** (`utils/ai_cache.py`): hashes the full prompt + model
    + json_mode flag and stores answers in `_data/ai_cache.jsonl` with a
    30-day TTL. Re-encountering the same story across the 3h cron
    cadence returns instantly from disk. Self-invalidates on prompt
    template changes (hash differs). Toggle with `AI_CACHE_ENABLED=0`.
  - **Pre-AI relevance gate** (`FETCH_RELEVANCE_MIN_AI`, default `3.0`):
    drops headlines with `entry_relevance_score < 3` before any AI call.
    Eliminates clickbait, short headlines, image-less wire copy.
  - **Prompt injection defense** (`utils/prompt_safety.py`): strips
    "ignore previous instructions", system-tag forgery, and other
    common jailbreak patterns from RSS-borne text before it reaches the
    LLM. Combined with explicit system-prompt instructions that field
    values are untrusted data.

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
