from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()
WORKFLOWS = ROOT / ".github" / "workflows"
failures: list[str] = []


def fail(path: Path, message: str) -> None:
    failures.append(f"{path.relative_to(ROOT)}: {message}")


def job_blocks(text: str) -> list[tuple[str, str]]:
    match = re.search(r"^jobs:\s*$", text, flags=re.MULTILINE)
    if not match:
        return []
    jobs_text = text[match.start() :]
    return [
        (item.group(1), item.group(2))
        for item in re.finditer(
            r"^  ([A-Za-z0-9_-]+):\s*$(.*?)(?=^  [A-Za-z0-9_-]+:\s*$|\Z)",
            jobs_text,
            flags=re.MULTILINE | re.DOTALL,
        )
    ]


for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
    text = path.read_text(encoding="utf-8")
    if re.search(r"pull_request_target\s*:", text, flags=re.IGNORECASE):
        fail(path, "pull_request_target is not allowed for this repository")
    if not re.search(r"^permissions:\s*$", text, flags=re.MULTILINE):
        fail(path, "must declare explicit top-level permissions")
    if re.search(
        r"^permissions:\s*write-all\s*$", text, flags=re.MULTILINE | re.IGNORECASE
    ):
        fail(path, "write-all permissions are not allowed")
    if not re.search(r"^concurrency:\s*$", text, flags=re.MULTILINE):
        fail(path, "must declare concurrency to prevent duplicate production runs")
    for action in re.findall(r"uses:\s*['\"]?([^'\"\s]+)", text):
        if re.search(r"@(main|master|HEAD)$", action, flags=re.IGNORECASE):
            fail(path, f"action {action} must use a released version")
    jobs = job_blocks(text)
    if not jobs:
        fail(path, "must define at least one job")
    for name, body in jobs:
        if not re.search(r"^\s{4}timeout-minutes:\s*\d+\s*$", body, flags=re.MULTILINE):
            fail(path, f"job {name} must set timeout-minutes")

if failures:
    print("WORKFLOW_CONTRACTS_FAILED")
    for item in failures:
        print(f"- {item}")
    raise SystemExit(1)

print("WORKFLOW_CONTRACTS_OK")
