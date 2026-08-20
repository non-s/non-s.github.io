import json
from datetime import UTC, datetime

from utils.atomic_state import save_versioned
from utils.excellence_evidence import live_claims, verified_claims, youtube_learning_claims


def test_live_claims_measure_recovery_but_do_not_invent_six_hours(tmp_path):
    journal = tmp_path / "live_continuity.json"
    journal.write_text(json.dumps({
        "started_at": "2026-08-20T18:00:00Z",
        "completed_at": "2026-08-20T18:10:00Z",
        "attempts": [
            {"broadcast_id": "a", "outcome": "disconnected", "error_type": "CalledProcessError"},
            {"broadcast_id": "b", "outcome": "completed", "recovery_latency_seconds": 2.839},
        ],
    }), encoding="utf-8")

    claims, details = live_claims([journal])

    assert claims == {
        "immediate_failure_handoff": True,
        "six_hour_session": False,
        "chaos_disconnect_recovery": True,
    }
    assert details["recovery_latencies_seconds"] == [2.839]


def test_live_claims_merge_overlapping_runner_coverage(tmp_path):
    paths = []
    for index, (start, end) in enumerate([
        ("2026-08-20T00:00:00Z", "2026-08-20T05:30:00Z"),
        ("2026-08-20T05:00:00Z", "2026-08-20T06:30:00Z"),
    ]):
        path = tmp_path / str(index) / "live_continuity.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"started_at": start, "completed_at": end, "attempts": []}), encoding="utf-8")
        paths.append(path)

    claims, details = live_claims(paths)

    assert claims["six_hour_session"] is True
    assert details["longest_continuous_coverage_seconds"] == 23_400


def test_external_claim_requires_current_attributed_https_evidence(tmp_path):
    path = tmp_path / "observations.json"
    path.write_text(json.dumps({"observations": [
        {"area": "engineering_quality", "criterion": "ci_green", "passed": True,
         "observed_at": "2026-08-20T10:00:00Z", "expires_at": "2026-08-21T10:00:00Z",
         "verifier": "github-actions", "evidence_url": "https://github.com/example/actions/1"},
        {"area": "live_continuity", "criterion": "public_playback_verified", "passed": True},
    ]}), encoding="utf-8")

    claims, accepted = verified_claims([path], now=datetime(2026, 8, 20, 12, tzinfo=UTC))

    assert claims == {"engineering_quality": {"ci_green": True}}
    assert len(accepted) == 1


def test_youtube_learning_claims_require_observed_joined_samples(tmp_path):
    (tmp_path / "analytics.json").write_text(
        json.dumps({"collected_at": "2026-08-20T10:00:00Z", "total_videos": 30}),
        encoding="utf-8",
    )
    catalog = []
    for index in range(30):
        catalog.append(
            {
                "content_id": f"lw-{index}",
                "youtube_video_id": f"yt-{index}",
                "fitness_window": "72h",
                "fitness": {"score": 0.5, "confidence": 0.8},
                "genome": {
                    "generation": 1 if index == 0 else 0,
                    "mutations": [{"field": "melt_rate"}] if index == 0 else [],
                },
            }
        )
    save_versioned(tmp_path / "catalog_memory.json", catalog, 1)
    save_versioned(
        tmp_path / "research_ledger.json",
        {
            "hypotheses": {},
            "experiments": {
                "exp-1": {
                    "result": {
                        "samples": 30,
                        "confidence": 0.7,
                        "effect": 0.08,
                        "status": "supported",
                    }
                }
            },
        },
        1,
    )

    claims, details = youtube_learning_claims(
        tmp_path, now=datetime(2026, 8, 20, 12, tzinfo=UTC)
    )

    assert all(claims.values())
    assert details["joined_fitness_records"] == 30
    assert details["fitness_records"] == 30
    assert details["governed_evolution_records"] == 1
    assert details["causal_results"][0]["experiment_id"] == "exp-1"


def test_youtube_learning_claims_fail_closed_for_stale_or_sparse_data(tmp_path):
    (tmp_path / "analytics.json").write_text(
        json.dumps({"collected_at": "2026-08-01T10:00:00Z", "total_videos": 100}),
        encoding="utf-8",
    )

    claims, details = youtube_learning_claims(
        tmp_path, now=datetime(2026, 8, 20, 12, tzinfo=UTC)
    )

    assert not any(claims.values())
    assert details["fitness_records"] == 0
