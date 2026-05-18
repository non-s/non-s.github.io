# GlobalBR News — YouTube Shorts Bot

[![📰 Refresh stories queue](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-news.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/fetch-news.yml)
[![YouTube Bot — Shorts only](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/youtube-bot.yml)
[![📊 YouTube Analytics nightly](https://github.com/non-s/non-s.github.io/actions/workflows/analytics.yml/badge.svg)](https://github.com/non-s/non-s.github.io/actions/workflows/analytics.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Automated pipeline that turns world news into vertical Shorts and uploads
them to YouTube. No website, no markdown blog — just **RSS + public APIs
→ AI → Shorts → YouTube**.

- Channel: <https://youtube.com/@globalbrnews>
- Cadence: **3 Shorts/day**, staggered at 08:00, 14:00, 20:00 UTC so
  each gets its own algorithm test window. YouTube API quota cap is
  ~5/day; we run at 60% of that.
- Cost: **$0/month** — every layer is on a no-card free tier.

**First time here?** Read [`SETUP.md`](SETUP.md) — it walks you through
every secret + every optional free service the pipeline can use.

## Pipeline

```
┌─────────────┐    ┌──────────────────┐    ┌────────────────────┐
│  RSS feeds  │ →  │ fetch_news.py    │ →  │ _data/stories_queue│
│  (~15 srcs) │    │ (dedup, AI rank) │    │  .json (pending)   │
└─────────────┘    └──────────────────┘    └─────────┬──────────┘
                                                     │
                                                     ▼
                  ┌──────────────────┐    ┌────────────────────┐
                  │ upload_youtube.py│ ←  │ generate_shorts.py │
                  │ (YouTube Data API)│   │  (Pillow + FFmpeg) │
                  └──────────────────┘    └────────────────────┘
```

The `_data/stories_queue.json` file is the only contract between the
two halves of the pipeline. `fetch_news.py` writes pending stories;
`generate_shorts.py` picks the highest-scoring N and marks them
consumed. Both can be run independently.

## Stack

| Layer | Tool | Free tier |
|--|--|--|
| RSS sources | `feedparser` (38 curated feeds) | OSS |
| Public sources | Reddit + HN + Wikipedia + Google Trends + GDELT | unauth, no key |
| AI primary | Mistral La Plateforme | 500k tokens/mo |
| AI fallback 1 | Cerebras (opt-in) | 1M tokens/day |
| AI fallback 2 | Google Gemini (opt-in) | 1,500 req/day |
| AI fallback 3 | Groq (opt-in) | ~14k req/day |
| B-roll motion video | Pexels Videos → NASA → Internet Archive | 20k req/mo (Pexels) / unauth (rest) |
| Background images | OG meta → Wikipedia → Openverse → Pollinations | unauth, no key |
| Captions (word-level) | Groq Whisper → faster-whisper local | 2k req/day (Groq) / OSS (fwh) |
| Narration | Microsoft Edge-TTS (6-voice rotation) | unlimited |
| Encoder | FFmpeg (libx264, AAC, libass) | OSS |
| Hosting | GitHub Actions (public repo) | unlimited minutes |
| Upload | YouTube Data API v3 | 10k units/day |
| Cross-post | Bluesky AT Protocol (opt-in) | free, vertical-video feed |
| Analytics | YouTube Analytics API v2 | unlimited |

Total cost: **$0/month**. Every layer above is on a no-credit-card free
tier or fully open-source.

## What makes this best-in-class

### Inauthentic-Content survival (the existential bit)

YouTube's 15 July 2025 policy terminated **12M+ channels in 2025**
including Screen Culture (1M+ subs) for pure wire-copy narration over
static frames. To stay on the right side of the bar this pipeline:

- **B-roll motion footage** instead of static frames — Pexels Videos
  API (200 req/h, free key) → NASA Image+Video → Internet Archive.
  Three different sources rotated per Short = no "templated visuals"
  signal.
- **Word-level burned captions** via Groq Whisper (free 2k req/day) or
  faster-whisper locally. +18 % watch time documented (Zebracat 2025).
- **Hook text overlay** for the first 3 seconds — the highest-leverage
  retention window in 2026 (swipe-away signal weighs heaviest).
- **AI disclosure flag** (`containsSyntheticMedia=true`) on every
  upload — explicit transparency satisfies the policy.
- **Transformative voice-over**: the AI prompt forces opinion / analysis
  / winner-and-loser framing — never just reading the headline.



- **5 keyless discovery sources** beyond classical RSS — Reddit, HN,
  Wikipedia, Google Trends, GDELT — so the queue is fuller and more
  current than any single-RSS pipeline.
- **Trending boost**: any story whose headline mentions a Google Trends
  term gets a score bump. Search what people are searching.
- **Performance feedback loop**: the nightly Analytics workflow writes
  a per-category retention summary; the next fetch-news run biases
  toward categories that retained >60% and demands a higher score
  from those that retained <30%. Self-tuning.
- **4-provider AI chain** — Mistral + Cerebras + Gemini + Groq, all
  free-tier, all opt-in. A story has up to 4 chances to survive a
  rate-limit or 5xx instead of being dropped.
- **5-layer image fallback** — story image → Open Graph scrape →
  Wikipedia thumbnail → Openverse CC → Pollinations AI. The Short
  almost never falls back to a generic background.
- **6-voice TTS rotation** — Jenny / Aria / Guy / Sonia / Ryan / Natasha,
  picked deterministically by story title hash. War/politics get the
  authoritative British voices, lifestyle gets the warmer ones.
- **Per-category playlists + first-comment seed** — every upload joins
  the right playlist and the channel auto-posts a sourcing + engagement
  prompt as the first comment.
- **Workflow run summaries** — every CI run drops a markdown panel
  with metrics under the Actions tab. Zero external monitoring needed.
- **AI response cache** — disk JSONL with 30-day TTL; identical
  prompts across runs come back free, cutting Mistral burn 60-80 %.
- **Pre-AI relevance gate** — `entry_relevance_score < 3` skips the
  AI call entirely. Roughly halves the AI calls per run.
- **Prompt-injection defense** — RSS-borne titles / descriptions are
  sanitized for "ignore previous instructions" / system-tag forgery
  patterns before they touch the LLM. System prompt explicitly tells
  every provider to treat field values as untrusted data.

## Workflows

| Workflow | Schedule (UTC) | Purpose |
|--|--|--|
| `fetch-news.yml` | every 3 h | Refresh the stories queue |
| `youtube-bot.yml` | 08 / 14 / 20 | Generate + upload 1 English Short per run |
| `youtube-bot-ptbr.yml` | 09 / 15 / 21 | Generate + upload 1 PT-BR Short per run (sibling channel, opt-in) |
| `analytics.yml` | 03:00 | Pull retention/CTR snapshot to `_data/analytics/` |
| `cleanup-branches.yml` | Sun 04:00 | Delete merged bot branches |

## Local dev

```bash
pip install -r requirements.txt
python fetch_news.py                  # update the queue
python generate_shorts.py             # render shorts locally
python upload_youtube.py              # upload (needs auth_youtube.py first)
```

See `.env.example` for required secrets.

## Security

See [`SECURITY.md`](SECURITY.md). Report vulnerabilities via the
repository's **Security → Report a vulnerability** tab.

## License

MIT — see [`LICENSE`](LICENSE).
