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
        "YOUTUBE_PUBLISHING_ENABLED",
        "0",
        "publishing",
        "Master switch for the hourly lofi Shorts publisher.",
        "Set to 0 to pause publishing entirely.",
    ),
    FeatureFlag(
        "ADAPTIVE_CADENCE_ENABLED",
        "1",
        "publishing",
        "Enable adaptive publish/skip decisions from the canonical 24/day UTC grid: "
        "00:00, 01:00, 02:00, 03:00, 04:00, 05:00, 06:00, 07:00, 08:00, 09:00, 10:00, "
        "11:00, 12:00, 13:00, 14:00, 15:00, 16:00, 17:00, 18:00, 19:00, 20:00, 21:00, "
        "22:00 and 23:00.",
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
        "YOUTUBE_DESCRIPTION_MODE",
        "full",
        "publishing",
        "YouTube description mode: empty or full.",
        "Set to empty for a minimal-description rollback.",
    ),
    FeatureFlag(
        "CHANNEL_PLAYLIST_PREFIX",
        "",
        "publishing",
        "Text prepended to every auto-created playlist title.",
        "Unset it to use bare playlist titles.",
    ),
    FeatureFlag(
        "CHANNEL_DEFAULT_HASHTAGS",
        "#Shorts",
        "publishing",
        "Comma-separated hashtags appended to the description when not already present.",
        "Set to #Shorts to drop channel-specific tags.",
    ),
    FeatureFlag(
        "CHANNEL_PLAYLIST_DESCRIPTION",
        "Shorts grouped for easier binge watching.",
        "publishing",
        "Description text used for every auto-created playlist.",
        "Unset it to use the generic default.",
    ),
    FeatureFlag(
        "PUBLISH_RECOVERY_DELAY_MINUTES",
        "40",
        "publishing",
        "Minutes after an hourly slot when recovery cron maps back to the intended slot.",
        "Set to 40.",
    ),
    FeatureFlag(
        "PUBLISH_HEARTBEAT_RECENT_RUN_TOLERANCE_MINUTES",
        "10",
        "publishing",
        "Lookback before a slot used by the heartbeat to avoid duplicate publisher dispatches.",
        "Raise if GitHub frequently delays publisher runs.",
    ),
    FeatureFlag(
        "YOUTUBE_SCHEDULE_UPLOADS",
        "0",
        "publishing",
        "Upload as private scheduled videos with publishAt instead of immediate public uploads.",
        "Set to 0 for normal slot-time public uploads.",
    ),
    FeatureFlag(
        "YOUTUBE_SCHEDULE_START_UTC",
        "",
        "publishing",
        "Optional RFC3339 start time for scheduled upload batches.",
        "Unset it.",
    ),
    FeatureFlag(
        "YOUTUBE_SCHEDULE_SLOTS_UTC",
        "",
        "publishing",
        "Optional comma-separated HH:MM UTC slots for scheduled upload batches.",
        "Unset to use the canonical publish grid.",
    ),
    FeatureFlag(
        "YOUTUBE_SCHEDULE_OFFSET",
        "0",
        "publishing",
        "Starting index into the rolling schedule when adding another scheduled batch.",
        "Reset to 0 after batch upload.",
    ),
    FeatureFlag(
        "STUDIO_REACH_IMPORT_ENABLED", "1", "analytics", "Import manually exported Shorts Reach CSV data.", "Set to 0."
    ),
    FeatureFlag(
        "YOUTUBE_REPORTING_ENABLED",
        "0",
        "analytics",
        "Enable optional Reporting API CSV backfill folders.",
        "Set to 0.",
    ),
    FeatureFlag(
        "QUOTA_GUARD_ENABLED",
        "1",
        "operations",
        "Block runs projected to exceed quota budget.",
        "Set to 0 for passive logging.",
    ),
    FeatureFlag(
        "QUOTA_GUARD_MODE", "block", "operations", "Quota guard mode: anything other than block just warns.", "Use off."
    ),
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
        "COMMUNITY_ENGAGEMENT_ENABLED",
        "0",
        "community",
        "Master switch for comment replies and the weekly Community post draft, "
        "independent of YOUTUBE_PUBLISHING_ENABLED.",
        "Set to 0 to pause both.",
    ),
    FeatureFlag(
        "COMMENT_REPLY_MAX_PER_RUN",
        "15",
        "community",
        "Cap on comment replies posted per community-comment-replies.yml run.",
        "Lower it, or set COMMUNITY_ENGAGEMENT_ENABLED to 0.",
    ),
    FeatureFlag(
        "STORM_AMBIENCE_ENABLED",
        "0",
        "publishing",
        "Master switch for the storm-ambience.yml pillar (real rain/thunder ambience), "
        "independent of YOUTUBE_PUBLISHING_ENABLED.",
        "Set to 0 to pause this pillar.",
    ),
    FeatureFlag(
        "STORM_MIN_DURATION_MINUTES",
        "45",
        "publishing",
        "Minimum runtime (minutes) for a generated storm-ambience video.",
        "Lower it for faster/smaller uploads.",
    ),
    FeatureFlag(
        "STORM_MAX_DURATION_MINUTES",
        "75",
        "publishing",
        "Maximum runtime (minutes) for a generated storm-ambience video.",
        "Lower it for faster/smaller uploads.",
    ),
    FeatureFlag(
        "STORM_MUSIC_LAYER_PROBABILITY",
        "0.35",
        "publishing",
        "Chance (0.0-1.0) a storm-ambience video also layers in one quiet Jamendo track.",
        "Set to 0 for pure rain/thunder ambience only.",
    ),
    FeatureFlag(
        "LIVE_CONTENT_PILLAR",
        "lofi",
        "publishing",
        "Which pillar scripts/live_stream_dynamic.py broadcasts: lofi (anime desk loop) or storm "
        "(rain & thunder ambience).",
        "Set to lofi to restore the original 24/7 live stream.",
    ),
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
