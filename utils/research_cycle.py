"""Data-first autonomous research cycle for Liquid Wire's own channel."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from utils.ai_research_advisor import advise
from utils.atomic_state import atomic_write_json, load_versioned
from utils.experiment_engine import Hypothesis, record_hypothesis


def _get(item: dict[str, Any], dotted: str) -> float | None:
    value: Any = item
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _eligible(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in catalog
        if isinstance(item, dict)
        and _get(item, "fitness.score") is not None
        and _get(item, "fitness.confidence") is not None
        and item.get("fitness_window") in {"early", "1h", "6h", "24h", "72h", "mature"}
        and item.get("kind") in {"short", "long"}
    ]


def _family_statistics(items: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in items:
        family = str(item.get("genome", {}).get("family", "unknown"))
        cohort = f"{family}|{item.get('kind')}|{item.get('fitness_window')}"
        score = _get(item, "fitness.score")
        if score is not None:
            grouped[cohort].append(score)
    return {
        family: {
            "samples": len(scores),
            "mean_fitness": round(float(np.mean(scores)), 6),
            "std_fitness": round(float(np.std(scores)), 6),
        }
        for family, scores in sorted(grouped.items())
    }


def _correlations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dimensions = {
        "visual_dna.composition.screen_fill": "screen fill",
        "visual_dna.composition.symmetry": "symmetry",
        "visual_dna.composition.entropy": "visual entropy",
        "visual_dna.motion.optical_flow_mean": "apparent motion",
        "visual_dna.appearance.brightness": "brightness",
        "visual_dna.appearance.saturation": "saturation",
        "visual_dna.temporal.opening_activity": "opening activity",
    }
    results: list[dict[str, Any]] = []
    cohorts: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        cohorts[(str(item["kind"]), str(item["fitness_window"]))].append(item)
    for (kind, window), cohort_items in sorted(cohorts.items()):
        for path, label in dimensions.items():
            pairs: list[tuple[float, float]] = []
            for item in cohort_items:
                value = _get(item, path)
                score = _get(item, "fitness.score")
                if value is not None and score is not None:
                    pairs.append((value, score))
            if len(pairs) < 8:
                continue
            x, y = np.asarray(pairs, dtype=float).T
            if float(np.std(x)) < 1e-9 or float(np.std(y)) < 1e-9:
                continue
            correlation = float(np.corrcoef(x, y)[0, 1])
            if not np.isfinite(correlation):
                continue
            results.append(
                {
                    "variable": path,
                    "label": label,
                    "format": kind,
                    "window": window,
                    "samples": len(pairs),
                    "correlation": round(correlation, 6),
                    "strength": "strong"
                    if abs(correlation) >= 0.5
                    else "weak"
                    if abs(correlation) < 0.25
                    else "moderate",
                    "causal": False,
                }
            )
    return sorted(results, key=lambda row: abs(row["correlation"]), reverse=True)


def _proposed_hypotheses(correlations: list[dict[str, Any]]) -> list[Hypothesis]:
    proposals: list[Hypothesis] = []
    for signal in correlations:
        if signal["strength"] == "weak":
            continue
        direction = "increase" if signal["correlation"] > 0 else "decrease"
        proposals.append(
            Hypothesis(
                statement=(
                    f"Increasing {signal['label']} may {direction} {signal['format']} "
                    f"fitness in the {signal['window']} window"
                ),
                independent_variable=str(signal["variable"]),
                dependent_metric="fitness.score",
                expected_direction=direction,
                rationale=(
                    f"Observed non-causal correlation {signal['correlation']:.3f} across "
                    f"{signal['samples']} {signal['format']} creations observed in the same "
                    f"{signal['window']} window; controlled replication is required."
                ),
            )
        )
    return proposals[:3]


def run_research_cycle(data_root: Path) -> dict[str, Any]:
    catalog_path = data_root / "catalog_memory.json"
    catalog = load_versioned(catalog_path, 1, {}, []) if catalog_path.exists() else []
    items = _eligible(catalog if isinstance(catalog, list) else [])
    correlations = _correlations(items)
    hypotheses = _proposed_hypotheses(correlations)
    ledger_path = data_root / "research_ledger.json"
    for hypothesis in hypotheses:
        record_hypothesis(ledger_path, hypothesis)
    generated_at = datetime.now(UTC).isoformat()
    report = {
        "schema_version": 1,
        "generated_at": generated_at,
        "eligible_creations": len(items),
        "data_status": "sufficient_for_hypotheses" if correlations else "insufficient_data",
        "family_statistics": _family_statistics(items),
        "correlations": correlations,
        "proposed_hypothesis_ids": [hypothesis.hypothesis_id for hypothesis in hypotheses],
        "limitations": [
            "Observational correlations are not causal evidence.",
            "Fitness comparisons are valid only within stored age windows and format-specific models.",
            "Missing YouTube metrics reduce confidence and are not imputed.",
        ],
    }
    report["ai_advisor"] = advise(data_root, report)
    data_root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(data_root / "research_report.json", report)
    lines = [
        "# Liquid Wire research report",
        "",
        f"Generated: {generated_at}",
        f"Eligible creations: {len(items)}",
        f"Status: {report['data_status']}",
        "",
        "## Observations",
        "",
    ]
    lines.extend(
        f"- {row['format']}/{row['window']} {row['label']}: r={row['correlation']:.3f}, "
        f"n={row['samples']} ({row['strength']}; non-causal)"
        for row in correlations
    )
    if not correlations:
        lines.append("- Insufficient comparable observations; no hypothesis was manufactured.")
    (data_root / "research_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
