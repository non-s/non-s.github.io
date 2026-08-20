"""Versioned scientific-method records with single-variable safeguards."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils.atomic_state import load_versioned, save_versioned
from utils.research_engine import hypothesis_status
from utils.state_lock import state_lock

RESEARCH_SCHEMA_VERSION = 1
VALID_STATUSES = {"planned", "running", "insufficient_data", "inconclusive", "supported", "contradicted"}
TERMINAL_STATUSES = {"inconclusive", "supported", "contradicted"}
SUPPORTED_CONTROLS = {
    "genome.motion.melt_rate": ("melt_rate", 0.02, 2.5),
    "genome.geometry.folds_theta": ("folds_theta", 1.0, 12.0),
    "genome.geometry.folds_phi": ("folds_phi", 1.0, 12.0),
    "genome.geometry.strand_count": ("strand_count", 4.0, 24.0),
}


def _identifier(prefix: str, value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:16]}"


@dataclass(frozen=True)
class Hypothesis:
    statement: str
    independent_variable: str
    dependent_metric: str
    expected_direction: str
    rationale: str
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def hypothesis_id(self) -> str:
        stable = {
            "statement": self.statement,
            "independent_variable": self.independent_variable,
            "dependent_metric": self.dependent_metric,
            "expected_direction": self.expected_direction,
            "rationale": self.rationale,
        }
        return _identifier("hyp", stable)


@dataclass(frozen=True)
class Experiment:
    hypothesis_id: str
    control_content_ids: tuple[str, ...]
    treatment_content_ids: tuple[str, ...]
    changed_variables: dict[str, Any]
    format: str
    target_window: str
    status: str = "planned"

    def __post_init__(self) -> None:
        if len(self.changed_variables) != 1:
            raise ValueError("causal experiments must change exactly one variable")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid experiment status: {self.status}")

    @property
    def experiment_id(self) -> str:
        return _identifier("exp", asdict(self))


def record_hypothesis(path: Path, hypothesis: Hypothesis) -> str:
    with state_lock(path):
        ledger = load_versioned(path, RESEARCH_SCHEMA_VERSION, {}, {"hypotheses": {}, "experiments": {}})
        ledger.setdefault("hypotheses", {})[hypothesis.hypothesis_id] = {
            **asdict(hypothesis),
            "status": "planned",
            "samples": 0,
            "confidence": 0.0,
        }
        save_versioned(path, ledger, RESEARCH_SCHEMA_VERSION)
    return hypothesis.hypothesis_id


def record_experiment(path: Path, experiment: Experiment) -> str:
    with state_lock(path):
        ledger = load_versioned(path, RESEARCH_SCHEMA_VERSION, {}, {"hypotheses": {}, "experiments": {}})
        if experiment.hypothesis_id not in ledger.get("hypotheses", {}):
            raise ValueError("experiment references an unknown hypothesis")
        ledger.setdefault("experiments", {})[experiment.experiment_id] = asdict(experiment)
        save_versioned(path, ledger, RESEARCH_SCHEMA_VERSION)
    return experiment.experiment_id


def record_result(path: Path, experiment_id: str, *, effect: float | None, samples: int, confidence: float) -> str:
    with state_lock(path):
        ledger = load_versioned(path, RESEARCH_SCHEMA_VERSION, {}, {"hypotheses": {}, "experiments": {}})
        experiment = ledger.get("experiments", {}).get(experiment_id)
        if not isinstance(experiment, dict):
            raise ValueError("unknown experiment")
        status = hypothesis_status(effect, samples, confidence)
        experiment["result"] = {"effect": effect, "samples": samples, "confidence": confidence, "status": status}
        experiment["status"] = status
        hypothesis = ledger["hypotheses"].get(experiment["hypothesis_id"])
        if isinstance(hypothesis, dict):
            hypothesis.update({"status": status, "samples": samples, "confidence": confidence})
        save_versioned(path, ledger, RESEARCH_SCHEMA_VERSION)
    return status


def plan_experiment(
    path: Path,
    hypothesis_id: str,
    *,
    independent_variable: str,
    format: str,
    target_window: str,
) -> str | None:
    """Create at most one active, executable experiment per format."""
    if independent_variable not in SUPPORTED_CONTROLS or format not in {"short", "long"}:
        return None
    with state_lock(path):
        ledger = load_versioned(path, RESEARCH_SCHEMA_VERSION, {}, {"hypotheses": {}, "experiments": {}})
        if hypothesis_id not in ledger.get("hypotheses", {}):
            return None
        experiments = ledger.setdefault("experiments", {})
        for experiment_id, raw in experiments.items():
            if not isinstance(raw, dict):
                continue
            if raw.get("hypothesis_id") == hypothesis_id:
                return str(experiment_id)
            if raw.get("format") == format and raw.get("status") in {"planned", "running", "insufficient_data"}:
                return None
        experiment = Experiment(
            hypothesis_id=hypothesis_id,
            control_content_ids=(),
            treatment_content_ids=(),
            changed_variables={
                independent_variable: {
                    "operation": "multiply",
                    "factor": 1.2,
                }
            },
            format=format,
            target_window=target_window,
        )
        experiments[experiment.experiment_id] = asdict(experiment)
        save_versioned(path, ledger, RESEARCH_SCHEMA_VERSION)
        return experiment.experiment_id


def assign_experiment(path: Path, profile: dict[str, Any], format: str) -> dict[str, Any] | None:
    """Randomize by deterministic balance and change exactly one control for treatment."""
    with state_lock(path):
        ledger = load_versioned(path, RESEARCH_SCHEMA_VERSION, {}, {"hypotheses": {}, "experiments": {}})
        candidates = [
            (experiment_id, raw)
            for experiment_id, raw in ledger.get("experiments", {}).items()
            if isinstance(raw, dict)
            and raw.get("format") == format
            and raw.get("status") in {"planned", "running", "insufficient_data"}
        ]
        if not candidates:
            return None
        experiment_id, experiment = sorted(candidates, key=lambda item: item[0])[0]
        changed = experiment.get("changed_variables", {})
        if not isinstance(changed, dict) or len(changed) != 1:
            return None
        variable, intervention = next(iter(changed.items()))
        control = experiment.get("control_content_ids", [])
        treatment = experiment.get("treatment_content_ids", [])
        variant = "control" if len(control) <= len(treatment) else "treatment"
        before = None
        after = None
        if variant == "treatment":
            target = SUPPORTED_CONTROLS.get(str(variable))
            if target is None or not isinstance(intervention, dict):
                return None
            field, lower, upper = target
            before = float(profile.get(field, lower))
            factor = float(intervention.get("factor", 1.2))
            after = min(upper, max(lower, before * factor))
            if field in {"folds_theta", "folds_phi", "strand_count"}:
                after = float(max(int(lower), min(int(upper), round(after))))
                profile[field] = int(after)
            else:
                after = round(after, 6)
                profile[field] = after
        experiment["status"] = "running"
        hypothesis = ledger.get("hypotheses", {}).get(experiment.get("hypothesis_id"), {})
        save_versioned(path, ledger, RESEARCH_SCHEMA_VERSION)
    assignment = {
        "experiment_id": experiment_id,
        "hypothesis_id": experiment["hypothesis_id"],
        "variant": variant,
        "changed_variables": copy.deepcopy(changed),
        "observed_intervention": {"field": variable, "before": before, "after": after},
        "target_window": experiment["target_window"],
        "hypothesis": copy.deepcopy(hypothesis) if isinstance(hypothesis, dict) else {},
    }
    profile["experiment"] = assignment
    return assignment


def record_assignment(path: Path, experiment_id: str, variant: str, content_id: str) -> None:
    """Attach the immutable content id to its assigned cohort idempotently."""
    cohort = "control_content_ids" if variant == "control" else "treatment_content_ids"
    with state_lock(path):
        ledger = load_versioned(path, RESEARCH_SCHEMA_VERSION, {}, {"hypotheses": {}, "experiments": {}})
        experiment = ledger.get("experiments", {}).get(experiment_id)
        if not isinstance(experiment, dict):
            raise ValueError("unknown experiment")
        ids = experiment.setdefault(cohort, [])
        if content_id not in ids:
            ids.append(content_id)
        experiment["status"] = "running"
        save_versioned(path, ledger, RESEARCH_SCHEMA_VERSION)


def conclude_ready_experiments(path: Path, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Close balanced cohorts using only same-format, same-age-window fitness."""
    ledger = load_versioned(path, RESEARCH_SCHEMA_VERSION, {}, {"hypotheses": {}, "experiments": {}})
    by_id = {str(item.get("content_id")): item for item in catalog if isinstance(item, dict)}
    results: list[dict[str, Any]] = []
    experiments = ledger.get("experiments", {}) if isinstance(ledger, dict) else {}
    for experiment_id, experiment in list(experiments.items()):
        if not isinstance(experiment, dict) or experiment.get("status") in TERMINAL_STATUSES:
            continue
        target_window = experiment.get("target_window")
        kind = experiment.get("format")

        def cohort(
            name: str,
            experiment_record: dict[str, Any] = experiment,
            experiment_kind: Any = kind,
            window: Any = target_window,
        ) -> list[tuple[float, float]]:
            values: list[tuple[float, float]] = []
            for content_id in experiment_record.get(name, []):
                item = by_id.get(str(content_id))
                fitness = item.get("fitness") if isinstance(item, dict) else None
                if (
                    isinstance(item, dict)
                    and item.get("kind") == experiment_kind
                    and item.get("fitness_window") == window
                    and isinstance(fitness, dict)
                    and isinstance(fitness.get("score"), (int, float))
                ):
                    values.append((float(fitness["score"]), float(fitness.get("confidence") or 0.0)))
            return values

        control = cohort("control_content_ids")
        treatment = cohort("treatment_content_ids")
        if len(control) < 3 or len(treatment) < 3:
            continue
        raw_effect = (
            sum(value for value, _ in treatment) / len(treatment)
            - sum(value for value, _ in control) / len(control)
        )
        hypothesis = ledger.get("hypotheses", {}).get(experiment.get("hypothesis_id"), {})
        direction = hypothesis.get("expected_direction") if isinstance(hypothesis, dict) else "increase"
        effect = raw_effect if direction == "increase" else -raw_effect
        mean_confidence = sum(conf for _, conf in [*control, *treatment]) / (len(control) + len(treatment))
        balance = min(len(control), len(treatment)) / max(len(control), len(treatment))
        confidence = min(1.0, mean_confidence * balance * (1.0 - math.exp(-(len(control) + len(treatment)) / 12.0)))
        # Do not terminate a healthy experiment merely because its first few
        # observations are predictably low-confidence. At 30 samples we close
        # honestly even if sparse YouTube metrics still make it inconclusive.
        if confidence < 0.6 and len(control) + len(treatment) < 30:
            continue
        status = record_result(
            path,
            str(experiment_id),
            effect=round(effect, 6),
            samples=len(control) + len(treatment),
            confidence=round(confidence, 6),
        )
        results.append(
            {
                "experiment_id": experiment_id,
                "status": status,
                "raw_treatment_effect": round(raw_effect, 6),
                "direction_adjusted_effect": round(effect, 6),
                "samples": len(control) + len(treatment),
                "confidence": round(confidence, 6),
            }
        )
    return results
