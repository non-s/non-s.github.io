#!/usr/bin/env python3
"""Prepare title/hook/thumbnail repairs for already-published Shorts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial_guard import editorial_issues

VIDEOS_DIR = ROOT / "_videos"
DATA_OUT = ROOT / "_data" / "published_packaging_repair.json"
DOC_OUT = ROOT / "docs" / "published_packaging_repair_2026-06-12.md"

OVERRIDES: dict[str, dict[str, str]] = {
    "U3muBbnmMbo": {
        "title": "Chickens remember up to 100 faces",
        "thumbnail_text": "FACE MEMORY",
        "hook": "Watch the face memory payoff first; chickens remember friends and bullies.",
        "rationale": "Aligns the title and thumbnail with the actual published description about chicken face memory.",
    },
    "hrvLkfiyQLc": {
        "title": "Butterflies unfurl straw-like tongues for nectar",
        "thumbnail_text": "NECTAR STRAW",
        "hook": "Watch the straw-like tongue first; it lets the butterfly drink without landing hard.",
        "rationale": "Fixes the truncated title and matches the published description about nectar-feeding mouthparts.",
    },
    "BTjx49FRn8U": {
        "title": "Wolves give away intent with one tail lift",
        "thumbnail_text": "TAIL LIFT",
        "hook": "Watch the tail lift first; it changes how the pack reads the moment.",
        "rationale": "Replaces a generic 'tail to signal' title with an observable payoff.",
    },
    "f4PDHoApChg": {
        "title": "Sheep recognize the herd by forehead bumps",
        "thumbnail_text": "HERD ID",
        "hook": "Watch the forehead first; those bumps work like a herd ID.",
        "rationale": "Removes the stitched 'Horses Sheep' error and follows the actual forehead-bump description.",
    },
    "-hlnfDdgbWE": {
        "title": "Lions turn evening walks into patrols",
        "thumbnail_text": "PRIDE PATROL",
        "hook": "Watch the pride walk first; the stroll is really a patrol.",
        "rationale": "Repairs the 'use their ears to use' loop while matching the published patrol description.",
    },
    "m0fPWQYUiIw": {
        "title": "Snakes follow motion with their whole body",
        "thumbnail_text": "BODY MOVE",
        "hook": "Watch the body line first; the movement points to the next turn.",
        "rationale": "Fixes singular grammar and removes the robotic body-part template.",
    },
    "a1JckQGKu3c": {
        "title": "Goats keep balance with tiny foot grips",
        "thumbnail_text": "FOOT GRIP",
        "hook": "Watch the feet first; the tiny grip keeps the climb steady.",
        "rationale": "Replaces 'because of this feet' with natural grammar and a visible cue.",
    },
    "U3ejh-CMePk": {
        "title": "Storks clean their eyes with a built-in shade",
        "thumbnail_text": "EYE SHADE",
        "hook": "Watch the eye first; the moving lid works like a tiny window shade.",
        "rationale": "Repairs the awkward title and matches the actual eyelid-cleaning description.",
    },
    "-sCe5JvKNXg": {
        "title": "Orangutans nap high in trees to stay safe",
        "thumbnail_text": "TREE NAP",
        "hook": "Watch the tree nap first; comfort is part of the survival trick.",
        "rationale": "Removes the 'use their body to use' loop and follows the published nap/survival description.",
    },
    "XECqyy47VFg": {
        "title": "Sharks in aquariums save energy with slow loops",
        "thumbnail_text": "SLOW LOOPS",
        "hook": "Watch the slow loop first; the tank changes how the shark saves energy.",
        "rationale": "Keeps the aquarium context but drops the vague 'sneaky trick' wording.",
    },
    "iP5gVRObQuo": {
        "title": "Monkeys turn their tails into alarm signals",
        "thumbnail_text": "TAIL ALARM",
        "hook": "Watch the tail first; it can warn the group before the move.",
        "rationale": "Repairs the generic body-part-to-signal pattern and matches the published alarm-system angle.",
    },
    "kQFZSUabpKs": {
        "title": "Ducks fake injury to pull danger away",
        "thumbnail_text": "FAKE INJURY",
        "hook": "Watch the fake injury first; it pulls danger away from the nest.",
        "rationale": "Turns a vague body trick into the known broken-wing display payoff.",
    },
    "KHNEgmGZgKg": {
        "title": "Cows remember faces longer than you think",
        "thumbnail_text": "FACE MEMORY",
        "hook": "Watch the face first; cows remember who they have seen before.",
        "rationale": "Removes generic 'another signal hiding in plain sight' language.",
    },
    "wRv-WePyaow": {
        "title": "Gray wolves roll in scent to confuse noses",
        "thumbnail_text": "SCENT TRICK",
        "hook": "Watch the scent roll first; it can scramble what other noses read.",
        "rationale": "Cleans the repeated-animal title while preserving the stronger idea.",
    },
    "3fmmBeCj73M": {
        "title": "White horses see blues and yellows best",
        "thumbnail_text": "HORSE COLOR",
        "hook": "Watch the contrast first; horses do not see color the way we do.",
        "rationale": "Removes the repeated category prefix and makes the payoff clearer.",
    },
    "RVQvVv_whYM": {
        "title": "Deer turn white tails into panic buttons",
        "thumbnail_text": "PANIC TAIL",
        "hook": "Watch the tail flash first; it warns the group in a blink.",
        "rationale": "Keeps a strong existing title but tightens it for scan speed.",
    },
    "7-ADzNJ9TH0": {
        "title": "Chickens warn each other with tiny head moves",
        "thumbnail_text": "HEAD TILT",
        "hook": "Watch the head first; the warning happens before the flock moves.",
        "rationale": "Replaces generic sequel copy with a specific visual promise.",
    },
    "bnDgHEHIWuo": {
        "title": "Lions nap all day for one survival reason",
        "thumbnail_text": "POWER NAP",
        "hook": "Watch the rest first; saving energy is part of the hunt.",
        "rationale": "Keeps the good premise while making the title more clickable.",
    },
    "_9korq6cLzk": {
        "title": "Black dog fur absorbs sunlight faster",
        "thumbnail_text": "BLACK FUR",
        "hook": "Watch the dark coat first; black fur absorbs more sunlight.",
        "rationale": "Repairs the repeated-dog wording and matches the published black-fur description.",
    },
    "JwXcPUwBmzM": {
        "title": "Those bird ear tufts are actually feathers",
        "thumbnail_text": "FAKE EARS",
        "hook": "Watch the ear tufts first; they are not ears at all.",
        "rationale": "Removes the stitched category prefix while keeping the clear myth payoff.",
    },
    "85VdygIXPBo": {
        "title": "Tigers stay silent before the ambush",
        "thumbnail_text": "SILENT HUNT",
        "hook": "Watch the silence first; roaring would ruin the ambush.",
        "rationale": "Fixes the truncated title and turns the premise into a sharper survival hook.",
    },
}


def _load_done_files() -> list[tuple[str, Path, dict[str, Any]]]:
    rows: list[tuple[str, Path, dict[str, Any]]] = []
    for path in VIDEOS_DIR.glob("*.done"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        video_id = str(data.get("video_id") or data.get("youtube_video_id") or "").strip()
        if video_id:
            rows.append((str(data.get("uploaded_at") or ""), path, data))
    return sorted(rows, reverse=True)


def _fallback_suggestion(data: dict[str, Any]) -> dict[str, str]:
    title = str(data.get("title") or "").strip()
    category = str(data.get("category") or "Nature").replace("_", " ").title()
    if title and not editorial_issues({"title": title}):
        repaired = title[:82]
    else:
        repaired = f"{category} reveal one visible cue"
    return {
        "title": repaired,
        "thumbnail_text": "WATCH THE CUE",
        "hook": f"Watch the first cue; the payoff is visible before the move.",
        "rationale": "Fallback repair for videos without a hand-authored override.",
    }


def build_repairs(limit: int | None = None) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    for _, path, data in _load_done_files()[: limit or 9999]:
        video_id = str(data.get("video_id") or data.get("youtube_video_id") or "").strip()
        suggestion = OVERRIDES.get(video_id) or _fallback_suggestion(data)
        old_title = str(data.get("title") or "").strip()
        new_title = suggestion["title"]
        issues = editorial_issues({"title": old_title, "hook": data.get("hook") or ""}, include_script=False)
        repairs.append(
            {
                "video_id": video_id,
                "uploaded_at": data.get("uploaded_at"),
                "done_file": path.relative_to(ROOT).as_posix(),
                "public_url": f"https://www.youtube.com/shorts/{video_id}",
                "studio_url": f"https://studio.youtube.com/video/{video_id}/edit",
                "old_title": old_title,
                "new_title": new_title,
                "thumbnail_text": suggestion["thumbnail_text"],
                "hook": suggestion["hook"],
                "priority": "high" if issues or old_title != new_title else "watch",
                "editorial_issues": issues,
                "rationale": suggestion["rationale"],
                "studio_actions": [
                    "Update title",
                    "Update description first line if available",
                    "Try custom thumbnail upload in Studio; if Shorts blocks it, keep change for future re-render",
                ],
            }
        )
    return repairs


def write_outputs(repairs: list[dict[str, Any]]) -> None:
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(repairs),
        "high_priority_count": sum(1 for item in repairs if item["priority"] == "high"),
        "repairs": repairs,
    }
    DATA_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Published Packaging Repair - 2026-06-12",
        "",
        "Goal: improve already-published Shorts with stronger titles, clearer hooks, and cleaner thumbnail promises.",
        "",
    ]
    for item in repairs:
        lines.extend(
            [
                f"## {item['video_id']} - {item['priority']}",
                f"- Studio: {item['studio_url']}",
                f"- Public: {item['public_url']}",
                f"- Old title: {item['old_title']}",
                f"- New title: {item['new_title']}",
                f"- Thumbnail/cover promise: {item['thumbnail_text']}",
                f"- Hook direction: {item['hook']}",
                f"- Why: {item['rationale']}",
                "",
            ]
        )
    DOC_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    repairs = build_repairs()
    write_outputs(repairs)
    print(json.dumps({"json": DATA_OUT.as_posix(), "doc": DOC_OUT.as_posix(), "count": len(repairs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
