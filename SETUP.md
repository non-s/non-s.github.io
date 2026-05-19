# Wild Brief — Setup Guide

Every secret + every optional free service the pipeline can use, in
order of importance.

The shortest path to a publishing channel is **§1 (3 secrets)** —
everything in §2 is opt-in and adds redundancy, retention, or
discovery breadth.

---

## 1. Required — without these, nothing publishes

### 1.1 Mistral La Plateforme API key

Primary AI provider for the fun-fact narration script. Free tier:
500 k tokens/month.

1. Sign up at <https://console.mistral.ai> (no credit card).
2. Generate an API key in **API Keys** → **Create new key**.
3. Add it as `MISTRAL_API_KEY` under
   **Settings → Secrets and variables → Actions → New repository secret**.

### 1.2 Pexels API key

Discovery + b-roll. Every Short is a real Pexels animal clip + AI
narration on top. Without this key the pipeline returns exit 2 and no
queue is produced. Free tier: 200 req/h, 20 k req/month.

1. Sign up at <https://www.pexels.com/api/new/>.
2. Copy the key from your dashboard.
3. Add as `PEXELS_API_KEY` (or `PEXELS` short form) on GitHub.

### 1.3 YouTube OAuth token

1. Set up a Google Cloud OAuth client (Desktop type):
   <https://console.cloud.google.com/apis/credentials>.
2. Enable the **YouTube Data API v3** AND the **YouTube Analytics
   API** for the project.
3. Download `client_secret.json` and drop it in the repo root locally.
4. Run `python auth_youtube.py` locally. It opens a browser, you log
   in with the YouTube account that owns the channel, and approve the
   requested scopes:
     - `youtube.upload` (uploads)
     - `youtube` (playlists)
     - `youtube.force-ssl` (pinned comments)
     - `youtube.readonly` + `yt-analytics.readonly` (analytics)
5. The script writes `token.json` — paste its entire contents as a
   single-line string into the GitHub secret `YOUTUBE_TOKEN`.

> **If you ever see `invalid_scope: Bad Request` in a workflow log**,
> the token was minted with an older scope list. Re-run
> `auth_youtube.py` and update the secret.

---

## 2. Recommended — free, opt-in upgrades

### 2.1 AI fallback chain (zero-cost reliability)

When Mistral rate-limits or 5xxs (and it will — free-tier is bursty),
the chain falls through to the first configured alternative. Each one
is a separate free tier; configuring even one of them lifts the
runs-per-day floor dramatically.

| Provider | Free tier | Sign-up | Secret name |
|----------|-----------|---------|-------------|
| Cerebras | 1 M tokens/day | <https://cloud.cerebras.ai> | `CEREBRAS_API_KEY` or `CEREBRAS` |
| Gemini | 1,500 req/day on flash-lite | <https://aistudio.google.com/apikey> | `GEMINI_API_KEY` or `GEMINI` |
| Groq | ~14 k req/day | <https://console.groq.com> | `GROQ_API_KEY` or `GROQ` |

Chain order is dynamic — `utils/provider_stats.py` reorders by recent
success rate every run, and a 429-burst on the primary trips the
in-run circuit breaker so later stories skip the dead provider entirely.

### 2.2 Burned-in captions (Groq Whisper — recommended)

Word-level captions lift Shorts retention by ~ 18 % (muted autoplay).
Groq Whisper is free, sub-second, 2 k req/day — set the same
`GROQ_API_KEY` from §2.1 and captions just turn on. Without it the
workflow falls back to local `faster-whisper` which works but takes
~ 10× longer per Short.

### 2.3 GitHub Pages dashboard (free)

`dashboard.yml` deploys nightly to GitHub Pages at
`https://<owner>.github.io/<repo>/` with top performers, retention by
category, A/B winners, cohort timing recommendations.

1. **Settings → Pages → Source: GitHub Actions** on the repo.
2. The dashboard workflow does the rest — no extra secret.

### 2.4 Token-saving defaults (already on)

- AI disk cache at `_data/ai_cache.jsonl` — same prompt → same answer
  for 30 days. Saves 60-80 % of Mistral calls on the 3-hour cron.
- Pexels b-roll cache at `_data/broll_cache/` — same query → same
  clip list for 7 days.
- AI provider stats at `_data/provider_stats.jsonl` — informs the
  fallback chain ordering.

---

## 3. What runs when

| Workflow | Schedule (UTC) | Purpose |
|----------|----------------|---------|
| `fetch-content.yml` | every 3 h | Pexels search + AI enrich → queue |
| `youtube-bot.yml` | 00 / 05 / 10 / 15 / 20 | 1 Short per run × 5 runs = 5 Shorts/day |
| `analytics.yml` | 03 daily | Pull retention + CTR per video |
| `daily-digest.yml` | 04 daily | Post GitHub Issue summarising the day |
| `dashboard.yml` | nightly | Rebuild static HTML dashboard on Pages |
| `comment-replies.yml` | every 6 h | Auto-reply to top-level viewer comments |
| `velocity-snapshot.yml` | every 2 h | +2 h / +6 h / +24 h view counts |
| `cleanup-branches.yml` | weekly | Delete merged `claude/*` branches |

All workflows share the `main-write` concurrency group so they
serialise on git push.

---

## 4. YouTube quota math

The Data API daily budget is **10,000 units**. Per Short upload:

| Call | Units |
|------|-------|
| `videos.insert` | 1,600 |
| `thumbnails.set` | 50 |
| `playlistItems.insert` | 50 |
| `commentThreads.insert` (pinned comment) | 50 |
| **Total per Short** | **~1,750** |

Sustainable Shorts/day at default config:

| Shorts/day | Units used | % of cap |
|------------|------------|----------|
| 3 | 5,250 | 52 % |
| 4 | 7,000 | 70 % |
| **5 (default)** | **8,750** | **87 % — safe ceiling** |
| 6 | 10,500 | 105 % — risk of cap-out |
| 8 (every 3 h) | 14,000 | **140 % — will fail** |

To go above 5/day, request a quota increase via the
[YouTube API Compliance form](https://support.google.com/youtube/contact/yt_api_form)
(free, 1-2 weeks). Approved projects routinely get 1 M units/day.

---

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `❌ PEXELS_API_KEY not set` | Secret missing | Add it (§1.2) |
| `invalid_scope: Bad Request` | Stale OAuth token | Re-run `auth_youtube.py`, update `YOUTUBE_TOKEN` |
| `Mistral rate limited (429)` storm | Free-tier quota hit | Configure one fallback (§2.1) — the in-run circuit breaker now opens after 3 give-ups and routes around Mistral |
| Workflow timeout at 25 min | Same as above | Same fix |
| Static Short (no motion) | All b-roll sources returned 0 | Check the `🔎 B-roll sources:` log line — it tells you which source failed. Verify Pexels key, or extend `ANIMAL_TOPICS` queries |
| Channel publishes 1 Short then stops | Poison-pill `.json` in `_videos/` | Run `git rm _videos/short-*.json` (the `.done` sidecars stay) and re-trigger the bot |

For anything else, check the workflow log via Actions → workflow run
→ Artifacts → download the log zip.

---

## 6. Operator hygiene

- **Never commit `token.json`** — `.gitignore` already excludes it,
  but watch for accidental adds.
- **Never push directly to `main`** if you're prototyping new content
  topics; use a `claude/*` branch + PR.
- **Roll the YouTube OAuth token every 6 months** — Google rotates
  refresh-tokens silently on inactivity.
- **Watch the YouTube quota ledger** — `_data/quota_log.jsonl` records
  every Data API call. The workflow summary surfaces the daily total
  and warns at 80 %.

That's all that's required to operate Wild Brief end-to-end.
