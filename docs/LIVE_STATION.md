# Liquid Wire Live

The live operation should be built from long procedural renders or a dedicated
real-time renderer. Do not reuse legacy pet/stock live tooling.

Validated launch path:

1. Generate a 2 minute `live-test` video.
2. Upload it as private.
3. Check Content ID.
4. Generate a 15 minute long session.
5. Only then test a public live stream.

## Continuous GitHub relay

`liquid-wire-live.yml` runs one public session for 330 minutes, below the
hosted-runner ceiling, then dispatches its successor. Every session generates
a fresh horizontal audiovisual source before FFmpeg repeats that source for
the session. `liquid-wire-live-watchdog.yml` checks every 30 minutes and
recovers the chain when no live run is active or queued.

This is continuous relay semantics, not one immortal runner process: YouTube
receives sequential broadcasts with a short generation/setup hand-off between
them. The workflow never reuses stock media, and every new session is governed
by the same visual/audio uniqueness contracts as ordinary publications.
