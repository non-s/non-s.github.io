# Wild Brief — Setup Guide (TikTok)

Every secret + every optional free service the pipeline can use, in
order of importance.

The shortest path to a publishing channel is **§1 (5 secrets)** —
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

### 1.3 TikTok developer app

1. Go to <https://developers.tiktok.com/> and sign in with the TikTok
   account that owns the channel (here: `@wildbrief_x`).
2. Click **Manage apps → Connect an app**. Pick a name (e.g.
   "Wild Brief Bot"), upload an icon, fill the description.
3. Under **Add products**, enable BOTH:
     - **Login Kit** (OAuth 2.0)
     - **Content Posting API** — and toggle on:
         * `video.publish` (Direct Post)
         * `video.upload` (Inbox fallback)
         * `user.info.basic`
         * `video.list`
4. Under **App configuration → Redirect URI** add
   `http://localhost:8080/callback` (matches `auth_tiktok.py`).
5. Submit the app for review. While it's pending you can still test
   in sandbox mode — the bot supports `TIKTOK_PUBLISH_MODE=inbox` so
   it drops drafts in your TikTok app for you to finalize from the
   phone.
6. From **App details** copy the **Client key** and **Client secret**
   and add them as GitHub secrets:
     - `TIKTOK_CLIENT_KEY`
     - `TIKTOK_CLIENT_SECRET`

### 1.4 TikTok OAuth token

1. Locally export the credentials and run the auth helper:

   ```bash
   export TIKTOK_CLIENT_KEY=awxxxxxxxxxx
   export TIKTOK_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   python auth_tiktok.py
   ```

2. A browser opens, you log in with the channel's TikTok account, and
   approve the requested scopes. The script writes `tiktok_token.json`.
3. Paste the entire file contents as a single-line string into the
   GitHub secret `TIKTOK_TOKEN`.

> **If you ever see `invalid_scope` in a workflow log**, the token was
> minted with an older scope list. Re-run `auth_tiktok.py` and update
> the secret.

> **Refresh tokens are single-use.** TikTok rotates the refresh_token
> on every refresh and immediately invalidates the previous one — so
> the runtime token diverges from the GitHub secret on the very first
> refresh. Without **§1.5** below the channel breaks within ≤24 h of
> every manual mint. §1.5 closes the loop so the bot keeps itself
> authenticated indefinitely.

### 1.5 GitHub PAT for auto-rotating the TikTok token

This is the lever that turns the bot into a fire-and-forget channel.
After every successful TikTok OAuth refresh, `upload_tiktok.py` calls
the GitHub Secrets API to PUT the rolled token JSON back into
`TIKTOK_TOKEN`. Without the PAT this round-trip silently no-ops, the
local file is shredded at end-of-job, and the next run dies with
`invalid_grant`.

1. Generate a Fine-grained PAT at
   <https://github.com/settings/personal-access-tokens/new>:
     - **Resource owner**: the account/org that owns this repo.
     - **Repository access**: *Only select repositories* → pick this repo.
     - **Permissions → Repository → Secrets**: **Read and write**.
     - **Expiration**: 1 year (rotate annually; GitHub emails reminders).
2. Copy the PAT and add it as `TIKTOK_SECRETS_PAT` under
   **Settings → Secrets and variables → Actions → New repository secret**.

That's it — the workflow already passes `TIKTOK_SECRETS_PAT` and
`GH_REPO_FULL` to the upload step. From the next run onward, every
refresh round-trips back into the secret and the loop self-heals.

> **What if you skip §1.5?** The channel still works, just not on
> autopilot: you'll see `invalid_grant` in the logs on the next refresh
> (≤24 h later) and have to re-run `auth_tiktok.py` + paste the JSON
> into `TIKTOK_TOKEN` every single time.

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
category, A/B winners.

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
| `tiktok-bot.yml` | 00 / 05 / 10 / 15 / 20 | 1 Short per run × 5 runs = 5 Shorts/day |
| `analytics.yml` | 03 daily | Pull view/like/comment/share metrics |
| `daily-digest.yml` | 04 daily | Post GitHub Issue summarising the day |
| `dashboard.yml` | nightly | Rebuild static HTML dashboard on Pages |
| `velocity-snapshot.yml` | every 2 h | +2 h / +6 h / +24 h view counts |
| `cleanup-branches.yml` | weekly | Delete merged `claude/*` branches |

All workflows share the `main-write` concurrency group so they
serialise on git push.

---

## 4. TikTok rate-limit math

TikTok caps the Content Posting API (unaudited apps) at:

- **6 posts / minute / user**
- **30 posts / day / user**

Sustainable Shorts/day at default config:

| Shorts/day | TikTok daily cap usage |
|------------|------------------------|
| 3 | 10 % |
| **5 (default)** | **17 % — safe ceiling** |
| 10 | 33 % |
| 20 | 67 % |
| 30 | 100 % (no headroom for retries) |

To go above 30/day, get the app **approved** by TikTok (free,
~1-2 weeks). Approved apps get higher per-user limits.

---

## 5. Direct Post vs. Inbox

| Mode | What happens | When to use |
|------|--------------|-------------|
| `direct` (default) | Video goes live immediately. | App is approved for `video.publish`. |
| `inbox` | Draft lands in your TikTok app; you tap publish from the phone. | App is in sandbox / awaiting Direct Post approval. |

Set the mode via `TIKTOK_PUBLISH_MODE` (env or workflow `vars`).

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `❌ PEXELS_API_KEY not set` | Secret missing | Add it (§1.2) |
| `invalid_scope` in TikTok logs | Stale OAuth token | Re-run `auth_tiktok.py`, update `TIKTOK_TOKEN` |
| `Mistral rate limited (429)` storm | Free-tier quota hit | Configure one fallback (§2.1) |
| Workflow timeout at 25 min | Same as above | Same fix |
| Static Short (no motion) | All b-roll sources returned 0 | Check the `🔎 B-roll sources:` log line — verify Pexels key, or extend `ANIMAL_TOPICS` queries |
| Channel publishes 1 Short then stops | Poison-pill `.json` in `_videos/` | Run `git rm _videos/short-*.json` (the `.done` sidecars stay) and re-trigger the bot |
| `Publish status: FAILED` | TikTok moderation rejected the clip | Open TikTok app → Inbox → see rejection reason |

For anything else, check the workflow log via Actions → workflow run
→ Artifacts → download the log zip.

---

## 7. Operator hygiene

- **Never commit `tiktok_token.json`** — `.gitignore` excludes it,
  but watch for accidental adds.
- **Never push directly to `main`** if you're prototyping new content
  topics; use a `claude/*` branch + PR.
- **Roll the TikTok OAuth token every ~12 months** — the refresh token
  itself expires after a year of use.
- **Watch the TikTok posts ledger** — `_data/tiktok_quota_log.jsonl`
  records every Direct Post init. The workflow summary surfaces the
  daily total and warns at 80 %.

That's all that's required to operate Wild Brief end-to-end.
