#!/usr/bin/env python3
"""Validate repo contracts that commonly drift in automation-heavy runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_slot_contracts import audit_slot_contracts  # noqa: E402
from scripts.check_schedule_sync import check_schedule_sync  # noqa: E402
from utils.feature_flags import docs_coverage  # noqa: E402

REQUIRED_FILES = (
    "404.html",
    "_config.yml",
    "robots.txt",
    "sitemap.xml",
    "scripts/import_studio_reach_export.py",
    "scripts/audit_slot_contracts.py",
    "scripts/security_manifest.py",
    "scripts/media_lifecycle.py",
    "scripts/merge_jsonl_state.py",
    "scripts/upload_intent.py",
    "scripts/production_smoke.py",
    ".well-known/security.txt",
    "utils/studio_reach_schema.py",
    "utils/api_quota_budget.py",
    "utils/feature_flags.py",
    "utils/time_semantics.py",
    "utils/retention_warehouse.py",
    "utils/media_lifecycle.py",
)

WORKFLOW_TOKENS = {
    ".github/workflows/quality-gate.yml": (
        "check_workflow_contracts.py",
        "check_repo_contracts.py",
        "audit_slot_contracts.py",
        "media_lifecycle.py --audit-tracked",
        "quota_preflight.py youtube-bot",
    ),
    ".github/workflows/storm-ambience.yml": (
        "generate_storm_ambience.py",
        "python upload_youtube.py --language=en",
    ),
    ".github/workflows/storm-shorts.yml": (
        "generate_storm_short.py",
        "python upload_youtube.py --language=en",
    ),
    ".github/workflows/cute-animals-shorts.yml": (
        "generate_cute_animal_short.py",
        "python upload_youtube.py --language=en",
        "CUTE_ANIMALS_ENABLED",
    ),
    ".github/workflows/baby-noise-ambience.yml": (
        "generate_baby_noise_ambience.py",
        "python upload_youtube.py --language=en",
        "BABY_NOISE_ENABLED",
    ),
    ".github/workflows/baby-noise-shorts.yml": (
        "generate_baby_noise_short.py",
        "python upload_youtube.py --language=en",
        "BABY_NOISE_ENABLED",
    ),
    ".github/workflows/ops-alert.yml": (
        "Storm Ambience - rain & thunder for sleep",
        "Storm Shorts - rain & thunder",
        "Baby Noise Ambience - white/pink/brown noise",
        "Baby Noise Shorts - white/pink/brown noise",
        "Production quality gate",
        "Build + deploy dashboard",
        "CodeQL",
        "Security, SBOM and license audit",
        "Production smoke",
        "OPS_ALERTS_ENABLED",
        "issues: write",
        "gh issue create",
        "gh issue comment",
    ),
    ".github/workflows/dashboard.yml": (
        "import_studio_reach_export.py",
        "build_dashboard.py",
        "Persist refreshed analytics",
    ),
    ".github/workflows/production-smoke.yml": (
        "production_smoke.py --json",
        'cron: "17 */6 * * *"',
    ),
}


def check_repo_contracts(root: Path = ROOT) -> list[str]:
    errors = list(check_schedule_sync(root))
    errors.extend(audit_slot_contracts(root).get("errors", []))
    for rel in REQUIRED_FILES:
        if not (root / rel).exists():
            errors.append(f"required file missing: {rel}")
    coverage = docs_coverage(root)
    for name in coverage.get("environment_doc_missing", []):
        errors.append(f"{name} is missing from docs/ENVIRONMENT.md")
    for name in coverage.get("env_example_missing", []):
        errors.append(f"{name} is missing from .env.example")
    for rel, tokens in WORKFLOW_TOKENS.items():
        text = (root / rel).read_text(encoding="utf-8") if (root / rel).exists() else ""
        for token in tokens:
            if token not in text:
                errors.append(f"{rel} is missing workflow token: {token}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    errors = check_repo_contracts(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"repo contract: {error}", file=sys.stderr)
        return 1
    print("repo contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
