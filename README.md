# GlobalBR News — YouTube Shorts Bot

Automated pipeline that turns world news into vertical Shorts and uploads
them to YouTube. No website, no markdown blog — just **RSS → AI →
Shorts → YouTube**.

- Channel: <https://youtube.com/@globalbrnews>
- Cadence: **3 Shorts/day**, staggered at 08:00, 14:00, 20:00 UTC so
  each gets its own algorithm test window. YouTube API quota cap is
  ~5/day; we run at 60% of that.

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
| RSS | `feedparser` | OSS |
| AI primary | Mistral La Plateforme | 500k tokens/mo |
| AI fallback | Cerebras (opt-in) | 1M tokens/day |
| Background image | Pollinations | unlimited |
| Narration | Microsoft Edge-TTS | unlimited |
| Encoder | FFmpeg (libx264, AAC) | OSS |
| Hosting | GitHub Actions (public repo) | unlimited minutes |
| Upload | YouTube Data API v3 | 10k units/day |
| Analytics | YouTube Analytics API v2 | unlimited |

Total cost: **$0/month**.

## Workflows

| Workflow | Schedule (UTC) | Purpose |
|--|--|--|
| `fetch-news.yml` | every 3 h | Refresh the stories queue |
| `youtube-bot.yml` | 08 / 14 / 20 | Generate + upload 1 Short per run |
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
