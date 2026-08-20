from __future__ import annotations

import json

from utils.autonomous_benchmarks import run_benchmarks


def test_autonomous_control_plane_stays_within_resource_budget(tmp_path):
    output = tmp_path / "benchmark.json"
    report = run_benchmarks(output, iterations=10)
    assert report["passed"] is True
    assert report["measurements"]["peak_memory_mb"] < report["limits"]["peak_memory_mb"]
    assert report["measurements"]["opencv_mean_ms"] < report["limits"]["opencv_mean_ms"]
    assert report["measurements"]["audio_analysis_ms"] < report["limits"]["audio_analysis_ms"]
    assert report["audio_probe"]["rms_db"] > -60
    assert report["render_budget"]["status"] in {"unmeasured", "pass"}
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == 1
