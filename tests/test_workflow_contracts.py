from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_workflows_parse_and_include_growth_steps():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))

    assert "quota_preflight.py youtube-bot" in (ROOT / ".github/workflows/youtube-bot.yml").read_text(encoding="utf-8")
    assert "skip_quota_guard" in (ROOT / ".github/workflows/youtube-bot.yml").read_text(encoding="utf-8")
    assert "apply_topic_freshness.py" in (ROOT / ".github/workflows/fetch-content.yml").read_text(encoding="utf-8")
    assert "compact_analytics.py" in (ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8")
    assert "check_repo_contracts.py" in (ROOT / ".github/workflows/quality-gate.yml").read_text(encoding="utf-8")
