# Wild Brief v1.0 Closure Contract

This project is considered closed for the current operating objective when the
checks below are true at the same time. New work should start from a new goal,
not from open-ended polishing.

## Closure Definition

- Hourly publishing is enabled and the latest slot has an `uploaded` row in
  `_data/upload_intents.jsonl`.
- Critical workflows are green: YouTube publisher, queue refresh, hourly
  heartbeat, watchdog, CodeQL, Pages and Production quality gate.
- Local contracts pass:
  - `python scripts/check_repo_contracts.py`
  - `python scripts/audit_slot_contracts.py`
  - `python scripts/check_schedule_sync.py`
  - `python -m pytest -q`
- Automation health is `excellent`.
- The queue has at least one clean `publish_ready` candidate, and the operating
  target is six clean reserve candidates.
- The dashboard renders and shows the `v1.0 closure status` card.
- No critical alert issue is open without an owner decision.

## No-Touch Rule

Do not change production code just because the project can be improved. Change
it only when one of these is true:

- A closure check fails.
- GitHub, YouTube, Pexels or a dependency changes behavior.
- A credential, quota or policy needs rotation.
- The operator explicitly chooses a new product goal.

## Routine Maintenance

Daily:

- Check the dashboard `v1.0 closure status`.
- Confirm the latest uploaded slot has a video id.
- Confirm `publish_ready` reserve is rebuilding toward `6/6`.

Weekly:

- Review `_data/reports/weekly-*.md`.
- Review `docs/INCIDENTS.md` if an alert issue was opened.
- Run the full local validation before large changes.

Monthly:

- Review dependency and security audit workflows.
- Rotate credentials only if required.
- Revisit `docs/EDITORIAL_HANDBOOK.md` only when the channel strategy changes.

## Golden Commands

```powershell
.\.venv\Scripts\python.exe scripts\check_repo_contracts.py
.\.venv\Scripts\python.exe scripts\audit_slot_contracts.py
.\.venv\Scripts\python.exe scripts\check_schedule_sync.py
.\.venv\Scripts\python.exe scripts\queue_ready_count.py --json
.\.venv\Scripts\python.exe -m pytest -q
```

## Recovery Priority

1. Restore evidence: make sure `_data/upload_intents.jsonl` has one `uploaded`
   row for the target slot.
2. Restore supply: get `publish_ready` back above the publish minimum, then
   toward the six-item reserve.
3. Restore health: run `scripts/run_intelligence_suite.py dashboard --strict`
   and rebuild the dashboard.
4. Restore confidence: wait for GitHub Actions to close green before declaring
   the incident resolved.
