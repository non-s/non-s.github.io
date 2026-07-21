from pathlib import Path

import yaml

from scripts.check_workflow_contracts import check_workflow_contracts

ROOT = Path(__file__).resolve().parent.parent


def test_all_workflows_follow_safety_contracts():
    assert check_workflow_contracts(ROOT) == []


def test_workflows_parse_and_include_pipeline_steps():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))

    youtube_workflow = (ROOT / ".github/workflows/youtube-bot.yml").read_text(encoding="utf-8")
    assert "quota_preflight.py youtube-bot --json --check-only" in youtube_workflow
    assert "Sincronizar main remoto antes da decisao" in youtube_workflow
    assert "git checkout -B main origin/main" in youtube_workflow
    assert "scripts/sync_lofi_broll.py" in youtube_workflow
    assert "scripts/sync_jamendo_music.py" in youtube_workflow
    assert "generate_lofi_short.py" in youtube_workflow
    assert "PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}" in youtube_workflow
    assert "YouTube automation state -" in youtube_workflow
    assert "merge_jsonl_state.py" in youtube_workflow
    assert "jsonl_merge_paths" in youtube_workflow
    assert yaml.safe_load(youtube_workflow)["concurrency"]["group"] == "youtube-publisher"
    assert "_data/analytics/api_quota_ledger.jsonl" in youtube_workflow
    assert "if: always() && env.PUBLISH_QUOTA_BLOCKED != '1'" in youtube_workflow
    assert "Salvar marcadores no git" in youtube_workflow
    assert 'cron: "0 * * * *"' in youtube_workflow
    assert 'cron: "10 * * * *"' in youtube_workflow
    assert 'cron: "20 * * * *"' in youtube_workflow
    assert 'cron: "30 * * * *"' in youtube_workflow
    assert 'cron: "40 * * * *"' in youtube_workflow
    assert 'cron: "50 * * * *"' in youtube_workflow

    watchdog_workflow = (ROOT / ".github/workflows/youtube-watchdog.yml").read_text(encoding="utf-8")
    assert 'cron: "7,17,27,37,47,57 * * * *"' in watchdog_workflow
    assert 'GRACE_MINUTES: "12"' in watchdog_workflow
    assert 'PUBLISH_SLOT_WINDOW_MINUTES: "10"' in watchdog_workflow
    assert "python scripts/youtube_slot_dispatch.py watchdog" in watchdog_workflow

    heartbeat_workflow = (ROOT / ".github/workflows/youtube-hourly-heartbeat.yml").read_text(encoding="utf-8")
    assert 'cron: "13 * * * *"' in heartbeat_workflow
    assert 'TARGET_WORKFLOW: "youtube-bot.yml"' in heartbeat_workflow
    assert "PUBLISH_HEARTBEAT_RECENT_RUN_TOLERANCE_MINUTES || '20'" in heartbeat_workflow
    assert 'PUBLISH_SLOT_WINDOW_MINUTES: "60"' in heartbeat_workflow
    assert "heartbeat recovery for slot" in heartbeat_workflow
    assert "python scripts/youtube_slot_dispatch.py heartbeat" in heartbeat_workflow

    dashboard_workflow = (ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8")
    assert "for path in index.html _data/analytics/latest.json" in dashboard_workflow
    assert "Analytics persistence skipped because live state changed during dashboard build" in dashboard_workflow
    assert "Analytics persistence skipped after repeated non-fast-forward pushes" in dashboard_workflow
    assert "run_intelligence_suite" not in dashboard_workflow

    alert_workflow = (ROOT / ".github/workflows/ops-alert.yml").read_text(encoding="utf-8")
    parsed_alert = yaml.safe_load(alert_workflow)
    assert parsed_alert["permissions"]["issues"] == "write"
    assert "YouTube Bot - Shorts only" in alert_workflow
    assert "YouTube hourly heartbeat" in alert_workflow
    assert "YouTube publishing watchdog" in alert_workflow
    assert "Production quality gate" in alert_workflow
    assert "Build + deploy dashboard" in alert_workflow
    assert "CodeQL" in alert_workflow
    assert "Security, SBOM and license audit" in alert_workflow
    assert "Production smoke" in alert_workflow
    assert "Refresh Pexels queue" not in alert_workflow
    assert "TTS fallback health" not in alert_workflow
    assert "OPS_ALERTS_ENABLED" in alert_workflow
    assert "gh issue create" in alert_workflow
    assert "gh issue comment" in alert_workflow


def test_youtube_publisher_syncs_latest_main_before_publish_decision():
    workflow = yaml.safe_load((ROOT / ".github/workflows/youtube-bot.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["generate-and-upload"]["steps"]
    names = [step.get("name") for step in steps]

    sync_index = names.index("Sincronizar main remoto antes da decisao")
    assert sync_index < names.index("Quota preflight")
    assert sync_index < names.index("Sincronizar bibliotecas de b-roll e musica lofi")
    assert sync_index < names.index("Gerar Short lofi")
    assert sync_index < names.index("Upload Shorts para YouTube")

    sync_step = steps[sync_index]
    assert "git fetch origin main" in sync_step["run"]
    assert "git checkout -B main origin/main" in sync_step["run"]


def test_dashboard_refreshes_manual_analytics_imports():
    workflow = yaml.safe_load((ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["build"]["steps"]
    names = [step.get("name") for step in steps]

    assert "Refresh manual analytics imports" in names
    assert "Build dashboard HTML" in names
    build_index = names.index("Build dashboard HTML")
    assert names.index("Refresh manual analytics imports") < build_index

    build_step = steps[build_index]
    assert build_step["run"].strip() == "python scripts/build_dashboard.py"


def test_expensive_workflows_have_realistic_timeouts():
    dashboard = yaml.safe_load((ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8"))
    quality_gate = yaml.safe_load((ROOT / ".github/workflows/quality-gate.yml").read_text(encoding="utf-8"))
    heartbeat = yaml.safe_load((ROOT / ".github/workflows/youtube-hourly-heartbeat.yml").read_text(encoding="utf-8"))

    assert dashboard["jobs"]["build"]["timeout-minutes"] >= 20
    assert quality_gate["jobs"]["validate"]["timeout-minutes"] >= 35
    assert heartbeat["jobs"]["dispatch-hourly"]["timeout-minutes"] <= 8
