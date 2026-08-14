"""Testes para utils/pipeline_metrics.py — metricas de pipeline
(record_pipeline_run + pipeline_summary)."""

import json

import pytest

from utils import pipeline_metrics as pm


@pytest.fixture(autouse=True)
def _isolate_metrics_file(tmp_path, monkeypatch):
    """Isola o arquivo de metricas para tmp_path para nao tocar em _data/ real."""
    monkeypatch.setattr(pm, "_metrics_file", lambda: tmp_path / "pipeline_metrics.json")


class TestRecordPipelineRun:
    def test_creates_file_with_first_entry(self, tmp_path):
        pm.record_pipeline_run("generate_short", success=True, duration_seconds=1.5, kind="vertical")
        data = json.loads((tmp_path / "pipeline_metrics.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        entry = data[0]
        assert entry["stage"] == "generate_short"
        assert entry["success"] is True
        assert entry["duration_seconds"] == 1.5
        assert entry["kind"] == "vertical"
        assert "at" in entry

    def test_appends_to_existing(self, tmp_path):
        path = tmp_path / "pipeline_metrics.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "stage": "upload",
                        "success": True,
                        "duration_seconds": 10,
                        "kind": "",
                        "at": "2026-01-01T00:00:00+00:00",
                    }
                ]
            ),
            encoding="utf-8",
        )
        pm.record_pipeline_run("generate_short", success=False, duration_seconds=2.0)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[1]["stage"] == "generate_short"
        assert data[1]["success"] is False

    def test_recovers_from_invalid_json(self, tmp_path):
        path = tmp_path / "pipeline_metrics.json"
        path.write_text("not json", encoding="utf-8")
        pm.record_pipeline_run("upload", success=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["stage"] == "upload"

    def test_recovers_from_non_list_json(self, tmp_path):
        path = tmp_path / "pipeline_metrics.json"
        path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        pm.record_pipeline_run("upload", success=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 1

    def test_bounded_to_last_500_entries(self, tmp_path):
        for i in range(505):
            pm.record_pipeline_run("upload", success=True, duration_seconds=float(i))
        data = json.loads((tmp_path / "pipeline_metrics.json").read_text(encoding="utf-8"))
        assert len(data) == pm._MAX_ENTRIES == 500
        assert data[0]["duration_seconds"] == 5.0
        assert data[-1]["duration_seconds"] == 504.0

    def test_default_duration_and_kind(self, tmp_path):
        pm.record_pipeline_run("upload", success=True)
        data = json.loads((tmp_path / "pipeline_metrics.json").read_text(encoding="utf-8"))
        assert data[0]["duration_seconds"] == 0.0
        assert data[0]["kind"] == ""

    def test_success_coerced_to_bool(self, tmp_path):
        pm.record_pipeline_run("upload", success=1)
        data = json.loads((tmp_path / "pipeline_metrics.json").read_text(encoding="utf-8"))
        assert data[0]["success"] is True


class TestPipelineSummary:
    def test_empty_when_file_missing(self):
        summary = pm.pipeline_summary()
        assert summary == {"total_runs": 0, "stages": {}}

    def test_empty_when_invalid_json(self, tmp_path):
        path = tmp_path / "pipeline_metrics.json"
        path.write_text("not json", encoding="utf-8")
        assert pm.pipeline_summary() == {"total_runs": 0, "stages": {}}

    def test_aggregates_per_stage(self, tmp_path):
        path = tmp_path / "pipeline_metrics.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "stage": "generate_short",
                        "success": True,
                        "duration_seconds": 10,
                        "kind": "vertical",
                        "at": "t1",
                    },
                    {
                        "stage": "generate_short",
                        "success": False,
                        "duration_seconds": 20,
                        "kind": "vertical",
                        "at": "t2",
                    },
                    {
                        "stage": "generate_short",
                        "success": True,
                        "duration_seconds": 30,
                        "kind": "vertical",
                        "at": "t3",
                    },
                    {"stage": "upload", "success": True, "duration_seconds": 5, "kind": "liquid_wire", "at": "t4"},
                ]
            ),
            encoding="utf-8",
        )
        summary = pm.pipeline_summary()
        assert summary["total_runs"] == 4
        short = summary["stages"]["generate_short"]
        assert short["runs"] == 3
        assert short["successes"] == 2
        assert short["failures"] == 1
        assert short["success_rate"] == 2 / 3
        assert short["avg_duration_seconds"] == 20.0
        upload = summary["stages"]["upload"]
        assert upload["runs"] == 1
        assert upload["success_rate"] == 1.0
        assert upload["avg_duration_seconds"] == 5.0

    def test_skips_entries_without_stage(self, tmp_path):
        path = tmp_path / "pipeline_metrics.json"
        path.write_text(
            json.dumps(
                [
                    {"stage": "upload", "success": True, "duration_seconds": 1, "kind": "", "at": "t"},
                    {"success": True, "duration_seconds": 1, "at": "t"},
                    {"stage": "", "success": True, "at": "t"},
                ]
            ),
            encoding="utf-8",
        )
        summary = pm.pipeline_summary()
        assert summary["total_runs"] == 3
        assert list(summary["stages"].keys()) == ["upload"]

    def test_zero_division_safe_when_no_runs(self):
        assert pm.pipeline_summary() == {"total_runs": 0, "stages": {}}

    def test_handles_non_list_file(self, tmp_path):
        path = tmp_path / "pipeline_metrics.json"
        path.write_text(json.dumps({"not": "list"}), encoding="utf-8")
        assert pm.pipeline_summary() == {"total_runs": 0, "stages": {}}

    def test_does_not_leak_total_duration_field(self, tmp_path):
        path = tmp_path / "pipeline_metrics.json"
        path.write_text(
            json.dumps([{"stage": "upload", "success": True, "duration_seconds": 5, "kind": "", "at": "t"}]),
            encoding="utf-8",
        )
        summary = pm.pipeline_summary()
        assert "total_duration" not in summary["stages"]["upload"]
