# Security Policy

## Supported Versions

Security fixes are applied to the `main` branch only. There are no
LTS/release lines; the project ships continuously via GitHub Actions.

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please report vulnerabilities privately:

1. Go to the repository's **Security** tab → **Report a vulnerability**
   (GitHub's private vulnerability reporting).
2. If unavailable, email the maintainer directly with a description and
   reproduction steps.

You will receive an acknowledgement within 72 hours. Responsible
disclosure is appreciated — credit will be given in the fix commit
unless you prefer to remain anonymous.

## Scope

This project handles sensitive credentials:

- YouTube OAuth tokens (`youtube_token.json`, `YOUTUBE_TOKEN` secret)
- GitHub Personal Access Tokens (`GH_PAT` secret)
- Google Gemini API keys (`GEMINI_API_KEY` secret)

Issues affecting the confidentiality of these secrets (e.g. token
leakage in logs, command-line args, or CI output) are treated as
**high severity**.

## Hardening measures already in place

- OAuth token files written with `umask 0o077`.
- Secrets restored to CI runners with `umask 077` + `chmod 600` and
  deleted in `if: always()` cleanup steps.
- `gh secret set` receives secret values via **stdin**, never argv.
- `actions/checkout` uses `persist-credentials: false` and SHA-pinned
  action versions.
- `bandit -ll` and `pip-audit` run as blocking gates in CI.
- AI-generated text is filtered through `is_safe_ai_text()` to reject
  prompt-injection artefacts (links, HTML, outcome claims).