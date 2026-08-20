"""Evidence-backed 10/10 scorecard; missing proof can never be rounded up."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def evaluate_scorecard(definition: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    spec = json.loads(definition.read_text(encoding="utf-8"))
    areas: dict[str, Any] = {}
    for name, block in spec["areas"].items():
        criteria = list(block["criteria"])
        results = {criterion: bool(evidence.get(name, {}).get(criterion, False)) for criterion in criteria}
        passed = sum(results.values())
        score = round(10.0 * passed / max(1, len(criteria)), 2)
        areas[name] = {"score": score, "complete": passed == len(criteria), "criteria": results}
    complete = all(area["complete"] for area in areas.values())
    return {"target": 10.0, "complete": complete, "areas": areas}
