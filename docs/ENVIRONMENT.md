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
| `AUDIO_LIBRARY_MANIFEST` | no | Optional manifest path for operator-curated local YouTube Audio Library tracks. Defaults to `_data/audio_library_manifest.json`. |
| `EXPERIMENTS_FILE` | no | Optional override for the experiment assignment cache. |
| `VARIANT_ASSIGNMENTS_FILE` | no | Optional override for the durable variant-assignment JSONL log. |
| `ADAPTIVE_CADENCE_ENABLED` | no | Enables publish vs safe-skip decisions from the canonical UTC slots `05:23`, `14:23`, `19:23` and `23:23`. Defaults to enabled in the YouTube workflow. |
| `ALLOW_FLEX_SLOT` | no | Allows one operator-defined `FLEX_SLOT_UTC` in addition to the canonical slots. |
| `FLEX_SLOT_UTC` | no | Optional `HH:MM` UTC flex slot used only when `ALLOW_FLEX_SLOT=1`. |
| `MIN_SLOT_PUBLISH_SCORE` | no | Minimum top-candidate publish score required for an adaptive slot to publish. |
| `MIN_QUEUE_OPPORTUNITY_SCORE` | no | Minimum top-candidate opportunity score required for an adaptive slot to publish. |

## Local-Only Files

Do not commit:

- OAuth client secrets.
- YouTube token JSON files.
- temporary rendered videos/audio/images.
- local TTS caches.
- local audio assets referenced by an operator-only audio manifest when those
  assets are not license-cleared for redistribution.
- manual credentials or debug dumps.

Operator-dropped Google Trends snapshots belong under `_data/trends/manual_import/`.
Those files should contain public trend data only.

Operator-curated audio can be listed in `_data/audio_library_manifest.json`.
Only commit the manifest or assets when their license is public and
redistribution-safe; otherwise keep the assets local and point
`AUDIO_LIBRARY_MANIFEST` at a private path.

Publish slot decisions are appended to `_data/publish_slot_decisions.jsonl`.
When adaptive cadence is enabled, a slot can safely return `skip_outside_slot`,
`skip_no_eligible_story`, `skip_low_queue_quality` or `skip_quota_guard`
without failing the workflow.

## Logging Rules

- Never print OAuth token payloads.
- Never print API keys.
- Keep alert bodies short and secret-free.
- Use `utils.observability.emit_event` for structured script events.
- Redact fields whose names include `token`, `secret`, `password`,
  `credential`, `authorization` or `api_key`.
