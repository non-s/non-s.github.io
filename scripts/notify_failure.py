"""
scripts/notify_failure.py — notifica o Discord quando um workflow falha.

Chamado como o ultimo passo de cada workflow, com `if: failure()`. Sem
DISCORD_WEBHOOK_URL configurado, send_notification() so loga um warning e
retorna False - nunca falha o step por si so.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.discord_webhook import notify_error  # noqa: E402
from utils.log_config import configure_logging  # noqa: E402


def _run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return "(run URL indisponivel)"


def main() -> int:
    configure_logging()
    workflow = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_WORKFLOW", "workflow")
    notify_error(f"{workflow} falhou", f"Run: {_run_url()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
