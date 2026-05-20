# Wild Brief — Animal Shorts Bot (TikTok)

[![🐾 Refresh animal queue](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-content.yml)
[![TikTok Bot — Shorts only](https://github.com/non-s/non-s.github.io/actions/workflows/tiktok-bot.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/tiktok-bot.yml)
[![📊 TikTok Analytics nightly](https://github.com/non-s/non-s.github.io/actions/workflows/analytics.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/analytics.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Automated pipeline that turns Pexels animal footage into vertical
TikTok videos with original voice-over narration, and publishes them
via the official TikTok Content Posting API 5 times a day.

- Channel: <https://www.tiktok.com/@wildbrief_x> (display name: **Wild Brief**)
- Cadence: **5 Shorts/day**, posted at 01, 14, 17, 22, 23 UTC —
  TikTok-tuned to Brazil + US peak engagement windows (BR 19-22 BRT
  double-stamped). 5 posts/day = 17 % of TikTok's 30/day unaudited-app
  ceiling.
- Duration target: **25-35 seconds** — TikTok For You rewards
  completion rate, not length. 30s Shorts at 85 % completion beat
  55s Shorts at 50 % completion every time.
- Cost: **$0/month** — every layer is on a no-card free tier.

**First time here?** Read [`SETUP.md`](SETUP.md) — it walks you through
every secret + every optional free service the pipeline can use.

## Pipeline

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│ Pexels videos   │ →  │ fetch_animals.py │ →  │ _data/stories_queue│
│ (6 categories)  │    │ (AI fun facts)   │    │  .json (pending)   │
└─────────────────┘    └──────────────────┘    └─────────┬──────────┘
                                                         │
                                                         ▼
                      ┌──────────────────┐    ┌────────────────────┐
                      │ generate_shorts  │ →  │ _videos/*.mp4      │
                      │ (TTS + b-roll +  │    │ + thumbnail JPG    │
                      │ captions)        │    │ + metadata JSON    │
                      └──────────────────┘    └─────────┬──────────┘
                                                         │
                                                         ▼
                      ┌──────────────────┐    ┌────────────────────┐
                      │ upload_tiktok    │ →  │ TikTok profile     │
                      │ (chunked +       │    │ + .done sidecar    │
                      │  Direct Post)    │    │ committed to git   │
                      └──────────────────┘    └────────────────────┘
```

## What every Short carries

- **30-45 second AI-narrated voice-over** with 3-5 surprising facts about
  the animal in the clip
- **Up to 6 Pexels b-roll clips** combined with hard cuts every ~7-8 s
- **Slow Ken Burns push** (1.00 → 1.04) inside each segment for retention
- **Word-level burned captions** transcribed via Groq Whisper (or local
  faster-whisper if no key)
- **Hook overlay** drawn over the first 3 s of the clip
- **Channel watermark** upper-right on every frame
- **Branded intro card** (~0.8 s) + outro card (~2 s) with the host's
  signature sign-off
- **AI-generated content flag** on every upload (TikTok policy compliance)

## Six animal categories

| Category | Example Pexels queries | Topic hashtag |
|----------|------------------------|---------------|
| 🐱 Cats | cat playing, kitten, cat sleeping | `#Cats` |
| 🐶 Dogs | puppy, dog running, golden retriever | `#Dogs` |
| 🐬 Ocean | dolphin, whale, shark, coral reef | `#Ocean` |
| 🦁 Wildlife | lion, elephant, tiger, leopard | `#Wildlife` |
| 🦅 Birds | eagle, parrot, owl, penguin | `#Birds` |
| 🐴 Farm | horse running, baby goat, sheep | `#FarmAnimals` |

Topics live in `fetch_animals.py:ANIMAL_TOPICS`. Each category rotates
through 6-7 queries deterministically per 3-hour window so the cron
doesn't burn the same query every run.

## Quality / retention levers (all built in)

- **Multi-provider AI fallback chain** — Mistral → Cerebras → Gemini →
  Groq, with disk cache + per-provider success-rate reordering + an
  in-run circuit breaker when Mistral 429s repeatedly
- **A/B framework** across hook style / script tone / thumbnail style /
  CTA style, with engagement-blended winner detection once each
  variant has ≥ 8 samples
- **Per-category retention bias** — high-velocity categories get
  amplified in the next ranking pass
- **Music bed** — Pixabay CC0 tracks ducked to −22 dB under TTS
- **Velocity tracker** — +2h / +6h / +24h view-count snapshots, the
  strongest predictor of algorithmic distribution on the For You feed
- **Pre-flight script quality lint** blocks weak hooks / clickbait /
  AI-tell phrases before upload
- **Channel memory** — past Shorts logged so the AI can reference
  prior coverage ("I covered foxes last week")
- **Panic kill switch** (`PANIC_HALT=1`) halts every entry point in
  case of emergency

## Operational ops

- **TikTok posts ledger** with 80 % warning before the daily 30-post cap
- **Daily digest GitHub Issue** at 04 UTC summarising the prior 24 h
  of Shorts + analytics
- **Anomaly detection** flags > 50 % drops vs the 7-day baseline
- **Token shredding** at the end of every workflow run (defence-in-depth)
- **`_videos/.done` sidecars** committed back to git on every successful
  upload — provides a full audit trail of what shipped, when, and which
  TikTok video ID it became

## What TikTok doesn't let us automate (yet)

Compared to the previous YouTube version, the TikTok Open API doesn't
expose endpoints for:

- **Reading or posting comments** — comment moderation is manual,
  inside the TikTok app. The auto-reply workflow is therefore disabled.
- **Setting a custom video cover image** — TikTok auto-generates the
  cover from a timestamp we request (1 s into the clip). The branded
  thumbnail we render is kept on disk for cross-posting / dashboards.
- **Playlists** — TikTok doesn't have a playlist concept; discovery is
  hashtag-driven, so the bot front-loads `#fyp #foryou #<topic>` in
  every caption instead.

## Tests

```
$ python -m pytest tests/
```

400+ tests covering every utility module, the AI fallback chain, the
A/B framework, the TikTok Content Posting contract, video composition,
captions, the queue schema, and an end-to-end smoke test that exercises
the full fetch → enrich → generate path with every external touchpoint
mocked.

## License

MIT. See [LICENSE](LICENSE).

## Operator follow-up

To start the channel from a clean slate:

1. Add `PEXELS_API_KEY`, `MISTRAL_API_KEY`, `TIKTOK_CLIENT_KEY`,
   `TIKTOK_CLIENT_SECRET`, `TIKTOK_TOKEN` to GitHub Secrets
   ([SETUP.md](SETUP.md)).
2. (Optional) Add at least one of `CEREBRAS_API_KEY` / `GEMINI_API_KEY` /
   `GROQ_API_KEY` for the fallback chain.
3. Trigger `fetch-content.yml` manually to populate the queue.
4. Trigger `tiktok-bot.yml` manually to publish the first Short — or
   wait for the next cron slot (01 / 14 / 17 / 22 / 23 UTC, tuned to
   Brazil + US TikTok peak-engagement windows).
