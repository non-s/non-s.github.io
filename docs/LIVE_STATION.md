# Pata Jazz Visual Radio

The live station is a community product, not an unattended playlist. Its five recurring sessions give people a shared vocabulary: Sunrise Companions, Focus With Paws, Golden Hour Friends, Rainy Window Club and After Dark Nest.

## Catalogue gate

Run `python scripts/plan_live_station.py`. It writes `_data/live_station_plan.json` and reports the verified catalogue size. The target is 181 unique tracks. A plan is **not** a broadcast command; it never reads an RTMP key or creates a YouTube event.

Only audio records with `license_verified_for_youtube: true` and a `license_url` can appear. Only video records with a source URL and licence can appear. The sync scripts preserve these audit fields. Older cached assets need a new sync or manual licence review before they qualify.

## Before any public broadcast

1. Review the generated plan and all credits.
2. Render and watch a private sample for audio transitions, visual pacing and accurate credits.
3. Confirm the Live Control Room metadata, moderation approach and stream health.
4. Start with an unlisted technical rehearsal. A public event requires an explicit publishing decision.

## Continuous mode

The Python command accepts `--duration-minutes 0` for an unbounded local
process. In GitHub Actions, the same input selects rolling 330-minute segments:
each hosted job closes cleanly before the six-hour limit and dispatches the next
segment automatically. Assets and the rendered loop are restored from Actions
cache, so later cycles normally start much faster than the first one. Manually
cancelling the workflow stops the chain and does not schedule another segment.
The RTMP stream name remains provided by the YouTube API at runtime and must
never be committed to the repository.

If FFmpeg exits or loses the RTMP connection, continuous mode waits briefly and
starts it again against the same stream. If the Python process or host restarts,
the command searches for a matching active/upcoming broadcast and reuses its
bound stream instead of creating a duplicate event. A host-level service manager
should still restart the Python command after machine or process failure.

### Host supervision

`deploy/pata-jazz-live.service` is a production-oriented systemd unit. Install
the repository and virtual environment under `/opt/pata-jazz`, keep the OAuth
token outside the checkout at `/etc/pata-jazz/youtube_token.json`, and install
the unit as `/etc/systemd/system/pata-jazz-live.service`. The service restarts
after failure and starts at boot once enabled. Review the video path and begin
with `--privacy unlisted` for the technical rehearsal before switching it to
`public`.

The self-hosted service remains an alternative for a dedicated server, but the
default continuous workflow does not depend on the operator's computer.

## Community rhythm

Use normal latency for the ambient station when reliability is most important. Schedule separate low-latency community sessions for polls, introductions and live chat; their outcomes should inform future session themes without pressuring people to remain watching.
