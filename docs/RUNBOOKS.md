# Wild Brief Runbooks

The v1.0 operating contract lives in [V1_CLOSURE.md](V1_CLOSURE.md). Use that
document as the final definition of "done" before starting new work.

## v1.0 Closure Check

1. Confirm `_data/upload_intents.jsonl` has an `uploaded` row for the latest
   UTC slot.
2. Run `python scripts/check_repo_contracts.py`.
3. Run `python scripts/audit_slot_contracts.py`.
4. Run `python scripts/check_schedule_sync.py`.
5. Run `python scripts/queue_ready_count.py --json`.
6. Run `python -m pytest -q`.
7. Build the dashboard and check the `v1.0 closure status` card.

## Queue Looks Stale

1. Run `python scripts/free_signal_harvester.py`.
2. Run `python scripts/apply_topic_freshness.py`.
3. Check `_data/trends/freshness_report.json`.
4. If the queue is still weak, run `python fetch_animals.py`.

## Studio Reach Import

1. Drop exported Studio or Google Sheets CSV files in `_data/studio_reach_exports/`.
2. Run `python scripts/import_studio_reach_export.py`.
3. Confirm `_data/analytics/studio_reach_latest.json` has non-zero rows.

## Quota Pressure

1. Run `python scripts/quota_preflight.py youtube-bot --json`.
2. Use `QUOTA_GUARD_MODE=warn` for passive logging.
3. Use `QUOTA_GUARD_MODE=block` only when the projected daily ratio should skip publication.

## TTS Fallback

1. Set `COQUI_TTS_COMMAND` to a local Coqui-compatible command if available.
2. Run `python scripts/tts_healthcheck.py --no-synth --json`.
3. Run without `--no-synth` locally when you want an actual sample render.

## Dashboard Refresh

Run `python scripts/run_intelligence_suite.py dashboard --strict`, then
`python scripts/build_dashboard.py`. The dashboard should render even with no
optional exports.

## Alert Issue

The free GitHub Issues alert workflow opens or comments on `Wild Brief
automation alert` when a critical workflow fails. Treat the issue as the active
incident room, paste the failed run URL, and close it only after the closure
checks pass again.
