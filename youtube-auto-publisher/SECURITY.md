# Security Policy

This project is maintained for production use. Security fixes should be small,
reviewable, and validated through the repository quality checks before release.

## Supported Branch

Security updates are applied to the default branch used for production deploys.

## Reporting a Vulnerability

Do not publish secrets, exploit payloads, private user data, tokens, API keys, or
OAuth material in a public issue.

Use the repository Security tab to open a private vulnerability report when that
option is available. If private reporting is not available, open a minimal public
issue that describes the affected area without sensitive reproduction details.

Include:

- affected workflow, credential path, API integration, or publishing step
- expected impact and who can trigger it
- safe reproduction notes without real credentials or private data
- suggested mitigation, if known

## Handling

Security-related changes should keep production behavior stable, include the
relevant automated checks, and avoid exposing credentials, tokens, or project
secrets.
