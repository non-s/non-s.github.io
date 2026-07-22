from pathlib import Path

import yaml

from scripts.check_workflow_contracts import _is_valid_action_ref, check_workflow_contracts

ROOT = Path(__file__).resolve().parent.parent


def test_all_workflows_follow_safety_contracts():
    assert check_workflow_contracts(ROOT) == []


def test_action_ref_validation():
    # Official actions require a semver tag.
    assert _is_valid_action_ref("actions/checkout@v4")
    assert _is_valid_action_ref("actions/checkout@v4.0.0")
    assert _is_valid_action_ref("actions/checkout@v7.0.0")
    assert _is_valid_action_ref("github/codeql-action/init@v4")
    # SHA pinning is always allowed.
    assert _is_valid_action_ref("actions/checkout@a81bbbf8298c0fa03ea29cdc473d45769f953675")
    # Branch or mutable refs are rejected.
    assert not _is_valid_action_ref("actions/checkout@main")
    assert not _is_valid_action_ref("actions/checkout@master")
    assert not _is_valid_action_ref("actions/checkout@HEAD")
    # Malformed or missing refs are rejected.
    assert not _is_valid_action_ref("actions/checkout")
    assert not _is_valid_action_ref("actions/checkout@v4-beta")
    # Third-party actions need at least a semver-looking tag.
    assert _is_valid_action_ref("some-org/some-action@v1")
    assert not _is_valid_action_ref("some-org/some-action@main")


def test_workflows_parse_and_include_pipeline_steps():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))

    storm_workflow = (ROOT / ".github/workflows/storm-ambience.yml").read_text(encoding="utf-8")
    assert "Sincronizar main remoto antes da decisao" in storm_workflow
    assert "git checkout -B main origin/main" in storm_workflow
    assert "generate_storm_ambience.py" in storm_workflow
    assert "Storm ambience automation state -" in storm_workflow
    assert yaml.safe_load(storm_workflow)["concurrency"]["group"] == "storm-ambience"
    assert "Salvar marcadores no git" in storm_workflow
    assert 'cron: "10 3,15 * * *"' in storm_workflow

    dashboard_workflow = (ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8")
    assert "for path in index.html _data/analytics/latest.json" in dashboard_workflow
    assert "Analytics persistence skipped because live state changed during dashboard build" in dashboard_workflow
    assert "Analytics persistence skipped after repeated non-fast-forward pushes" in dashboard_workflow
    assert "run_intelligence_suite" not in dashboard_workflow

    alert_workflow = (ROOT / ".github/workflows/ops-alert.yml").read_text(encoding="utf-8")
    parsed_alert = yaml.safe_load(alert_workflow)
    assert parsed_alert["permissions"]["issues"] == "write"
    assert "Storm Ambience - rain & thunder for sleep" in alert_workflow
    assert "Storm Shorts - rain & thunder" in alert_workflow
    assert "Production quality gate" in alert_workflow
    assert "Build + deploy dashboard" in alert_workflow
    assert "CodeQL" in alert_workflow
    assert "Security, SBOM and license audit" in alert_workflow
    assert "Production smoke" in alert_workflow
    assert "Refresh Pexels queue" not in alert_workflow
    assert "TTS fallback health" not in alert_workflow
    assert "YouTube Bot - Shorts only" not in alert_workflow
    assert "OPS_ALERTS_ENABLED" in alert_workflow
    assert "gh issue create" in alert_workflow
    assert "gh issue comment" in alert_workflow


def test_storm_publisher_syncs_latest_main_before_publish_decision():
    workflow = yaml.safe_load((ROOT / ".github/workflows/storm-ambience.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["generate-and-upload"]["steps"]
    names = [step.get("name") for step in steps]

    sync_index = names.index("Sincronizar main remoto antes da decisao")
    assert sync_index < names.index("Gerar video de ambiencia de tempestade")
    assert sync_index < names.index("Upload para o YouTube")

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
    storm_ambience = yaml.safe_load((ROOT / ".github/workflows/storm-ambience.yml").read_text(encoding="utf-8"))

    assert dashboard["jobs"]["build"]["timeout-minutes"] >= 20
    assert quality_gate["jobs"]["validate"]["timeout-minutes"] >= 35
    assert storm_ambience["jobs"]["generate-and-upload"]["timeout-minutes"] <= 60
