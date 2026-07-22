# Runbook

Operational guide for the Amber Hours pipeline: what each reliability
workflow watches, what to do when `ops-alert.yml` opens/updates its
"Wild Brief automation alert" issue, and routine maintenance procedures.
See [README.md](README.md) for the pipeline overview and
[SETUP.md](SETUP.md) for first-time setup.

## Alert triage

`ops-alert.yml` opens (or comments on) one GitHub issue whenever a
monitored workflow fails or a health check reports degraded, with the
workflow name, conclusion, commit, and run link. Start from the workflow
name in that issue:

| Workflow | What it means when it fails |
| --- | --- |
| `YouTube Bot - Shorts only` | A Shorts publish run itself failed -- check the run log first (auth, quota, or a real bug). |
| `24/7 Live Stream Relay` | A live-relay job crashed or hit its 6h timeout. Usually self-heals via the watchdog below; only chase it if the channel is actually offline. |
| `24/7 live stream watchdog` | The watchdog itself failed to run (rare -- usually a `gh` auth or API issue, not the stream). |
| `YouTube publishing watchdog` | Couldn't dispatch a recovery run for a missed Shorts slot. |
| `Publishing health check` | **No real upload has landed within the staleness window while publishing is enabled** -- the clearest sign of silent degradation (see below). |
| `Admin: detect orphaned video markers` | The weekly YouTube-API sweep for deleted videos failed to run (auth/quota), not that an orphan was found (that's a normal log line, not a failure). |
| `Token rotation check` | `YOUTUBE_TOKEN` is overdue for rotation (see below) -- or has never been recorded as rotated at all. |
| `CodeQL` / `Security, SBOM and license audit` | A real code-scanning finding or a dependency/secret-pattern hit -- open the run and read the finding before dismissing. |
| `Production quality gate` / `Production smoke` | A regular CI check failed on `main` -- treat like any failing test suite. |

### Publishing health check fired -- what to actually check

1. Is `YOUTUBE_PUBLISHING_ENABLED` really meant to be `1` right now? If
   publishing was intentionally paused, this is a false positive --
   nothing to do.
2. Check the last few `Storm Ambience - rain & thunder for sleep` /
   `Storm Shorts - rain & thunder` runs: are they green but producing
   nothing? Each format loops one fixed, committed real clip now (no
   live fetch, no external dependency to go stale) -- an upload-step
   failure here is far more likely `uploadLimitExceeded` (see below)
   than a missing-media issue.
3. `scripts/check_publishing_health.py` can be run locally (or via
   `workflow_dispatch`) for the exact numbers: hours since the last real
   upload, and why it's counted as stale.

## Token rotation

`YOUTUBE_TOKEN` is a long-lived OAuth refresh token -- it does not expire
on its own, which is exactly why `token-rotation-check.yml` exists to
prompt for it periodically (`_data/security/token_rotation.json`,
default 180-day window).

To rotate:

1. Regenerate the token following [SETUP.md](SETUP.md)'s "Generate
   `YOUTUBE_TOKEN`" section and replace the `YOUTUBE_TOKEN` repository
   secret.
2. Run `token-rotation-check.yml` manually with `mark_rotated: true` to
   record today's date as the new baseline (this commits
   `_data/security/token_rotation.json`).

## External uptime monitor (not automatable from here)

Everything above runs *inside* GitHub Actions, which means a full GitHub
Actions outage is a blind spot nothing in this repo can self-heal --
neither the live-relay job nor its watchdog would run at all. An
external monitor closes that gap. Recommended setup (either service's
free tier is enough for this):

- **UptimeRobot** (<https://uptimerobot.com>) or **Healthchecks.io**
  (<https://healthchecks.io>): create a monitor that checks the channel's
  live status page (`https://www.youtube.com/channel/<CHANNEL_ID>/live`)
  for HTTP 200, or use Healthchecks.io's "dead man's switch" pattern --
  have `live-stream-watchdog.yml` (or a new lightweight step in it) `curl`
  a Healthchecks.io ping URL on every run, and let Healthchecks.io alert
  you if no ping arrives within its grace window. The latter also
  indirectly detects a GitHub Actions-wide outage, since no workflow runs
  at all means no ping arrives either.
- Point the alert at an email or phone number you actually check --
  GitHub issue notifications (what `ops-alert.yml` uses) are useless
  during a GitHub outage.

This wasn't wired up automatically because it needs an account/API key
on a third-party service this environment has no access to provision.

## Dashboard

`dashboard.yml` builds `index.html` daily: total views, subscribers
gained, Shorts published, and title-collision rate as live tiles; a
14-day trend table + sparkline for the same metrics
(`_data/analytics/dashboard_history.jsonl`); and a "Branding mix" table
of how published videos split across mood playlist buckets. View/
watch-time numbers only populate after a manual Studio Reach CSV import
(see SETUP.md) -- the page says so explicitly when none has ever run.
