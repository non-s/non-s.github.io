# Contributing

## Local checks

Run the critical path before pushing:

```bash
python -m compileall -q .
python -m pytest -q
python scripts/check_schedule_sync.py
python scripts/audit_slot_contracts.py
python scripts/check_repo_contracts.py
python scripts/doctor.py --json
```

## Automation rules

- Keep `utils/publish_schedule.py`, `youtube-bot.yml`, `youtube-watchdog.yml` and docs in slot sync.
- Add rollback flags to `.env.example`, `docs/ENVIRONMENT.md` and `utils/feature_flags.py`.
- Prefer warn mode for new production gates until real channel data proves the block threshold.
- Do not commit OAuth tokens, rendered media, private audio assets or local caches.
- Preserve append-only ledgers such as `_data/upload_intents.jsonl`, `_data/source_provenance.jsonl` and `_data/originality_pack.jsonl`.
