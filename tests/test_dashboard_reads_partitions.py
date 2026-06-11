import importlib
import json
import sys
from pathlib import Path


def test_dashboard_reads_compacted_partitions_when_csv_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts))
    sys.modules.pop("build_dashboard", None)
    import build_dashboard

    dashboard = importlib.reload(build_dashboard)
    partition = tmp_path / "_data" / "analytics" / "partitions" / "video_metrics" / "2026-06.jsonl"
    partition.parent.mkdir(parents=True)
    partition.write_text(
        json.dumps({"pulled_at": "2026-06-10", "metrics": {"views": 12, "average_view_percentage": 66}}) + "\n",
        encoding="utf-8",
    )

    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")

    assert "Daily views" in body
