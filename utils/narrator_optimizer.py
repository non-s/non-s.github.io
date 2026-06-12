"""Narrator performance helpers."""

from __future__ import annotations

from collections import defaultdict


def narrator_report(items: list[dict]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        voice = str(item.get("narrator_voice") or (item.get("experiments") or {}).get("narrator_voice") or "unknown")
        groups[voice].append(item)
    rows = []
    for voice, sample in groups.items():
        growth = [float(i.get("growth_score", i.get("score", 0)) or 0) for i in sample]
        retention = [float(i.get("view_pct", i.get("average_view_percentage", 0)) or 0) for i in sample]
        rows.append(
            {
                "voice": voice,
                "n": len(sample),
                "mean_growth": round(sum(growth) / len(growth), 3) if growth else 0,
                "mean_retention": round(sum(retention) / len(retention), 3) if retention else 0,
            }
        )
    rows.sort(key=lambda item: (item["mean_growth"], item["mean_retention"], item["n"]), reverse=True)
    winner = rows[0]["voice"] if rows and rows[0]["voice"] != "unknown" and rows[0]["n"] >= 2 else ""
    return {
        "winner": winner,
        "voices": rows,
        "rule": "Prefer the winner when sample size is meaningful; keep exploration until then.",
    }


def category_voice_hint(category: str, report: dict | None = None) -> str:
    report = report or {}
    winner = str(report.get("winner") or "")
    if winner:
        return winner
    defaults = {
        "ocean": "aria",
        "arctic": "aria",
        "birds": "jenny",
        "primates": "guy",
        "dogs": "jenny",
        "cats": "aria",
    }
    return defaults.get(str(category or "").lower(), "aria")
