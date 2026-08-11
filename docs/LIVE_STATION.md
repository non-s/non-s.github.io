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

## Community rhythm

Use normal latency for the ambient station when reliability is most important. Schedule separate low-latency community sessions for polls, introductions and live chat; their outcomes should inform future session themes without pressuring people to remain watching.
