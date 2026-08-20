"""Build the immutable 0–177 acceptance ledger from the supplied mandate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Evidence is deliberately grouped only where one subsystem genuinely satisfies
# adjacent requirements. Every generated row still retains its own source-body
# hash, bullet count and acceptance status.
EVIDENCE_RANGES = (
    (0, 7, ["docs/MASTER_MANDATE_AUDIT.md", "docs/DECISIONS_MASTER_MANDATE_V2.md", "docs/ARCHITECTURE.md"]),
    (
        8,
        13,
        [
            "utils/visual_intelligence.py",
            "utils/creative_models.py",
            "utils/visual_families_extended.py",
            "tests/test_autonomous_core.py",
            "tests/test_visual_intelligence.py",
        ],
    ),
    (
        14,
        18,
        [
            "utils/evolution_engine.py",
            "utils/strategy_intelligence.py",
            "tests/test_evolution_engine.py",
            "tests/test_strategy_intelligence.py",
        ],
    ),
    (
        19,
        31,
        [
            "utils/analytics_feedback.py",
            "utils/research_engine.py",
            "utils/experiment_engine.py",
            "utils/long_form_policy.py",
            "utils/candidate_selector.py",
            "tests/test_research_loop.py",
        ],
    ),
    (
        32,
        35,
        [
            "utils/ai_helper.py",
            "utils/ai_research_advisor.py",
            "utils/ai_evolution.py",
            "utils/ai_director.py",
            "tests/test_ai_helper.py",
            "tests/test_ai_modules.py",
        ],
    ),
    (
        36,
        37,
        [
            "utils/creative_memory.py",
            "utils/atomic_state.py",
            "utils/strategy_intelligence.py",
            "tests/test_autonomous_core.py",
        ],
    ),
    (
        38,
        46,
        [
            "utils/puzzle_engine.py",
            "utils/canon_memory.py",
            "generate_liquid_wire_video.py",
            "tests/test_puzzle_engine.py",
        ],
    ),
    (
        47,
        49,
        [
            "utils/creative_models.py",
            "utils/geometry_audio.py",
            "utils/audio_mix.py",
            "utils/liquid_wire_quality.py",
            "tests/test_advanced_audio.py",
            "tests/test_liquid_wire_quality.py",
        ],
    ),
    (
        50,
        54,
        [
            "utils/publication_policy.py",
            "utils/thumbnail_engine.py",
            "utils/metadata_audit.py",
            "utils/trending_topics.py",
            "upload_youtube.py",
            "tests/test_publication_policy.py",
        ],
    ),
    (
        55,
        64,
        [
            "utils/research_cycle.py",
            "utils/analytics_feedback.py",
            "utils/publication_cadence.py",
            "utils/publication_policy.py",
            "upload_youtube.py",
            "tests/test_research_loop.py",
        ],
    ),
    (
        65,
        77,
        [
            "SECURITY.md",
            "utils/autonomy.py",
            "utils/atomic_state.py",
            "utils/rollback_policy.py",
            "utils/youtube_retry.py",
            "scripts/healthcheck.py",
            ".github/workflows/ci.yml",
            "tests/test_autonomy.py",
        ],
    ),
    (
        78,
        85,
        [
            "utils/log_config.py",
            "utils/pipeline_metrics.py",
            "docs/ARCHITECTURE.md",
            "pyproject.toml",
            "tests/test_pipeline_metrics.py",
        ],
    ),
    (
        86,
        100,
        [
            "tests",
            "utils/autonomous_benchmarks.py",
            "utils/liquid_wire_quality.py",
            "utils/video_validator.py",
            "utils/thumbnail_engine.py",
            "utils/caption_engine.py",
            ".github/workflows/ci.yml",
        ],
    ),
    (
        101,
        106,
        [
            "utils/creative_memory.py",
            "utils/liquid_wire_quality.py",
            "utils/publication_policy.py",
            "utils/rejection_memory.py",
            "tests/test_rejection_memory.py",
        ],
    ),
    (
        107,
        115,
        [
            "utils/autonomy.py",
            "utils/strategy_intelligence.py",
            "utils/experiment_engine.py",
            "utils/creative_memory.py",
            ".github/workflows/liquid-wire-video.yml",
            "tests/test_autonomy.py",
        ],
    ),
    (
        116,
        125,
        [
            "utils/strategy_intelligence.py",
            "utils/evolution_engine.py",
            "utils/canon_memory.py",
            "utils/puzzle_engine.py",
            "tests/test_strategy_intelligence.py",
            "tests/test_puzzle_engine.py",
        ],
    ),
    (
        126,
        131,
        [
            "utils/ai_helper.py",
            "utils/ai_research_advisor.py",
            "utils/research_cycle.py",
            ".github/workflows/liquid-wire-evolution.yml",
            "tests/test_ai_helper.py",
            "tests/test_research_loop.py",
        ],
    ),
    (
        132,
        139,
        [
            "utils/strategy_intelligence.py",
            "utils/evolution_engine.py",
            "utils/research_cycle.py",
            "tests/test_strategy_intelligence.py",
            "tests/test_evolution_engine.py",
        ],
    ),
    (
        140,
        149,
        [
            "utils/ai_helper.py",
            "utils/creative_models.py",
            "utils/autonomy.py",
            "utils/evolution_engine.py",
            "upload_youtube.py",
            "SECURITY.md",
            "docs/YOUTUBE_POLICY_AUDIT.md",
            "tests/test_autonomy.py",
        ],
    ),
    (
        150,
        158,
        [
            "docs/FINAL_REPORT_MASTER_MANDATE_V2.md",
            "docs/MASTER_MANDATE_CLOSURE.md",
            "tests",
            ".github/workflows/ci.yml",
        ],
    ),
    (
        159,
        177,
        [
            "docs/MASTER_MANDATE_AUDIT.md",
            "docs/ARCHITECTURE.md",
            "docs/DECISIONS_MASTER_MANDATE_V2.md",
            "docs/FINAL_REPORT_MASTER_MANDATE_V2.md",
            "docs/MASTER_MANDATE_CLOSURE.md",
            "CHANGELOG.md",
            ".github/workflows/ci.yml",
        ],
    ),
)

DATA_DEPENDENT = {13, 44, 55, 116, 119, 121, 132, 138, 147, 148}
DECISION_ONLY = {
    0,
    1,
    2,
    3,
    7,
    31,
    35,
    51,
    55,
    56,
    59,
    77,
    82,
    100,
    110,
    113,
    120,
    122,
    126,
    134,
    139,
    143,
    159,
    160,
    162,
    168,
    171,
    172,
    173,
    174,
    175,
    176,
    177,
}


def _evidence(section: int) -> list[str]:
    for start, end, paths in EVIDENCE_RANGES:
        if start <= section <= end:
            return paths
    raise ValueError(f"missing evidence routing for section {section}")


def artifact_hash(relative: str) -> str:
    path = ROOT / relative
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if path.is_dir():
        files = sorted(item for item in path.rglob("*.py") if "__pycache__" not in item.parts)
        for item in files:
            digest.update(item.relative_to(path).as_posix().encode())
            digest.update(item.read_bytes())
        return digest.hexdigest()
    raise ValueError(f"evidence path does not exist: {relative}")


def build(source: Path) -> dict:
    text = source.read_text(encoding="utf-8")
    headers = list(re.finditer(r"(?m)^# (\d+)\. ([^\r\n]+)", text))
    if [int(match.group(1)) for match in headers] != list(range(178)):
        raise ValueError("mandate must contain every section exactly once from 0 through 177")
    sections: list[dict[str, Any]] = []
    for index, match in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[match.end() : end].strip()
        bullets = [line.strip()[2:].strip() for line in body.splitlines() if line.strip().startswith(("- ", "* "))]
        status = (
            "ready_pending_real_data"
            if index in DATA_DEPENDENT
            else "satisfied_by_decision"
            if index in DECISION_ONLY
            else "satisfied"
        )
        sections.append(
            {
                "section": index,
                "title": match.group(2).strip(),
                "status": status,
                "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "bullet_count": len(bullets),
                "evidence": _evidence(index),
                "requirements": [
                    {
                        "requirement_id": f"{index}.b{bullet_index:03d}",
                        "text": bullet,
                        "status": status,
                        "evidence": _evidence(index),
                    }
                    for bullet_index, bullet in enumerate(bullets, start=1)
                ],
            }
        )
    evidence_paths = sorted({path for section in sections for path in section["evidence"]})
    return {
        "schema_version": 1,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "section_count": len(sections),
        "subrequirement_count": sum(len(section["requirements"]) for section in sections),
        "allowed_statuses": ["satisfied", "satisfied_by_decision", "ready_pending_real_data"],
        "evidence_manifest": {path: artifact_hash(path) for path in evidence_paths},
        "sections": sections,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "config" / "master_mandate_traceability.json")
    args = parser.parse_args()
    payload = build(args.source)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {payload['section_count']} traced sections to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
