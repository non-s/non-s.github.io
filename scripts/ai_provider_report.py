#!/usr/bin/env python3
"""Summarise AI provider health and routing order."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import provider_stats

OUT = ROOT / "_data" / "ai_provider_report.json"


def main() -> int:
    providers = []
    env_names = {
        "mistral": "MISTRAL_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    now = time.time()
    for name in provider_stats.DEFAULT_ORDER:
        rate = provider_stats.success_rate(name)
        until = provider_stats.cooldown_until(name, now=now)
        providers.append(
            {
                "provider": name,
                "configured": bool(os.environ.get(env_names[name], "").strip()),
                "success_rate": None if rate is None else round(rate, 3),
                "cooldown_seconds": max(0, int(until - now)) if until else 0,
            }
        )
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "default_chain": provider_stats.preferred_chain(),
        "json_chain": provider_stats.preferred_chain_for_task("json"),
        "rewrite_chain": provider_stats.preferred_chain_for_task("rewrite"),
        "longform_chain": provider_stats.preferred_chain_for_task("longform"),
        "providers": providers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ai provider report: " + ", ".join(payload["default_chain"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
