# Wild Brief Environment

## Required Secrets

| Name | Required | Use |
| --- | --- | --- |
| `YOUTUBE_TOKEN` | yes | OAuth token JSON for official YouTube Data API upload and optional Analytics API reads. |
| `PEXELS_API_KEY` or `PEXELS` | yes | Free b-roll/source clip discovery. |
| One AI text provider key | yes | Queue/story rewriting and packaging assistance. Supported names include `MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY` and `GROQ_API_KEY`. |

## Optional Secrets and Settings

| Name | Required | Use |
| --- | --- | --- |
| `PIXABAY_API_KEY` or `PIXABAY` | no | Additional free media source. |
| `GEMINI_API_KEY` or `GEMINI` | no | Visual QA when configured. |
| `WILD_BRIEF_RSS_URLS` | no | Comma-separated RSS URLs for `scripts/free_signal_harvester.py`. |
| `WILD_BRIEF_GMAIL_ALERTS` | no | Set to `1` only when alert payload generation should be enabled. |
| `WILD_BRIEF_ALERT_TO` | no | Alert recipient used only when alerts are explicitly enabled. |
| `COQUI_TTS_COMMAND` | no | Optional local Coqui-compatible TTS command. Edge TTS remains primary. |
| `COQUI_TTS_MODEL` | no | Optional local Coqui model name. |

## Local-Only Files

Do not commit:

- OAuth client secrets.
- YouTube token JSON files.
- temporary rendered videos/audio/images.
- local TTS caches.
- manual credentials or debug dumps.

Operator-dropped Google Trends snapshots belong under `_data/trends/manual_import/`.
Those files should contain public trend data only.

## Logging Rules

- Never print OAuth token payloads.
- Never print API keys.
- Keep alert bodies short and secret-free.
- Use `utils.observability.emit_event` for structured script events.
- Redact fields whose names include `token`, `secret`, `password`,
  `credential`, `authorization` or `api_key`.
