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
        "72",
        "publishing",
        "Raw pending story target for hourly queue refresh before quality pruning.",
        "Raise only when prebuilding inventory.",
    ),
    FeatureFlag(
        "PUBLISH_BACKFILL_QUEUE_TARGET",
        "18",
        "publishing",
        "Raw pending-story target used only when publish-ready emergency backfill is needed.",
        "Set lower or rely on fetch-content during provider slowdowns.",
    ),
    FeatureFlag(
        "FETCH_REFRESH_TIMEOUT_SECONDS",
        "720",
        "publishing",
        "Maximum seconds for one Pexels queue refresh before skipping generated commits.",
        "Lower it if refresh jobs approach publish attempts.",
    ),
    FeatureFlag(
        "PUBLISH_BACKFILL_READY_TARGET",
        "6",
        "publishing",
        "Minimum editor-approved publish-ready candidates before a publish attempt.",
        "Lower only during provider outages.",
    ),
    FeatureFlag(
        "PUBLISH_BACKFILL_PENDING_BATCH",
        "6",
        "publishing",
        "Extra raw pending target added on each emergency backfill attempt.",
        "Lower if the publish workflow approaches timeout.",
    ),
    FeatureFlag(
        "PUBLISH_BACKFILL_TIMEOUT_SECONDS",
        "540",
        "publishing",
        "Maximum seconds allowed for one publish-workflow emergency backfill attempt.",
        "Lower it to preserve the upload slot; fetch-content handles deep replenishment.",
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
        "PUBLISH_HEARTBEAT_RUNTIME_MINUTES",
        "170",
        "publishing",
        "Minutes the bounded YouTube heartbeat keeps dispatching missed hourly slots.",
        "Lower to reduce runner time or disable the heartbeat workflow.",
    ),
    FeatureFlag(
        "PUBLISH_HEARTBEAT_DISPATCH_MINUTE",
        "6",
        "publishing",
        "Minute of each hour when the heartbeat dispatches a missed publisher run.",
        "Use an off-peak minute between 3 and 12.",
    ),
    FeatureFlag(
        "PUBLISH_HEARTBEAT_RECENT_RUN_TOLERANCE_MINUTES",
        "10",
        "publishing",
        "Lookback before a slot used by the heartbeat to avoid duplicate publisher dispatches.",
        "Raise if GitHub frequently delays publisher runs.",
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
    FeatureFlag(
        "PEXELS_SEARCH_PER_PAGE",
        "32",
        "discovery",
        "Pexels video results requested per search call.",
        "Lower if Pexels responses approach timeout.",
    ),
    FeatureFlag(
        "PEXELS_DISCOVERY_PAGES",
        "2",
        "discovery",
        "Maximum Pexels result pages searched when queue inventory is short.",
        "Set to 1 to search only the first page.",
    ),
    FeatureFlag(
        "PEXELS_BACKFILL_QUERY_TAKE",
        "6",
        "discovery",
        "Topic query count used during low-inventory Pexels backfill.",
        "Lower if provider quota becomes tight.",
    ),
    FeatureFlag(
        "PEXELS_TOPIC_CALL_BUDGET",
        "2",
        "discovery",
        "Maximum Pexels search calls allowed per topic per refresh run.",
        "Lower if provider quota becomes tight.",
    ),
    FeatureFlag(
        "PEXELS_DEEP_SEARCH_GAP",
        "8",
        "discovery",
        "Pending-story gap that enables deeper Pexels page search.",
        "Raise it to reserve deeper paging for emergencies.",
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
        "OPS_ALERTS_ENABLED",
        "1",
        "operations",
        "Create a GitHub Issue when a critical automation workflow fails.",
        "Set to 0 to silence issue alerts.",
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
    FeatureFlag("MUSIC_BED_ENABLED", "0", "production", "Allow optional music beds.", "Set to 0."),
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
