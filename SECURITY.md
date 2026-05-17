# Security Policy

## Reporting a Vulnerability

Please report security issues via **GitHub Security Advisories**:
<https://github.com/non-s/non-s.github.io/security/advisories/new>

For machine-readable contact info, see [`/.well-known/security.txt`](https://non-s.github.io/.well-known/security.txt).

## Supported Versions

Only the current `main` branch is maintained. There are no LTS branches.

## Scope

In scope:

- The Jekyll site (`_layouts/`, `_includes/`, `_data/`, `_posts/`, root HTML/XML).
- The Python automation pipeline (`fetch_news.py`, `generate_*.py`, `utils/`, `_videos/`).
- The GitHub Actions workflows under `.github/workflows/`.

Out of scope:

- Third-party services we integrate with (Mistral, Pollinations, edge-tts,
  Mailchimp, YouTube, jsDelivr, GitHub Pages). Report those upstream.
- Issues already known and tracked publicly in the GitHub issue tracker.
- Denial-of-service, social engineering, or physical attacks against
  infrastructure we don't control.

## What we do

- Address verified high/critical issues within 14 days where feasible.
- Credit reporters who request acknowledgement (no monetary bounty).
- Keep the issue private until a fix lands on `main`.
