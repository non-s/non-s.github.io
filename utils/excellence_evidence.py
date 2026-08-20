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


def build_evidence(data_root: Path, manifest_paths: Iterable[Path] = ()) -> dict[str, Any]:
    live, live_details = live_claims(data_root.glob("**/live_continuity.json"))
    external, accepted = verified_claims(manifest_paths)
    evidence = {area: dict(criteria) for area, criteria in external.items()}
    evidence.setdefault("live_continuity", {}).update(live)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence": evidence,
        "details": {"live_continuity": live_details, "accepted_external_observations": accepted},
    }
