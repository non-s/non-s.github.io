"""Versioned scientific-method records with single-variable safeguards."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils.atomic_state import load_versioned, save_versioned
from utils.research_engine import hypothesis_status
from utils.state_lock import state_lock

RESEARCH_SCHEMA_VERSION = 1
VALID_STATUSES = {"planned", "running", "insufficient_data", "inconclusive", "supported", "contradicted"}


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
