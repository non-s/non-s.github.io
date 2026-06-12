from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.audit_slot_contracts import audit_slot_contracts
from scripts.upload_intent import build_upload_intent, duplicate_uploaded, write_upload_intent
from utils.analytics_schema import build_video_metric_row
from utils.claim_risk import evaluate_claim_risk
from utils.comment_policy import classify_comment
from utils.experiment_registry import build_registry, validate_registry
from utils.experiment_scheduler import plan_experiment_schedule
from utils.frame_zero_packaging import score_frame_zero
from utils.hook_library import score_hook
from utils.loop_semantics import score_loop_semantics
from utils.opening_gate_v2 import evaluate_opening_gate
from utils.originality_pack import build_originality_pack, stable_hash
from utils.payoff_controller import score_payoff
from utils.retention_warehouse import reconcile_studio_api
from utils.rights_guard import evaluate_rights_guard
from utils.search_enrichment import enrich_search_terms
from utils.story_patterns import classify_story_pattern
from utils.time_semantics import (
    CURRENT_VIEWS_REGIME,
    LEGACY_VIEWS_REGIME,
    publish_day_pt,
    temporal_fields,
    views_regime,
)
from utils.voice_registry import voice_profile


def test_time_semantics_use_pacific_days_and_views_cutover():
    fields = temporal_fields(now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc))

    assert fields["publish_day_pt"] == "2026-06-10"
    assert fields["quota_day_pt"] == "2026-06-10"
    assert publish_day_pt("2026-12-01T05:23:00+00:00") == "2026-11-30"
    assert views_regime("2025-03-30T20:00:00+00:00") == LEGACY_VIEWS_REGIME
    assert views_regime("2025-04-01T07:00:00+00:00") == CURRENT_VIEWS_REGIME


def test_slot_audit_checks_bot_watchdog_docs_and_temporal_fields(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    slots = " ".join(f"{hour:02d}:00" for hour in range(24))
    (tmp_path / ".github" / "workflows" / "youtube-bot.yml").write_text(
        'on:\n  schedule:\n    - cron: "0 * * * *"\n',
        encoding="utf-8",
    )
    (tmp_path / ".github" / "workflows" / "youtube-watchdog.yml").write_text(slots, encoding="utf-8")
    docs = slots + " publish_ts_utc publish_day_pt quota_day_pt views_regime"
    (tmp_path / "README.md").write_text(docs, encoding="utf-8")
    (tmp_path / "docs" / "ENVIRONMENT.md").write_text(docs, encoding="utf-8")
    (tmp_path / "docs" / "WILD_BRIEF_WORLD_CLASS_UPGRADE.md").write_text(docs, encoding="utf-8")

    assert audit_slot_contracts(tmp_path)["ok"] is True
    (tmp_path / ".github" / "workflows" / "youtube-watchdog.yml").write_text("14:00 19:00 23:00", encoding="utf-8")

    errors = audit_slot_contracts(tmp_path)["errors"]
    assert any("05:00" in error and "watchdog" in error for error in errors)


def test_opening_gate_v2_scores_first_windows_and_can_block():
    strong = evaluate_opening_gate(
        {"hook": "Why this octopus changes color before escape", "thumbnail_text": "COLOR ESCAPE", "has_broll": True},
        transcript_words=[{"word": "Why", "start": 0.2}],
        mode="block",
    )
    weak = evaluate_opening_gate(
        {"hook": "This animal is amazing", "thumbnail_text": "TOO MANY WORDS ON SCREEN NOW", "has_broll": False},
        transcript_words=[{"word": "This", "start": 2.4}],
        mode="block",
    )

    assert strong["approved"] is True
    assert strong["subscores"]["score_first_0_7s"] >= 70
    assert weak["approved"] is False
    assert "first_word_after_1_5s" in weak["reasons"]


def test_hook_patterns_payoff_and_loop_semantics_reward_specific_callbacks():
    story = {
        "title": "Octopus escape trick",
        "hook": "This octopus changes color before escape.",
        "script": "This octopus changes color before escape. Because the flash confuses predators, it gets one second to vanish. Now the color at the start makes sense.",
        "category": "octopus",
    }

    assert classify_story_pattern(story)["cluster"] in {"Survival Cheats", "Hidden Behaviors"}
    assert score_hook(story["hook"], story)["score"] > score_hook("You won't believe what happens next", story)["score"]
    assert score_payoff(story["script"], story["hook"])["payoff_second"] < 12
    loop = score_loop_semantics(story["script"], story["hook"])
    assert loop["state"] == "live_loop"
    assert loop["callback_keyword_overlap"] > 0


def test_claim_risk_rights_and_originality_pack_are_deterministic():
    unsupported = {"script": "This is the deadliest frog ever discovered and it always wins."}
    supported = {
        "story_id": "frog-1",
        "title": "Poison frog signal",
        "script": "Some poison frogs can warn predators with bright color.",
        "source_url": "https://example.org/frog",
        "source_license": "Pexels License",
        "source_clip_id": "clip-1",
        "video": "_videos/short-frog.mp4",
        "has_broll": True,
        "has_captions": True,
    }

    assert evaluate_claim_risk(unsupported)["level"] == "block"
    assert evaluate_claim_risk(supported)["level"] == "safe"
    assert evaluate_rights_guard({**supported, "title": "Disney animal face"})["state"] == "manual_review"
    pack = build_originality_pack(supported)
    assert pack["complete"] is True
    assert stable_hash(pack) == stable_hash(build_originality_pack(supported))


def test_experiment_registry_and_scheduler_enforce_low_volume_limits():
    registry = build_registry()
    assert validate_registry(registry)["ok"] is True

    plan = plan_experiment_schedule(
        registry,
        engaged_views_per_day=371,
        active_axes=["hook_style", "loop_style", "cta_style"],
    )

    assert plan["limits"]["multivariate_allowed"] is False
    assert any(row["axis"] == "loop_style" for row in plan["underpowered_tests"])


def test_retention_warehouse_and_analytics_row_include_new_fields():
    row = build_video_metric_row(
        "vid1",
        "Title",
        {"views": 100, "engaged_views": 76, "average_view_percentage": 64},
        context={"publish_ts_utc": "2026-06-11T05:23:00+00:00"},
    )
    rec = reconcile_studio_api({"plays": 100, "engaged_views": 76}, row["metrics"])

    assert row["publish_day_pt"] == "2026-06-10"
    assert row["metrics"]["plays"] == 100
    assert "continued_watch_rate" in row["metrics"]
    assert rec["within_2pct"] is True


def test_upload_intent_records_prepared_and_detects_uploaded_duplicates(tmp_path):
    path = tmp_path / "upload_intents.jsonl"
    meta = {"story_id": "story-1", "script": "A tight script", "experiments": {"hook_style": "question"}}
    prepared = build_upload_intent(meta, slot="05:23", status="prepared")
    uploaded = {**prepared, "status": "uploaded", "video_id": "yt123"}

    assert write_upload_intent(prepared, path)["written"] is True
    assert write_upload_intent(uploaded, path)["written"] is True
    assert write_upload_intent(uploaded, path)["written"] is False
    assert duplicate_uploaded(prepared, path)["video_id"] == "yt123"


def test_p1_helpers_cover_search_frame_comment_and_voice():
    story = {
        "title": "Octopus biology",
        "script": "The octopus is a cephalopod.",
        "scientific_name": "Octopus vulgaris",
    }

    assert "octopus vulgaris" in enrich_search_terms(story)["search_terms"]
    assert score_frame_zero({"thumbnail_text": "COLOR ESCAPE", "has_broll": True})["approved"] is True
    assert classify_comment("Can you explain octopus camouflage?")["state"] == "short_candidate"
    assert voice_profile("pt-BR")["primary"].startswith("pt-BR")


def test_jsonl_seed_files_are_valid():
    root = Path(__file__).resolve().parents[1]
    for rel in (
        "_data/upload_intents.jsonl",
        "_data/fact_sources.jsonl",
        "_data/source_provenance.jsonl",
        "_data/originality_pack.jsonl",
    ):
        for line in (root / rel).read_text(encoding="utf-8").splitlines():
            assert json.loads(line)
