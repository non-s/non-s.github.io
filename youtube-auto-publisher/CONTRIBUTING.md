# Contributing

This repository is maintained for production publishing workflows. Changes
should be small, reviewable, and validated before they reach the default branch.

## Before You Open a PR

- Start from the current default branch.
- Keep unrelated refactors out of the change.
- Do not commit secrets, OAuth tokens, API keys, downloaded private media, or
  generated local artifacts.
- Run the Quality workflow checks locally when possible.

## Production Checklist

- Python modules still compile.
- Credential handling remains environment-based and secret-safe.
- Publishing behavior, retries, or API changes are described in the PR.
- Any security-sensitive change references `SECURITY.md`.
