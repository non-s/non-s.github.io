from pathlib import Path

import yaml

from scripts.check_workflow_contracts import check_workflow_contracts
from scripts.run_intelligence_suite import SCRIPT_SETS

ROOT = Path(__file__).resolve().parent.parent


def test_all_workflows_follow_safety_contracts():
    assert check_workflow_contracts(ROOT) == []


def test_workflows_parse_and_include_growth_steps():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))

    youtube_workflow = (ROOT / ".github/workflows/youtube-bot.yml").read_text(encoding="utf-8")
    assert "quota_preflight.py youtube-bot --json --check-only" in youtube_workflow
    assert "Registrar quota consumida" not in youtube_workflow
    assert "PUBLISH_EVENT_SCHEDULE_CRON" in youtube_workflow
    assert "skip_quota_guard" in youtube_workflow
    assert "Sincronizar main remoto antes da decisao" in youtube_workflow
    assert "git checkout -B main origin/main" in youtube_workflow
    assert "Garantir fila minima" in youtube_workflow
    assert "python fetch_animals.py" in youtube_workflow
    assert "scripts/queue_ready_count.py --refresh --json" in youtube_workflow
    assert "publish_eligible" in youtube_workflow
    assert "count_field pending" in youtube_workflow
    assert "PUBLISH_BACKFILL_READY_TARGET || '6'" in youtube_workflow
    assert 'target="${QUEUE_TARGET_PUBLISH_READY:-6}"' in youtube_workflow
    assert "PUBLISH_MIN_READY_TO_PUBLISH || '1'" in youtube_workflow
    assert 'minimum_to_publish="${QUEUE_MIN_READY_TO_PUBLISH:-1}"' in youtube_workflow
    assert "QUEUE_TARGET_PENDING: ${{ vars.PUBLISH_BACKFILL_QUEUE_TARGET || '18' }}" in youtube_workflow
    assert 'BROLL_SOURCE_MODE: "pexels"' in youtube_workflow
    assert "BROLL_SOURCE_MODE: ${{ vars.BROLL_SOURCE_MODE || 'pexels' }}" in youtube_workflow
    assert "PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY || secrets.PEXELS }}" in youtube_workflow
    assert "MUSIC_BED_ENABLED: ${{ vars.MUSIC_BED_ENABLED || '0' }}" in youtube_workflow
    assert "QUEUE_BACKFILL_PENDING_BATCH: ${{ vars.PUBLISH_BACKFILL_PENDING_BATCH || '6' }}" in youtube_workflow
    assert "QUEUE_BACKFILL_TIMEOUT_SECONDS: ${{ vars.PUBLISH_BACKFILL_TIMEOUT_SECONDS || '540' }}" in youtube_workflow
    assert "PEXELS_SEARCH_PER_PAGE: ${{ vars.PEXELS_SEARCH_PER_PAGE || '32' }}" in youtube_workflow
    assert "PEXELS_DISCOVERY_PAGES: ${{ vars.PEXELS_DISCOVERY_PAGES || '2' }}" in youtube_workflow
    assert "PEXELS_BACKFILL_QUERY_TAKE: ${{ vars.PEXELS_BACKFILL_QUERY_TAKE || '6' }}" in youtube_workflow
    assert "PEXELS_TOPIC_CALL_BUDGET: ${{ vars.PEXELS_TOPIC_CALL_BUDGET || '2' }}" in youtube_workflow
    assert "PEXELS_DEEP_SEARCH_GAP: ${{ vars.PEXELS_DEEP_SEARCH_GAP || '8' }}" in youtube_workflow
    assert "base_pending_target + (attempt - 1) * pending_batch" in youtube_workflow
    assert "QUEUE_BACKFILL_ATTEMPTS" in youtube_workflow
    assert 'while [ "${publishable}" -lt "${minimum_to_publish}" ]' in youtube_workflow
    assert "Publish-eligible inventory can satisfy this one-Short run" in youtube_workflow
    assert "at least one Short clears final publish quality" in youtube_workflow
    assert "fetch-content owns deeper replenishment" in youtube_workflow
    assert 'timeout "${backfill_timeout}s" python fetch_animals.py' in youtube_workflow
    assert (
        'while { [ "${ready}" -lt "${target}" ] || [ "${pending}" -lt "${base_pending_target}" ]; }'
        not in youtube_workflow
    )
    assert "REQUIRE_SHORT_ON_PUBLISH" in youtube_workflow
    assert 'hard_fail_decisions = {"skip_no_eligible_story", "skip_low_queue_quality"}' in youtube_workflow
    assert "Publishing was required, but the publish window could not select an eligible Short" in youtube_workflow
    assert "REQUIRE_UPLOAD_ON_PUBLISH" in youtube_workflow
    assert "Sincronizar diagnosticos da fila" in youtube_workflow
    assert "python scripts/run_intelligence_suite.py queue" in youtube_workflow
    assert "YouTube automation state -" in youtube_workflow
    assert "merge_jsonl_state.py" in youtube_workflow
    assert "reconcile_queue_uploads.py" in youtube_workflow
    assert "jsonl_merge_paths" in youtube_workflow
    assert yaml.safe_load(youtube_workflow)["concurrency"]["group"] == "youtube-publisher"
    assert "_data/analytics/api_quota_ledger.jsonl" in youtube_workflow
    assert "_data/rejected_queue.jsonl" in youtube_workflow
    assert "if: always() && env.PUBLISH_QUOTA_BLOCKED != '1'" in youtube_workflow
    assert "Sincronizar diagnosticos da fila" in youtube_workflow
    assert "Salvar marcadores no git" in youtube_workflow
    assert (
        "steps.publish_window.outputs.should_publish == 'true'\n        run: python scripts/run_intelligence_suite.py queue"
        not in youtube_workflow
    )
    assert 'cron: "2 * * * *"' in youtube_workflow
    assert 'cron: "22 * * * *"' in youtube_workflow
    assert 'cron: "42 * * * *"' in youtube_workflow
    watchdog_workflow = (ROOT / ".github/workflows/youtube-watchdog.yml").read_text(encoding="utf-8")
    assert 'cron: "7,17,27,37,47,57 * * * *"' in watchdog_workflow
    assert 'GRACE_MINUTES: "12"' in watchdog_workflow
    assert 'PUBLISH_SLOT_WINDOW_MINUTES: "60"' in watchdog_workflow
    assert "python scripts/youtube_slot_dispatch.py watchdog" in watchdog_workflow
    fetch_workflow = (ROOT / ".github/workflows/fetch-content.yml").read_text(encoding="utf-8")
    assert 'cron: "9,23 * * * *"' in fetch_workflow
    assert 'workflows: ["YouTube Bot - Shorts only"]' in fetch_workflow
    assert "github.event.workflow_run.conclusion != 'cancelled'" in fetch_workflow
    assert "Failed publisher" in fetch_workflow
    assert "do not hold the" in fetch_workflow
    assert 'BROLL_SOURCE_MODE: "pexels"' in fetch_workflow
    assert "PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY || secrets.PEXELS }}" in fetch_workflow
    assert "FETCH_REFRESH_TIMEOUT_SECONDS: ${{ vars.FETCH_REFRESH_TIMEOUT_SECONDS || '720' }}" in fetch_workflow
    assert "Pexels refresh timed out; leaving generated diagnostics uncommitted" in fetch_workflow
    assert "apply_topic_freshness.py" in fetch_workflow
    assert "quota_preflight.py fetch-content --json --no-fail-on-block" in fetch_workflow
    assert "FETCH_QUOTA_BLOCKED" in fetch_workflow
    assert 'if [ "${FETCH_QUOTA_BLOCKED:-0}" = "1" ]; then' in fetch_workflow
    assert "Sync latest main before queue refresh" in fetch_workflow
    assert "git checkout -B main origin/main" in fetch_workflow
    assert "leaving generated diagnostics uncommitted" in fetch_workflow
    assert "QUEUE_TARGET_PENDING || '72'" in fetch_workflow
    assert yaml.safe_load(fetch_workflow)["concurrency"]["group"] == "queue-refresh"
    assert "PEXELS_SEARCH_PER_PAGE: ${{ vars.PEXELS_SEARCH_PER_PAGE || '32' }}" in fetch_workflow
    assert "PEXELS_DISCOVERY_PAGES: ${{ vars.PEXELS_DISCOVERY_PAGES || '2' }}" in fetch_workflow
    assert "PEXELS_BACKFILL_QUERY_TAKE: ${{ vars.PEXELS_BACKFILL_QUERY_TAKE || '6' }}" in fetch_workflow
    assert "PEXELS_TOPIC_CALL_BUDGET: ${{ vars.PEXELS_TOPIC_CALL_BUDGET || '2' }}" in fetch_workflow
    assert "PEXELS_DEEP_SEARCH_GAP: ${{ vars.PEXELS_DEEP_SEARCH_GAP || '8' }}" in fetch_workflow
    assert "merge_jsonl_state.py" in fetch_workflow
    assert "reconcile_queue_uploads.py" in fetch_workflow
    assert "jsonl_merge_paths" in fetch_workflow
    assert "_data/scale_blueprint.json" in fetch_workflow
    assert "compact_analytics.py" in (ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8")
    assert "_data/scale_blueprint.json" in (ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8")
    assert "check_repo_contracts.py" in (ROOT / ".github/workflows/quality-gate.yml").read_text(encoding="utf-8")
    assert "_data/next_shorts.json" in fetch_workflow
    assert "_data/control_plane_report.json" in fetch_workflow
    assert "_data/queue_audit.json" in fetch_workflow
    assert "_data/dry_run_publish.json" in fetch_workflow
    assert "_data/reject_report.json" in fetch_workflow
    assert "_data/next_shorts.json" in youtube_workflow
    assert "_data/scale_blueprint.json" in youtube_workflow
    assert "_data/control_plane_report.json" in youtube_workflow
    assert "_data/queue_audit.json" in youtube_workflow
    assert "_data/dry_run_publish.json" in youtube_workflow
    assert "_data/reject_report.json" in youtube_workflow
    dashboard_workflow = (ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8")
    assert "_data/next_shorts.json" in dashboard_workflow
    assert "_data/control_plane_report.json" in dashboard_workflow
    assert "_data/analytics/weekly_summary.json" in dashboard_workflow
    assert "_data/experiments_recommendations.json" in dashboard_workflow
    assert "_data/post_upload_session_ops.json" in dashboard_workflow

    heartbeat_workflow = (ROOT / ".github/workflows/youtube-hourly-heartbeat.yml").read_text(encoding="utf-8")
    assert 'cron: "13 * * * *"' in heartbeat_workflow
    assert 'workflows: ["Refresh Pexels queue"]' in heartbeat_workflow
    assert "github.event.workflow_run.conclusion == 'success'" in heartbeat_workflow
    assert 'TARGET_WORKFLOW: "youtube-bot.yml"' in heartbeat_workflow
    assert "PUBLISH_HEARTBEAT_RECENT_RUN_TOLERANCE_MINUTES || '20'" in heartbeat_workflow
    assert 'PUBLISH_SLOT_WINDOW_MINUTES: "60"' in heartbeat_workflow
    assert "heartbeat recovery for slot" in heartbeat_workflow
    assert "python scripts/youtube_slot_dispatch.py heartbeat" in heartbeat_workflow
    assert "time.sleep" not in heartbeat_workflow

    alert_workflow = (ROOT / ".github/workflows/ops-alert.yml").read_text(encoding="utf-8")
    parsed_alert = yaml.safe_load(alert_workflow)
    assert parsed_alert["permissions"]["issues"] == "write"
    assert "YouTube Bot - Shorts only" in alert_workflow
    assert "Refresh Pexels queue" in alert_workflow
    assert "YouTube hourly heartbeat" in alert_workflow
    assert "YouTube publishing watchdog" in alert_workflow
    assert "Production quality gate" in alert_workflow
    assert "Build + deploy dashboard" in alert_workflow
    assert "CodeQL" in alert_workflow
    assert "Security, SBOM and license audit" in alert_workflow
    assert "TTS fallback health" in alert_workflow
    assert "Production smoke" in alert_workflow
    assert "OPS_ALERTS_ENABLED" in alert_workflow
    assert "gh issue create" in alert_workflow
    assert "gh issue comment" in alert_workflow


def test_youtube_publisher_syncs_latest_main_before_publish_decision():
    workflow = yaml.safe_load((ROOT / ".github/workflows/youtube-bot.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["generate-and-upload"]["steps"]
    names = [step.get("name") for step in steps]

    sync_index = names.index("Sincronizar main remoto antes da decisao")
    assert sync_index < names.index("Garantir fila minima")
    assert sync_index < names.index("Preparar inteligencia pre-publicacao")
    assert sync_index < names.index("Decidir janela de publicacao")

    sync_step = steps[sync_index]
    assert "git fetch origin main" in sync_step["run"]
    assert "git checkout -B main origin/main" in sync_step["run"]


def test_queue_refresh_syncs_latest_main_before_generating_state():
    workflow = yaml.safe_load((ROOT / ".github/workflows/fetch-content.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["refresh-queue"]["steps"]
    names = [step.get("name") for step in steps]

    sync_index = names.index("Sync latest main before queue refresh")
    assert sync_index < names.index("Refresh Pexels stories")
    assert sync_index < names.index("Reconcile uploaded queue state")
    assert sync_index < names.index("Commit queue state")

    sync_step = steps[sync_index]
    assert "git fetch origin main" in sync_step["run"]
    assert "git checkout -B main origin/main" in sync_step["run"]


def test_dashboard_strict_audit_keeps_youtube_token_when_available():
    workflow = yaml.safe_load((ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["build"]["steps"]
    refresh = next(step for step in steps if step.get("name") == "Refresh YouTube analytics snapshot")
    audit = next(step for step in steps if step.get("name") == "Audit local automation health")

    assert "YOUTUBE_TOKEN" in refresh.get("env", {})
    assert "python scripts/run_intelligence_suite.py dashboard" not in refresh.get("run", "")
    assert "printf '%s' \"$YOUTUBE_TOKEN\" | python -m json.tool > /dev/null" in refresh.get("run", "")
    assert "youtube_token.json" not in refresh.get("run", "")
    assert "YOUTUBE_TOKEN" in audit.get("env", {})
    audit_run = audit.get("run", "")
    assert "[ ! -f youtube_token.json ]" in audit_run
    assert "trap 'rm -f youtube_token.json' EXIT" in audit_run
    assert "python scripts/run_intelligence_suite.py dashboard --strict" in audit_run


def test_expensive_workflows_have_realistic_timeouts():
    dashboard = yaml.safe_load((ROOT / ".github/workflows/dashboard.yml").read_text(encoding="utf-8"))
    quality_gate = yaml.safe_load((ROOT / ".github/workflows/quality-gate.yml").read_text(encoding="utf-8"))
    heartbeat = yaml.safe_load((ROOT / ".github/workflows/youtube-hourly-heartbeat.yml").read_text(encoding="utf-8"))

    assert dashboard["jobs"]["build"]["timeout-minutes"] >= 20
    assert quality_gate["jobs"]["validate"]["timeout-minutes"] >= 35
    assert heartbeat["jobs"]["dispatch-hourly"]["timeout-minutes"] <= 8


def test_queue_prune_refreshes_reports_after_mutating_queue():
    dashboard = SCRIPT_SETS["dashboard"]
    prune_index = max(i for i, script in enumerate(dashboard) if script == "scripts/prune_queue.py")
    for report in (
        "scripts/apply_topic_freshness.py",
        "scripts/agency_gate_report.py",
        "scripts/queue_audit.py",
        "scripts/dry_run_publish.py",
        "scripts/next_shorts.py",
        "scripts/packaging_report.py",
        "scripts/youtube_brain_report.py",
        "scripts/audit_automation.py",
    ):
        assert max(i for i, script in enumerate(dashboard) if script == report) > prune_index
    for mode in ("pre_generate", "queue"):
        scripts = SCRIPT_SETS[mode]
        prune_index = max(i for i, script in enumerate(scripts) if script == "scripts/prune_queue.py")
        for report in (
            "scripts/apply_topic_freshness.py",
            "scripts/sequence_plan.py",
            "scripts/autonomous_growth_loop.py",
            "scripts/agency_gate_report.py",
            "scripts/packaging_report.py",
            "scripts/youtube_brain_report.py",
            "scripts/audit_automation.py",
        ):
            assert max(i for i, script in enumerate(scripts) if script == report) > prune_index
        for report in (
            "scripts/queue_audit.py",
            "scripts/dry_run_publish.py",
            "scripts/reject_report.py",
            "scripts/next_shorts.py",
        ):
            assert max(i for i, script in enumerate(scripts) if script == report) > prune_index

    post_publish = SCRIPT_SETS["post_publish"]
    post_prune = max(i for i, script in enumerate(post_publish) if script == "scripts/prune_queue.py")
    for report in (
        "scripts/apply_topic_freshness.py",
        "scripts/agency_gate_report.py",
        "scripts/queue_audit.py",
        "scripts/dry_run_publish.py",
        "scripts/reject_report.py",
        "scripts/packaging_report.py",
        "scripts/youtube_brain_report.py",
        "scripts/next_shorts.py",
        "scripts/audit_automation.py",
    ):
        assert max(i for i, script in enumerate(post_publish) if script == report) > post_prune


def test_final_automation_health_runs_after_queue_reports():
    for mode in ("pre_generate", "post_publish", "queue", "dashboard"):
        scripts = SCRIPT_SETS[mode]
        final_audit = max(i for i, script in enumerate(scripts) if script == "scripts/audit_automation.py")
        for report in (
            "scripts/prune_queue.py",
            "scripts/queue_audit.py",
            "scripts/dry_run_publish.py",
            "scripts/next_shorts.py",
            "scripts/scale_blueprint.py",
        ):
            assert final_audit > max(i for i, script in enumerate(scripts) if script == report)


def test_next_shorts_refreshes_after_queue_mutations_and_weekly_review():
    for mode in ("pre_generate", "queue"):
        scripts = SCRIPT_SETS[mode]
        next_index = max(i for i, script in enumerate(scripts) if script == "scripts/next_shorts.py")
        for mutator in ("scripts/prune_queue.py", "scripts/agency_gate_report.py", "scripts/packaging_report.py"):
            assert next_index > max(i for i, script in enumerate(scripts) if script == mutator)

    dashboard = SCRIPT_SETS["dashboard"]
    assert max(i for i, script in enumerate(dashboard) if script == "scripts/next_shorts.py") > max(
        i for i, script in enumerate(dashboard) if script == "scripts/weekly_growth_review.py"
    )
    final_next = max(i for i, script in enumerate(dashboard) if script == "scripts/next_shorts.py")
    final_prune = max(i for i, script in enumerate(dashboard) if script == "scripts/prune_queue.py")
    assert final_prune < final_next
    for report in (
        "scripts/agency_gate_report.py",
        "scripts/queue_audit.py",
        "scripts/dry_run_publish.py",
        "scripts/reject_report.py",
    ):
        assert final_prune < max(i for i, script in enumerate(dashboard) if script == report) < final_next


def test_dashboard_suite_refreshes_dashboard_only_operational_reports():
    dashboard = SCRIPT_SETS["dashboard"]
    for script in (
        "scripts/queue_audit.py",
        "scripts/dry_run_publish.py",
        "scripts/reject_report.py",
    ):
        assert script in dashboard

    growth_index = max(i for i, script in enumerate(dashboard) if script == "scripts/autonomous_growth_loop.py")
    for script in ("scripts/queue_audit.py", "scripts/dry_run_publish.py"):
        assert max(i for i, item in enumerate(dashboard) if item == script) > growth_index
    comment_index = max(i for i, script in enumerate(dashboard) if script == "scripts/comment_to_short_pipeline.py")
    for script in (
        "scripts/prune_queue.py",
        "scripts/agency_gate_report.py",
        "scripts/queue_audit.py",
        "scripts/dry_run_publish.py",
        "scripts/reject_report.py",
        "scripts/next_shorts.py",
    ):
        assert max(i for i, item in enumerate(dashboard) if item == script) > comment_index


def test_session_graph_actioner_runs_after_graph_refresh():
    for mode in ("dashboard", "post_publish"):
        scripts = SCRIPT_SETS[mode]
        graph_index = max(i for i, script in enumerate(scripts) if script == "scripts/post_upload_session_ops.py")
        actioner_index = max(i for i, script in enumerate(scripts) if script == "scripts/session_graph_actioner.py")
        assert graph_index < actioner_index
