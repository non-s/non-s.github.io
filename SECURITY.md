# Security Policy

## Reporting a Vulnerability

Please report security issues via **GitHub Security Advisories**:

  Repository → **Security** tab → **Report a vulnerability**

The public web property also exposes `/.well-known/security.txt` with the
current contact and policy URLs for automated vulnerability-report tooling.

## Supported Versions

Only the current `main` branch is maintained. There are no LTS branches.

## Scope

In scope:

- The Python automation pipeline (`generate_lofi_short.py`,
  `generate_lofi_mix.py`, `upload_youtube.py`, `auth_youtube.py`,
  `scripts/live_stream_dynamic.py`, `utils/`).
- The GitHub Actions workflows under `.github/workflows/`.

Out of scope:

- Third-party services we integrate with (YouTube, Pixabay, Jamendo).
  Report those upstream.
- Issues already known and tracked publicly in the GitHub issue tracker.
- Denial-of-service, social engineering, or physical attacks against
  infrastructure we don't control.

## What we do

- Address verified high/critical issues within 14 days where feasible.
- Credit reporters who request acknowledgement (no monetary bounty).
- Keep the issue private until a fix lands on `main`.
- Keep YouTube uploads on the official YouTube Data API path.
- Keep Analytics reads on the official YouTube Analytics API path when enabled.
- Avoid unsupported/private YouTube endpoints. When Studio-only features are
  needed, generate operator-assist artifacts instead of automating them.
- Redact or avoid logging values whose field names include token, secret,
  password, credential, authorization or API key.
- Treat `YOUTUBE_TOKEN`, OAuth client secrets, provider keys and local TTS
  assets as local or GitHub-secret-only material.

## Environment Inventory

Required:

- `YOUTUBE_TOKEN`
- `PIXABAY_API_KEY`

Optional:

- `YOUTUBE_STREAM_KEY` (24/7 live relay only)
- `ADAPTIVE_CADENCE_ENABLED`
- `ALLOW_FLEX_SLOT`
- `FLEX_SLOT_UTC`
- `MIN_SLOT_PUBLISH_SCORE`
- `MIN_QUEUE_OPPORTUNITY_SCORE`

See `docs/ENVIRONMENT.md` for the operating checklist.
