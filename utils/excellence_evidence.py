"""Derive excellence claims from measurable, inspectable evidence.

The collector is deliberately conservative: source code or a configured workflow
never counts as proof that production behaved correctly.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils.atomic_state import load_versioned


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _iso(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def live_claims(journals: Iterable[Path]) -> tuple[dict[str, bool], dict[str, Any]]:
    """Evaluate live continuity without trusting hand-written pass flags."""
    attempts: list[dict[str, Any]] = []
    sessions: list[tuple[datetime, datetime]] = []
    sources: list[str] = []
    recovery_latencies: list[float] = []
    chaos_recoveries = 0
    for path in journals:
        payload = _read_json(path)
        rows = payload.get("attempts", [])
        if not isinstance(rows, list):
            continue
        valid_rows = [row for row in rows if isinstance(row, dict)]
        attempts.extend(valid_rows)
        for previous, current in zip(valid_rows, valid_rows[1:], strict=False):
            if previous.get("outcome") != "disconnected":
                continue
            latency = current.get("recovery_latency_seconds")
            if isinstance(latency, (int, float)) and 0 <= float(latency) <= 60:
                recovery_latencies.append(float(latency))
                if (
                    previous.get("error_type") == "CalledProcessError"
                    and current.get("broadcast_id") != previous.get("broadcast_id")
                ):
                    chaos_recoveries += 1
        sources.append(str(path))
        started = _iso(payload.get("started_at"))
        completed = _iso(payload.get("completed_at"))
        if started and completed and completed >= started:
            sessions.append((started, completed))

    # Merge intervals so overlapping runner handoffs count as continuous channel coverage.
    merged: list[list[datetime]] = []
    for start, end in sorted(sessions):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    longest = max(((end - start).total_seconds() for start, end in merged), default=0.0)
    completed_attempts = sum(row.get("outcome") == "completed" for row in attempts)
    claims = {
        "immediate_failure_handoff": bool(recovery_latencies),
        "six_hour_session": longest >= 21_600,
        "chaos_disconnect_recovery": chaos_recoveries > 0,
    }
    details = {
        "sources": sources,
        "attempt_count": len(attempts),
        "completed_attempts": completed_attempts,
        "recovery_latencies_seconds": recovery_latencies,
        "chaos_recoveries": chaos_recoveries,
        "longest_continuous_coverage_seconds": round(longest, 3),
    }
    return claims, details


def verified_claims(
    manifests: Iterable[Path], *, now: datetime | None = None
) -> tuple[dict[str, dict[str, bool]], list[dict[str, Any]]]:
    """Load expiring external claims that carry a verifier and evidence URL.

    This is the bridge for GitHub/YouTube observations. A bare boolean is not
    accepted: claims must be current, attributable and link to their evidence.
    """
    current = now or datetime.now(UTC)
    result: dict[str, dict[str, bool]] = {}
    accepted: list[dict[str, Any]] = []
    for path in manifests:
        payload = _read_json(path)
        observations = payload.get("observations", [])
        if not isinstance(observations, list):
            continue
        for row in observations:
            if not isinstance(row, dict) or row.get("passed") is not True:
                continue
            area, criterion = str(row.get("area", "")), str(row.get("criterion", ""))
            observed, expires = _iso(row.get("observed_at")), _iso(row.get("expires_at"))
            if not area or not criterion or not observed or not expires or not observed <= current <= expires:
                continue
            if not str(row.get("verifier", "")).strip() or not str(row.get("evidence_url", "")).startswith("https://"):
                continue
            result.setdefault(area, {})[criterion] = True
            accepted.append({**row, "manifest": str(path)})
    return result, accepted


def youtube_learning_claims(
    data_root: Path, *, now: datetime | None = None
) -> tuple[dict[str, bool], dict[str, Any]]:
    """Derive learning claims from actual joined observations, never source code."""
    current = now or datetime.now(UTC)
    analytics = _read_json(data_root / "analytics.json")
    collected = _iso(analytics.get("collected_at"))
    analytics_age_hours = (
        (current - collected).total_seconds() / 3600.0
        if collected and collected <= current
        else None
    )
    catalog = load_versioned(data_root / "catalog_memory.json", 1, {}, [])
    rows = catalog if isinstance(catalog, list) else []
    joined = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("youtube_video_id")
        and isinstance(row.get("fitness"), dict)
        and row.get("fitness_window")
    ]
    fitness_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("fitness"), dict)
        and isinstance(row["fitness"].get("score"), (int, float))
        and isinstance(row["fitness"].get("confidence"), (int, float))
        and row.get("fitness_window")
    ]
    evolved = [
        row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("genome"), dict)
        and int(row["genome"].get("generation", 0)) > 0
        and len(row["genome"].get("mutations", [])) == 1
    ]
    ledger = load_versioned(
        data_root / "research_ledger.json", 1, {}, {"hypotheses": {}, "experiments": {}}
    )
    experiments = ledger.get("experiments", {}) if isinstance(ledger, dict) else {}
    causal_results = [
        {"experiment_id": experiment_id, **experiment["result"]}
        for experiment_id, experiment in experiments.items()
        if isinstance(experiment, dict)
        and isinstance(experiment.get("result"), dict)
        and int(experiment["result"].get("samples", 0)) >= 30
        and experiment["result"].get("status") in {"supported", "contradicted", "inconclusive"}
    ]
    claims = {
        "daily_analytics": analytics_age_hours is not None and analytics_age_hours <= 36,
        "catalog_performance_join": bool(joined),
        "fitness_samples_min_30": len(fitness_rows) >= 30,
        "active_governed_evolution": bool(evolved),
        "causal_experiment_results": bool(causal_results),
    }
    details = {
        "analytics_collected_at": collected.isoformat() if collected else None,
        "analytics_age_hours": round(analytics_age_hours, 3) if analytics_age_hours is not None else None,
        "catalog_records": len(rows),
        "joined_fitness_records": len(joined),
        "fitness_records": len(fitness_rows),
        "governed_evolution_records": len(evolved),
        "causal_results": causal_results,
    }
    return claims, details


def build_evidence(data_root: Path, manifest_paths: Iterable[Path] = ()) -> dict[str, Any]:
    live, live_details = live_claims(data_root.glob("**/live_continuity.json"))
    learning, learning_details = youtube_learning_claims(data_root)
    external, accepted = verified_claims(manifest_paths)
    evidence = {area: dict(criteria) for area, criteria in external.items()}
    evidence.setdefault("live_continuity", {}).update(live)
    evidence.setdefault("youtube_learning", {}).update(learning)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence": evidence,
        "details": {
            "live_continuity": live_details,
            "youtube_learning": learning_details,
            "accepted_external_observations": accepted,
        },
    }
