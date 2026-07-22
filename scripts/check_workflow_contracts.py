#!/usr/bin/env python3
"""Guard GitHub Actions workflow safety contracts."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ".github/workflows"


def _top_level_key(text: str, key: str) -> bool:
    return bool(re.search(rf"^{re.escape(key)}:\s*$", text, flags=re.MULTILINE))


def _is_reusable_workflow_only(text: str) -> bool:
    return bool(re.search(r"^  workflow_call:\s*$", text, flags=re.MULTILINE)) and not any(
        re.search(rf"^  {event}:\s*$", text, flags=re.MULTILINE)
        for event in ("push", "pull_request", "pull_request_target", "schedule", "workflow_dispatch", "workflow_run")
    )


def _is_valid_action_ref(action: str) -> bool:
    """Require a pinned semver tag for official actions; allow SHA pins for any action.

    Local reusable workflows (./path/to/workflow.yml) and Docker actions are not
    checked here. Third-party actions must either use a semver tag or a full
    40-character SHA.
    """
    if "@" not in action:
        return False
    _, ref = action.rsplit("@", 1)
    # Full SHA pin is acceptable for any action.
    if re.fullmatch(r"[0-9a-f]{40}", ref, flags=re.IGNORECASE):
        return True
    # Official actions/* and github/* actions must use a semver tag.
    if action.startswith(("actions/", "github/")):
        return bool(re.fullmatch(r"v\d+(?:\.\d+)?(?:\.\d+)?", ref))
    # Third-party actions: accept any semver-looking tag to avoid being overly
    # restrictive, but still require a tag (no branch names).
    return bool(re.fullmatch(r"v?\d+(?:\.\d+)?(?:\.\d+)?", ref))


def _workflow_paths(root: Path) -> list[Path]:
    workflows = root / WORKFLOW_DIR
    return sorted(
        p for p in workflows.glob("*.yml") if not any(part == "archive" for part in p.relative_to(root).parts)
    )


def check_workflow_contracts(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for path in _workflow_paths(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")

        try:
            parsed: dict[str, Any] = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{rel}: invalid YAML: {exc}")
            continue

        if re.search(r"pull_request_target\s*:", text, flags=re.IGNORECASE):
            errors.append(f"{rel}: pull_request_target is not allowed")
        if not _top_level_key(text, "permissions"):
            errors.append(f"{rel}: must declare explicit top-level permissions")
        if re.search(r"^\s*permissions:\s*write-all\s*$", text, flags=re.MULTILINE | re.IGNORECASE):
            errors.append(f"{rel}: write-all permissions are not allowed")
        if not _top_level_key(text, "concurrency") and not _is_reusable_workflow_only(text):
            errors.append(f"{rel}: must declare concurrency")

        for action in re.findall(r"uses:\s*['\"]?([^'\"\s]+)", text):
            if re.search(r"@(main|master|HEAD)$", action, flags=re.IGNORECASE):
                errors.append(f"{rel}: action {action} must use a released version")
            if not _is_valid_action_ref(action):
                errors.append(f"{rel}: action {action} must use a pinned semantic version tag (e.g. v4, v4.0.0)")

        jobs = parsed.get("jobs") or {}
        if not isinstance(jobs, dict) or not jobs:
            errors.append(f"{rel}: must define at least one job")
            continue
        for name, job in jobs.items():
            if not isinstance(job, dict):
                errors.append(f"{rel}: job {name} must be a mapping")
                continue
            if "uses" not in job and "timeout-minutes" not in job:
                errors.append(f"{rel}: job {name} must set timeout-minutes")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    errors = check_workflow_contracts(Path(args.root).resolve())
    if errors:
        print("WORKFLOW_CONTRACTS_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"WORKFLOW_CONTRACTS_OK workflows={len(_workflow_paths(Path(args.root).resolve()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
