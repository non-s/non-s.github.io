"""Central registry for Wild Brief feature flags.

The registry is intentionally small and static: it gives docs, tests and
workflow checks one place to validate the operator surface without importing
heavy production modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FeatureFlag:
    name: str
    default: str
    owner: str
    description: str
    rollback: str


FLAGS: tuple[FeatureFlag, ...] = (
    FeatureFlag(
        "ADAPTIVE_CADENCE_ENABLED",
        "1",
        "publishing",
        "Enable adaptive publish/skip decisions.",
        "Set to 0 for legacy slot behavior.",
    ),
    FeatureFlag("ALLOW_FLEX_SLOT", "0", "publishing", "Allow one extra operator-defined UTC slot.", "Set to 0."),
    FeatureFlag("FLEX_SLOT_UTC", "", "publishing", "Optional HH:MM UTC flex slot.", "Unset it."),
    FeatureFlag(
        "MIN_SLOT_PUBLISH_SCORE",
        "72",
        "publishing",
        "Minimum publish score for adaptive cadence.",
        "Lower or disable adaptive cadence.",
    ),
    FeatureFlag(
        "MIN_QUEUE_OPPORTUNITY_SCORE",
        "50",
        "publishing",
        "Minimum queue opportunity score for a slot.",
        "Lower or disable adaptive cadence.",
    ),
    FeatureFlag(
        "QUEUE_TARGET_PENDING",
        "1",
        "publishing",
        "Pending story target for on-demand hourly queue refresh.",
        "Raise only when prebuilding inventory.",
    ),
    FeatureFlag(
        "YOUTUBE_DESCRIPTION_MODE",
        "empty",
        "publishing",
        "YouTube description mode: empty or full.",
        "Set to full.",
    ),
    FeatureFlag(
        "PUBLISH_RECOVERY_DELAY_MINUTES",
        "40",
        "publishing",
        "Minutes after an hourly slot when recovery cron maps back to the intended slot.",
        "Set to 40.",
    ),
    FeatureFlag(
        "STUDIO_REACH_IMPORT_ENABLED", "1", "analytics", "Import manually exported Shorts Reach CSV data.", "Set to 0."
    ),
    FeatureFlag(
        "STUDIO_REACH_IMPORT_PATH",
        "_data/studio_reach_exports",
        "analytics",
        "Path to Studio/Sheets reach CSV exports.",
        "Leave empty or remove files.",
    ),
    FeatureFlag(
        "TOPIC_FRESHNESS_ENABLED", "1", "discovery", "Annotate queue entries with free freshness signals.", "Set to 0."
    ),
    FeatureFlag("OPENING_AUDIT_ENABLED", "1", "production", "Score the first second opening package.", "Set to 0."),
    FeatureFlag(
        "OPENING_AUDIT_STRICT",
        "1",
        "production",
        "Reject openings below the configured score.",
        "Set to 0 for informational mode.",
    ),
    FeatureFlag(
        "OPENING_MIN_SCORE",
        "72",
        "production",
        "Minimum opening audit score.",
        "Lower threshold or disable strict mode.",
    ),
    FeatureFlag("OPENING_GATE_MODE", "warn", "production", "Opening gate v2 mode: off, warn or block.", "Use warn."),
    FeatureFlag(
        "OPENING_GATE_MIN_SCORE",
        "78",
        "production",
        "Minimum opening gate v2 score.",
        "Lower threshold or set OPENING_GATE_MODE=off.",
    ),
    FeatureFlag("FACT_GUARD_MODE", "block", "production", "Claim risk mode: warn or block.", "Use warn."),
    FeatureFlag("RIGHTS_GUARD_MODE", "block", "production", "Rights guard mode: warn or block.", "Use warn."),
    FeatureFlag(
        "ORIGINALITY_PACK_MODE",
        "warn",
        "production",
        "Originality pack completeness mode: warn or block.",
        "Use warn.",
    ),
    FeatureFlag(
        "SESSION_GRAPH_ENABLED", "1", "growth", "Build post-upload handoff and sequel graph artifacts.", "Set to 0."
    ),
    FeatureFlag(
        "COMMENT_TO_SHORT_ENABLED", "1", "growth", "Promote strong viewer questions into Short ideas.", "Set to 0."
    ),
    FeatureFlag(
        "COMMENT_TO_SHORT_MIN_SCORE",
        "64",
        "growth",
        "Minimum score to add a comment idea to the queue.",
        "Raise threshold or disable.",
    ),
    FeatureFlag("COMMENT_TO_SHORT_MAX_ITEMS", "6", "growth", "Maximum comment ideas added per run.", "Lower limit."),
    FeatureFlag(
        "QUOTA_GUARD_ENABLED",
        "1",
        "operations",
        "Block runs projected to exceed quota budget.",
        "Set to 0 for passive logging.",
    ),
    FeatureFlag("QUOTA_GUARD_MODE", "block", "operations", "Quota guard mode: warn or block.", "Use warn."),
    FeatureFlag(
        "UPLOAD_IDEMPOTENCY_MODE",
        "block",
        "operations",
        "Upload idempotency mode: warn or block duplicate completed intents.",
        "Use warn.",
    ),
    FeatureFlag(
        "UPLOAD_SLOT_IDEMPOTENCY_MODE",
        "block",
        "operations",
        "Block a second successful upload for the same publish slot.",
        "Use warn.",
    ),
    FeatureFlag(
        "MEDIA_LIFECYCLE_CLEANUP",
        "1",
        "operations",
        "Delete generated media after successful upload while keeping metadata markers.",
        "Set to 0 temporarily while debugging renders.",
    ),
    FeatureFlag(
        "OPS_GUARDIAN_ENFORCE",
        "1",
        "operations",
        "Apply ops guardian paused-topic guidance during candidate selection.",
        "Set to 0.",
    ),
    FeatureFlag(
        "QUOTA_GUARD_MAX_DAILY_RATIO",
        "0.95",
        "operations",
        "Daily budget ratio before guard trips.",
        "Raise ratio or disable.",
    ),
    FeatureFlag("QUOTA_LEDGER_ENABLED", "1", "operations", "Write API quota ledger artifacts.", "Set to 0."),
    FeatureFlag(
        "YOUTUBE_DAILY_QUOTA_BUDGET",
        "10000",
        "operations",
        "Conservative daily YouTube quota unit budget.",
        "Raise only after checking API quota.",
    ),
    FeatureFlag(
        "YOUTUBE_DAILY_UPLOAD_BUDGET",
        "100",
        "operations",
        "Conservative daily YouTube upload-call budget.",
        "Match the Google Cloud upload quota.",
    ),
    FeatureFlag(
        "YOUTUBE_REPORTING_ENABLED",
        "0",
        "analytics",
        "Enable optional Reporting API CSV backfill folders.",
        "Set to 0.",
    ),
    FeatureFlag(
        "WAREHOUSE_COMPACTION_ENABLED", "1", "analytics", "Write monthly JSONL analytics partitions.", "Set to 0."
    ),
    FeatureFlag("MUSIC_BED_ENABLED", "1", "production", "Allow autonomous public-domain music beds.", "Set to 0."),
    FeatureFlag(
        "ARCHIVE_AUDIO_ENABLED",
        "1",
        "production",
        "Allow Internet Archive public-domain/CC0 audio candidates after license metadata checks.",
        "Set to 0.",
    ),
    FeatureFlag(
        "ARCHIVE_AUDIO_ROWS",
        "12",
        "production",
        "Limit Archive API search breadth per mood.",
        "Lower rows or set ARCHIVE_AUDIO_ENABLED=0.",
    ),
    FeatureFlag(
        "ARCHIVE_AUDIO_CACHE_DIR",
        "_data/archive_audio_cache",
        "production",
        "Cache downloaded Archive audio.",
        "Remove cache and disable Archive audio.",
    ),
    FeatureFlag(
        "MUSIC_BED_CANARY_PERCENT",
        "5",
        "production",
        "Percent of Shorts allowed into safe music-bed canary.",
        "Set to 0.",
    ),
    FeatureFlag(
        "SEO_METADATA_LINT_ENABLED",
        "1",
        "production",
        "Attach deterministic SEO/metadata lint to every Short.",
        "Set to 0.",
    ),
    FeatureFlag("SEO_METADATA_LINT_STRICT", "0", "production", "Reject metadata with SEO lint errors.", "Set to 0."),
    FeatureFlag("COQUI_TTS_COMMAND", "", "resilience", "Optional local Coqui-compatible TTS command.", "Unset it."),
    FeatureFlag("COQUI_TTS_MODEL", "", "resilience", "Optional Coqui model name.", "Unset it."),
    FeatureFlag("COQUI_TTS_LOCALE_ARG", "0", "resilience", "Pass language_idx to Coqui CLI.", "Set to 0."),
)


def registry() -> tuple[FeatureFlag, ...]:
    return FLAGS


def flag_names() -> list[str]:
    return [flag.name for flag in FLAGS]


def snapshot(env: dict | None = None) -> dict[str, str]:
    source = env or os.environ
    return {flag.name: str(source.get(flag.name, flag.default)) for flag in FLAGS}


def markdown_table() -> str:
    lines = ["| Flag | Default | Owner | Purpose | Rollback |", "|---|---:|---|---|---|"]
    for flag in FLAGS:
        lines.append(f"| `{flag.name}` | `{flag.default}` | {flag.owner} | {flag.description} | {flag.rollback} |")
    return "\n".join(lines)


def missing_from_text(text: str) -> list[str]:
    return [flag.name for flag in FLAGS if flag.name not in text]


def docs_coverage(root: Path) -> dict:
    env_doc = (
        (root / "docs" / "ENVIRONMENT.md").read_text(encoding="utf-8")
        if (root / "docs" / "ENVIRONMENT.md").exists()
        else ""
    )
    env_example = (root / ".env.example").read_text(encoding="utf-8") if (root / ".env.example").exists() else ""
    return {
        "environment_doc_missing": missing_from_text(env_doc),
        "env_example_missing": missing_from_text(env_example),
    }
