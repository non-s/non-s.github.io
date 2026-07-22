test:
    python -m pytest -q

contracts:
    python scripts/check_schedule_sync.py
    python scripts/audit_slot_contracts.py
    python scripts/check_repo_contracts.py
    python scripts/check_workflow_contracts.py

dashboard:
    python scripts/build_dashboard.py
