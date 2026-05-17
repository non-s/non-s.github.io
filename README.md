# GlobalBR News

A fully automated world-news portal that ingests RSS, enriches each story with AI, and publishes to the blog + YouTube every hour. No human in the loop.

**Live site:** [non-s.github.io](https://non-s.github.io) · **YouTube:** [@serenolofi](https://www.youtube.com/@serenolofi)

## What it does

Every hour, GitHub Actions runs `fetch_news.py`, which:

1. Reads ~30 RSS feeds (BBC, Reuters, The Guardian, AP, NPR, Al Jazeera, etc.).
2. Filters out spam, duplicates, dead source URLs, and short / low-quality items.
3. Sends each surviving story to **Mistral** for SEO title, summary, key points, tl;dr, FAQ, entities, and category classification.
4. Applies a 0–10 quality gate; anything under 6 is dropped before publication.
5. Generates a cover image (Pollinations.ai) and Jekyll post in `_posts/`.
6. Commits and pushes — Jekyll on GitHub Pages does the rest.

Once a day, a YouTube workflow:
- Builds an English roundup video (FFmpeg + edge-tts narration + an AI-painted thumbnail).
- Generates Shorts from the most engaging single-story posts.
- Uploads both and writes blog posts pointing to the videos.

The site is **English-only** — there is no translation pass and no PT-BR mirror.

## The stack

| Concern | Tool |
|---|---|
| Static site | Jekyll 3.x on GitHub Pages |
| Hosting & CI | GitHub Pages + GitHub Actions |
| RSS | `feedparser` |
| LLM | Mistral La Plateforme (free tier, `mistral-small-latest`) via REST |
| Image generation | Pollinations.ai Flux (no API key) |
| TTS | Microsoft `edge-tts` (Jenny / Davis) |
| Video assembly | FFmpeg + Pillow |
| YouTube upload | YouTube Data API v3 + OAuth |
| Search engine indexing | IndexNow + Google Indexing API |

## Required GitHub Secrets

| Secret | Used for | Required? |
|---|---|---|
| `MISTRAL_API_KEY` | All AI calls (rewriting, FAQ, video meta) | **Yes** — site stops publishing without it |
| `YOUTUBE_TOKEN` | OAuth token for video upload | Only for `youtube-bot.yml` |
| `MAILCHIMP_API_KEY` / `MAILCHIMP_AUDIENCE_ID` / `MAILCHIMP_SERVER` | Daily newsletter campaign | Only for `newsletter.yml` |
| `GOOGLE_INDEXING_CREDENTIALS` | Google Search Console push | Optional |
| `BING_API_KEY` / `INDEXNOW_KEY` | IndexNow ping | Optional |

A complete list — including all tuning variables — is in [`.env.example`](.env.example).

## Where things live

```
fetch_news.py            # main hourly pipeline
generate_video.py        # YouTube roundup video (English)
generate_shorts.py       # YouTube Shorts (one per story)
generate_audio.py        # MP3 narration per post
audit_site.py            # weekly quality report → _data/audit_report.json
utils/
  ai_helper.py           # Mistral wrapper, quality_score, sentiment, etc.
  text.py                # humanize_for_tts (strips markdown for TTS)
  frontmatter.py         # YAML parse helpers
  digest.py              # shared helpers for editorial digests
  video_common.py        # PIL / font / download helpers shared by video pipelines
  dedup.py / retry.py    # plumbing
_layouts/post.html       # JSON-LD (NewsArticle + FAQPage + BreadcrumbList)
sitemap.xml              # main sitemap (image + news annotations)
sitemap-news.xml         # Google News sitemap (48h window)
.github/workflows/       # fetch-news, youtube-bot, newsletter, etc.
```

## Security

Report vulnerabilities via [GitHub Security Advisories](https://github.com/non-s/non-s.github.io/security/advisories/new); the machine-readable contact is `/.well-known/security.txt`. See [`SECURITY.md`](SECURITY.md) for scope and turnaround.

## Editorial transparency

Every published post carries an "About this summary" block linking back to the original publisher. The AI rewrites and enriches; it does not invent. See [`/editorial-policy/`](https://non-s.github.io/editorial-policy/) for the full disclosure.

## Local development

```sh
bundle install                  # Jekyll dependencies
pip install -r requirements.txt # Python dependencies
bundle exec jekyll serve        # http://localhost:4000

# Run the pipeline locally (needs MISTRAL_API_KEY in env)
MISTRAL_API_KEY=xxx python fetch_news.py

# Run the test suite
pytest -q
```

## License

The site theme, generators, and original commentary are released under MIT. Headlines and excerpts from source articles are used under fair-use principles for news aggregation; full article text remains the copyright of the original publisher.
