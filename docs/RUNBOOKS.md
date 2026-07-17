# Amber Hours Runbooks

## Publisher Health Check

1. Confirm `_data/upload_intents.jsonl` has an `uploaded` row for the
   latest UTC slot.
2. Run `python scripts/check_repo_contracts.py`.
3. Run `python scripts/audit_slot_contracts.py`.
4. Run `python scripts/check_schedule_sync.py`.
5. Run `python -m pytest -q`.

## Media Library Looks Empty

1. Trigger `admin-resync-broll.yml` to force a fresh b-roll sync.
2. Trigger `admin-check-media-library.yml` to see current bgm/b-roll
   counts.
3. If Jamendo/Pixabay supply is thin, the next scheduled `youtube-bot.yml`
   run will keep retrying — an empty-supply cycle is a skip, not a
   failure.

## Studio Reach Import

1. Drop exported Studio or Google Sheets CSV files in
   `_data/studio_reach_exports/`.
2. Run the `studio-reach-import.yml` workflow (or
   `python scripts/import_studio_reach_export.py` locally).
3. Confirm `_data/analytics/studio_reach_latest.json` has non-zero rows.

## Quota Pressure

1. Run `python scripts/quota_preflight.py youtube-bot --json`.
2. Set `QUOTA_GUARD_MODE` to anything other than `block` (e.g. `off`) to
   stop hard-blocking while investigating.

## Dashboard Refresh

Run `python scripts/build_dashboard.py`. It renders even with no optional
analytics imports present.

## Alert Issue

The free GitHub Issues alert workflow (`ops-alert.yml`) opens or comments
on `Wild Brief automation alert` when a critical workflow fails. Treat the
issue as the active incident room, paste the failed run URL, and close it
only after the health check above passes again.
