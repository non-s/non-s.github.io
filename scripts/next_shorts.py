#!/usr/bin/env python3
"""List the strongest next Shorts without rendering."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.publish_score import score_story
from utils.editorial_mix_optimizer import build_mix_plan, classify_lane, mix_adjustment
from utils.agency_gate import filter_candidates
from utils.editorial_guard import editorial_issues
from utils.publish_priority import autonomy_priority, publish_priority_key, queue_score
from utils.queue_pruner import prune_queue

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/next_shorts.json")

BODY_CUE_TERMS = (
    "alarm call",
    "body cue",
    "body posture",
    "ear position",
    "eye contact",
    "face shape",
    "feeding cue",
    "fin movement",
    "first movement",
    "flipper movement",
    "hand movement",
    "head movement",
    "tail position",
    "wing movement",
    "wing position",
    "beak movement",
    "ear",
    "ears",
    "eye",
    "eyes",
    "face",
    "faces",
    "feet",
    "fin",
    "fins",
    "flipper",
    "flippers",
    "hand",
    "hands",
    "head",
    "hoof",
    "hooves",
    "leg",
    "legs",
    "nose",
    "paw",
    "paws",
    "tail",
    "wing",
    "wings",
)


def _console_safe(text: str) -> str:
    return text.encode("ascii", errors="replace").decode("ascii")


def title_shape(title: str) -> str:
    """Collapse animal/body-part swaps into a comparable title template."""
    text = str(title or "").lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    text = re.sub(r"^[a-z0-9-]+s?\b", "{subject}", text, count=1)
    for term in sorted(BODY_CUE_TERMS, key=len, reverse=True):
        pattern = r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
        text = re.sub(pattern, "{cue}", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bthe\s+\{cue\}", "{cue}", text)
    return text


def _title_subject(title: str) -> str:
    match = re.match(r"\s*([A-Za-z][A-Za-z'-]*)", str(title or ""))
    return match.group(1) if match else "Animals"


def _title_cue(title: str) -> str:
    text = re.sub(r"\s+", " ", str(title or "").lower()).strip()
    patterns = (
        r"\bthrough\s+(.+)$",
        r"\bwith\s+(.+)$",
        r"\brely\s+on\s+(.+?)\s+to\b",
        r"\brely\s+on\s+(.+?)\s+for\b",
        r"\bfollow\s+the\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            cue = match.group(1).strip(" .")
            return re.sub(r"^(the|a|an)\s+", "", cue)
    return "first cue"


def _cue_moment(cue: str) -> str:
    cue = str(cue or "").lower().strip()
    return {
        "ear position": "their ears shift",
        "ear movement": "their ears move",
        "ear": "their ears shift",
        "ears": "their ears shift",
        "head movement": "their heads move",
        "head": "their heads move",
        "fin movement": "their fins shift",
        "fin": "their fins shift",
        "fins": "their fins shift",
        "hand movement": "their hands move",
        "hand": "their hands move",
        "hands": "their hands move",
        "tail position": "their tails lift",
        "tail": "their tails lift",
        "wing movement": "their wings move",
        "wing position": "their wings shift",
        "wing": "their wings move",
        "wings": "their wings move",
        "paw": "their paws move",
        "paws": "their paws move",
        "beak movement": "their beaks move",
        "beak": "their beaks move",
        "flipper movement": "their flippers shift",
        "flipper": "their flippers shift",
        "flippers": "their flippers shift",
        "first movement": "the first move appears",
        "feeding cue": "the feeding cue appears",
        "call": "one call lands",
    }.get(cue, f"the {cue} changes")


def _cue_signal(cue: str) -> str:
    cue = str(cue or "").lower().strip()
    return {
        "ear position": "ear shift",
        "ear movement": "ear shift",
        "ear": "ear shift",
        "ears": "ear shift",
        "head movement": "head movement",
        "head": "head movement",
        "fin movement": "fin cue",
        "fin": "fin cue",
        "fins": "fin cue",
        "hand movement": "hand cue",
        "hand": "hand cue",
        "hands": "hand cue",
        "tail position": "tail lift",
        "tail": "tail lift",
        "wing movement": "wing beat",
        "wing position": "wing angle",
        "wing": "wing beat",
        "wings": "wing beat",
        "paws": "paw cue",
        "paw": "paw cue",
        "beak movement": "beak cue",
        "beak": "beak cue",
        "flipper movement": "flipper cue",
        "flipper": "flipper cue",
        "flippers": "flipper cue",
        "first movement": "first move",
        "feeding cue": "feeding cue",
        "call": "call",
    }.get(cue, cue or "first cue")


def title_rewrite_suggestions(title: str) -> list[str]:
    subject = _title_subject(title)
    lower_subject = subject.lower()
    cue = _title_cue(title)
    cue_moment = _cue_moment(cue)
    cue_signal = _cue_signal(cue)
    candidates = [
        f"{subject} react differently when {cue_moment}",
        f"{subject} read the moment from one {cue_signal}",
        f"The {cue_signal} that changes how {lower_subject} react",
    ]
    suggestions: list[str] = []
    current_shape = title_shape(title)
    for candidate in candidates:
        clean = re.sub(r"\s+", " ", candidate).strip()
        if not clean or clean.lower() == str(title or "").strip().lower():
            continue
        if title_shape(clean) == current_shape:
            continue
        if editorial_issues({"title": clean, "seo_title": clean}, include_script=False):
            continue
        if clean not in suggestions:
            suggestions.append(clean[:82])
    return suggestions[:3]


def build_title_shape_mix(rows: list[dict], windows: tuple[int, ...] = (10, 30)) -> dict:
    summaries = []
    warnings = []
    rewrite_candidates_by_id: dict[str, dict] = {}
    for size in windows:
        window = [(rank, row) for rank, row in enumerate(rows[:size], start=1) if row.get("title")]
        if not window:
            continue
        row_shapes = [
            (rank, row, shape)
            for rank, row in window
            if (shape := title_shape(str(row.get("title") or "")))
        ]
        counts = Counter(shape for _rank, _row, shape in row_shapes)
        if not counts:
            continue
        top_shape, top_count = counts.most_common(1)[0]
        share = round(top_count / max(1, len(row_shapes)), 3)
        summary = {
            "window": size,
            "items": len(row_shapes),
            "dominant_shape": top_shape,
            "dominant_count": top_count,
            "dominant_share": share,
            "top_shapes": [
                {"shape": shape, "count": count, "share": round(count / max(1, len(row_shapes)), 3)}
                for shape, count in counts.most_common(5)
            ],
        }
        summaries.append(summary)
        threshold = 0.4 if size <= 10 else 0.27
        min_count = 4 if size <= 10 else 8
        if top_count >= min_count and share >= threshold:
            allowed_count = min_count - 1
            warnings.append(
                {
                    "window": size,
                    "shape": top_shape,
                    "count": top_count,
                    "share": share,
                    "action": "alternate title promises before publishing this block",
                }
            )
            repeated = [(rank, row) for rank, row, shape in row_shapes if shape == top_shape]
            for rank, row in repeated[allowed_count:]:
                key = str(row.get("id") or row.get("title") or rank)
                rewrite_candidates_by_id.setdefault(
                    key,
                    {
                        "rank": rank,
                        "id": row.get("id", ""),
                        "title": row.get("title", ""),
                        "shape": top_shape,
                        "suggested_titles": title_rewrite_suggestions(str(row.get("title") or "")),
                        "window": size,
                        "action": "rewrite title with a different promise shape before publishing this cluster",
                    },
                )
    return {
        "status": "watch" if warnings else "healthy",
        "warnings": warnings,
        "rewrite_candidates": sorted(
            rewrite_candidates_by_id.values(),
            key=lambda item: (int(item.get("rank", 0) or 0), int(item.get("window", 0) or 0)),
        )[:10],
        "windows": summaries,
    }


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    data, _rejected, prune_summary = prune_queue(data)
    rows = []
    pending_stories = [story for story in data.get("stories") or [] if not story.get("consumed")]
    mix_plan = build_mix_plan(pending_stories)
    candidates, _held = filter_candidates([story for story in data.get("stories") or [] if not story.get("consumed")])
    for story in candidates:
        queue_prune = story.get("queue_prune") or {}
        queue_state = queue_prune.get("state")
        if queue_state and queue_state != "publish_ready":
            continue
        score = score_story(story)
        if score.get("approved") is True and score.get("state") == "publish_ready":
            lane_adjustment = mix_adjustment(story)
            score = {**score, "score": round(min(100.0, float(score.get("score") or 0) + lane_adjustment), 1)}
            rows.append(
                {
                    "id": story.get("id", ""),
                    "title": story.get("seo_title") or story.get("title") or "",
                    "category": story.get("category", ""),
                    "autonomy_priority": autonomy_priority(story, queue_score(story)),
                    "queue_score": queue_score(story),
                    "template_cluster": queue_prune.get("template_cluster", ""),
                    "mechanism_cluster": queue_prune.get("mechanism_cluster", ""),
                    "objective_reasons": queue_prune.get("objective_reasons") or [],
                    "lane": classify_lane(story),
                    "mix_adjustment": lane_adjustment,
                    "score": score,
                }
            )
    rows = sorted(
        rows,
        key=lambda row: publish_priority_key(
            {"autonomy": {"priority": row.get("autonomy_priority", 0)}, "queue_prune": {"score": row.get("queue_score", 0)}},
            row.get("score") or {},
        ),
        reverse=True,
    )[:30]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "items": rows,
                "editorial_mix": mix_plan,
                "title_shape_mix": build_title_shape_mix(rows),
                "selection_rule": "autonomy_priority first, queue_score and publish_score as tie-breakers",
                "prune_summary": prune_summary,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for row in rows[:10]:
        print(
            _console_safe(
                f"p{row['autonomy_priority']:5.1f} q{row['queue_score']:5.1f} "
                f"s{row['score']['score']:5.1f} [{row['category']}] {row['title']}"
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
