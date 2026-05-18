# GlobalBR News — YouTube Shorts Bot

Automated pipeline that turns world news into vertical Shorts and uploads
them to YouTube. No website, no markdown blog — just **RSS → AI →
Shorts → YouTube**.

- Channel: <https://youtube.com/@globalbrnews>
- Cadence: up to **3 Shorts/day**, one story each (YouTube API quota
  cap is ~5/day; we run conservatively below that).

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
| AI (title, hook, script) | Mistral La Plateforme | 500k tokens/mo |
| Background image | Pollinations | unlimited |
| Narration | Microsoft Edge-TTS | unlimited |
| Encoder | FFmpeg (libx264, AAC) | OSS |
| Hosting | GitHub Actions (public repo) | unlimited minutes |
| Upload | YouTube Data API v3 | 10k units/day |

Total cost: **$0/month**.

## Workflows

| Workflow | Schedule | Purpose |
|--|--|--|
| `fetch-news.yml` | every 3 h | Refresh the stories queue |
| `youtube-bot.yml` | daily 14:00 UTC | Generate + upload up to 3 Shorts |
| `cleanup-branches.yml` | weekly | Delete merged bot branches |

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
