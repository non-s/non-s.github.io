"""Data-first autonomous research cycle for Liquid Wire's own channel."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from utils.ai_research_advisor import advise
from utils.atomic_state import atomic_write_json, load_versioned
from utils.experiment_engine import (
    Hypothesis,
    conclude_ready_experiments,
    plan_experiment,
    record_hypothesis,
)
from utils.strategy_intelligence import (
    creative_map,
    experiment_meta_learning,
    lineage_graph,
    pareto_frontier,
    value_of_information,
)


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
    # Independent variables must be controls the renderer can intervene on.
    # Perceived output measurements remain useful outcomes, but cannot be
    # assigned as treatments and therefore must never be labelled causal inputs.
    dimensions = {
        "genome.motion.melt_rate": "melt rate",
        "genome.geometry.folds_theta": "theta folds",
        "genome.geometry.folds_phi": "phi folds",
        "genome.geometry.strand_count": "strand count",
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


def _experiment_priorities(
    hypotheses: list[Hypothesis], correlations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    signals = {str(signal["variable"]): signal for signal in correlations}
    priorities: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        signal = signals.get(hypothesis.independent_variable)
        if signal is None:
            continue
        correlation = float(signal["correlation"])
        priorities.append(
            {
                "hypothesis_id": hypothesis.hypothesis_id,
                "value_of_information": value_of_information(
                    uncertainty=1.0 - min(1.0, abs(correlation)),
                    novelty=1.0,
                    expected_performance=max(0.0, correlation),
                ),
            }
        )
    return sorted(priorities, key=lambda item: item["value_of_information"], reverse=True)


def _plain_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _operational_summary(data_root: Path, catalog: list[dict[str, Any]]) -> dict[str, int]:
    candidate_count = sum(
        int(item.get("candidate_selection", {}).get("budget", 0))
        for item in catalog
        if isinstance(item, dict) and isinstance(item.get("candidate_selection"), dict)
    )
    rejection_path = data_root / "rejection_memory.json"
    rejections = load_versioned(rejection_path, 1, {}, []) if rejection_path.exists() else []
    metrics = _plain_json(data_root / "pipeline_metrics.json", [])
    metric_rows = metrics if isinstance(metrics, list) else []
    renders = sum(
        1
        for row in metric_rows
        if isinstance(row, dict)
        if str(row.get("stage", "")).startswith("generate")
    )
    tags = _plain_json(data_root / "video_tags.json", {})
    return {
        "candidates_evaluated": candidate_count,
        "rejections_recorded": len(rejections) if isinstance(rejections, list) else 0,
        "render_runs": renders,
        "creations_cataloged": len(catalog),
        "videos_published_or_uploaded": len(tags) if isinstance(tags, dict) else 0,
    }


def run_research_cycle(data_root: Path) -> dict[str, Any]:
    catalog_path = data_root / "catalog_memory.json"
    catalog = load_versioned(catalog_path, 1, {}, []) if catalog_path.exists() else []
    items = _eligible(catalog if isinstance(catalog, list) else [])
    correlations = _correlations(items)
    hypotheses = _proposed_hypotheses(correlations)
    ledger_path = data_root / "research_ledger.json"
    for hypothesis in hypotheses:
        record_hypothesis(ledger_path, hypothesis)
    priorities = _experiment_priorities(hypotheses, correlations)
    hypothesis_by_id = {item.hypothesis_id: item for item in hypotheses}
    planned_experiment_id = None
    for priority in priorities:
        selected_hypothesis = hypothesis_by_id.get(str(priority["hypothesis_id"]))
        signal = next(
            (
                item
                for item in correlations
                if selected_hypothesis and item["variable"] == selected_hypothesis.independent_variable
            ),
            None,
        )
        if selected_hypothesis is None or signal is None:
            continue
        planned_experiment_id = plan_experiment(
            ledger_path,
            selected_hypothesis.hypothesis_id,
            independent_variable=selected_hypothesis.independent_variable,
            format=str(signal["format"]),
            target_window=str(signal["window"]),
        )
        if planned_experiment_id:
            break
    concluded_experiments = conclude_ready_experiments(
        ledger_path, catalog if isinstance(catalog, list) else []
    )
    ledger = load_versioned(ledger_path, 1, {}, {"hypotheses": {}, "experiments": {}})
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": generated_at,
        "eligible_creations": len(items),
        "data_status": "sufficient_for_hypotheses" if correlations else "insufficient_data",
        "family_statistics": _family_statistics(items),
        "correlations": correlations,
        "proposed_hypothesis_ids": [hypothesis.hypothesis_id for hypothesis in hypotheses],
        "experiment_priorities": priorities,
        "planned_experiment_id": planned_experiment_id,
        "concluded_experiments": concluded_experiments,
        "pareto_content_ids": pareto_frontier(items),
        "creative_map": creative_map(items),
        "lineage_graph": lineage_graph(items),
        "meta_learning": experiment_meta_learning(ledger if isinstance(ledger, dict) else {}),
        "operational_summary": _operational_summary(data_root, catalog if isinstance(catalog, list) else []),
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
    summary: dict[str, int] = report["operational_summary"]
    lines.extend(
        [
            "",
            "## Retained operational evidence",
            "",
            f"- Candidates evaluated: {summary['candidates_evaluated']}",
            f"- Rejections recorded: {summary['rejections_recorded']}",
            f"- Render runs: {summary['render_runs']}",
            f"- Creations cataloged: {summary['creations_cataloged']}",
            f"- Videos uploaded/published: {summary['videos_published_or_uploaded']}",
            "",
            "## Next learning action",
            "",
        ]
    )
    if report["experiment_priorities"]:
        best = report["experiment_priorities"][0]
        lines.append(
            f"- Highest value-of-information hypothesis: {best['hypothesis_id']} "
            f"(score={best['value_of_information']:.3f}); controlled replication required."
        )
    else:
        lines.append("- No experiment proposed until a same-format, same-window cohort is sufficient.")
    (data_root / "research_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
