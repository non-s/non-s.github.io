# Security Policy

## Reporting a Vulnerability

Please report security issues via **GitHub Security Advisories**:

  Repository → **Security** tab → **Report a vulnerability**

## Supported Versions

Only the current `main` branch is maintained. There are no LTS branches.

## Scope

In scope:

- The Python automation pipeline (`fetch_news.py`, `generate_shorts.py`,
  `upload_youtube.py`, `auth_youtube.py`, `utils/`).
- The GitHub Actions workflows under `.github/workflows/`.

Out of scope:

- Third-party services we integrate with (Mistral, Pollinations, edge-tts,
  YouTube). Report those upstream.
- Issues already known and tracked publicly in the GitHub issue tracker.
- Denial-of-service, social engineering, or physical attacks against
  infrastructure we don't control.

## What we do

- Address verified high/critical issues within 14 days where feasible.
- Credit reporters who request acknowledgement (no monetary bounty).
- Keep the issue private until a fix lands on `main`.
