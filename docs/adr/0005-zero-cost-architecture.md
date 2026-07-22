# ADR 0001: Zero-Cost Architecture

## Status

Accepted.

## Context

Wild Brief must grow without paid services. The system can use free API quota,
operator-provided exports and local deterministic scoring, but it should not
depend on paid inference, private endpoints or unavailable browser automation.

## Decision

- Keep YouTube publishing on the official Data API.
- Keep analytics normalization append-only and tolerant of missing optional data.
- Use local guardrails for openings, claims, rights, originality, experiments and upload idempotency.
- Default new gates to `warn`; allow `block` only through explicit environment flags.
- Track operator-only manual actions as JSON artifacts instead of pretending they are automated.

## Consequences

The system remains cheap and recoverable. Some decisions are conservative until
manual Studio exports or YouTube Analytics fields provide enough signal.
