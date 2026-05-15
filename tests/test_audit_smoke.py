"""Smoke test: ensure audit_site.py runs against the repo's own _posts/."""
import importlib
import json
from pathlib import Path


def test_audit_site_runs(tmp_path, monkeypatch):
    """Running audit_site.main() against the repo should produce a JSON report."""
    audit = importlib.import_module("audit_site")

    # Redirect output to a temp dir so the test never overwrites the real report.
    fake_data_dir = tmp_path / "_data"
    fake_data_dir.mkdir()
    monkeypatch.setattr(audit, "DATA_DIR", fake_data_dir)
    monkeypatch.setattr(audit, "OUTPUT_FILE", fake_data_dir / "audit_report.json")

    audit.main()

    out = fake_data_dir / "audit_report.json"
    assert out.exists(), "audit_site.main() must write its report"
    report = json.loads(out.read_text(encoding="utf-8"))

    # Sanity-check the shape; counts depend on live posts so we don't pin numbers.
    assert "total_posts" in report
    assert "issues_count" in report
    assert isinstance(report["category_counts"], dict)
    assert isinstance(report["posts_without_image"], list)
